import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import mysql.connector

from app.product_utm.db import ProductUTMDBClient
from app.services.db_manager import DBManager
from app.utils import replica_reader

WRITER, REPLICA = "writer.example", "replica.example"
ENV = {"DB_READ_REPLICA_HOST": REPLICA, "READ_REPLICA_SYNC_TIMEOUT_SECONDS": "5", "READ_REPLICA_FALLBACK_TO_WRITER": "true"}


class FakeCursor:
    def __init__(self, server):
        self.server, self.rowcount, self._rows = server, 1, []

    def execute(self, sql, params=None):
        self.server.handle(sql, params, self)

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class FakeConn:
    in_transaction = False

    def __init__(self, server):
        self.server = server

    def cursor(self, dictionary=False):
        return FakeCursor(self.server)

    def is_connected(self):
        return True

    def commit(self):
        pass

    def rollback(self):
        pass

    def start_transaction(self):
        pass

    def close(self):
        pass


class FakeServer:
    """One fake MySQL host. `on_replica_poll` scripts the heartbeat SELECT results."""

    def __init__(self, host, log, role):
        self.host, self.log, self.role = host, log, role
        self.heartbeat_token = 0
        self.replicates_to = None   # the writer fake pushes heartbeat writes to its replica fake
        self.polls = []          # scripted replies for the heartbeat SELECT: int token, or an Exception
        self.query_error = None

    def handle(self, sql, params, cursor):
        s = " ".join(sql.split())
        self.log.append((self.host, s.split("(")[0][:48], params))
        if s.startswith("SELECT @@read_only"):
            cursor._rows = [{"ro": 1 if self.role == "replica" else 0, "h": self.host}]
        elif s.startswith("INSERT INTO utm_replica_heartbeat"):
            self.heartbeat_token = max(self.heartbeat_token, params[0])
            if self.replicates_to is not None:
                self.replicates_to.heartbeat_token = max(self.replicates_to.heartbeat_token, params[0])
        elif s.startswith("SELECT token FROM utm_replica_heartbeat"):
            reply = self.polls.pop(0) if self.polls else self.heartbeat_token
            if isinstance(reply, Exception):
                raise reply
            cursor._rows = [{"token": reply}]
        elif s.startswith("SELECT GET_LOCK"):
            cursor._rows = [{"acquired": 1}]
        elif s.startswith("SELECT RELEASE_LOCK"):
            cursor._rows = [{"released": 1}]
        elif s.startswith("SELECT") and self.query_error is not None:
            raise self.query_error
        elif s.startswith("SELECT"):
            cursor._rows = [{"served_by": self.host}]


class ReplicaRoutingBase(unittest.TestCase):
    def setUp(self):
        self.log = []
        self.servers = {WRITER: FakeServer(WRITER, self.log, "writer"), REPLICA: FakeServer(REPLICA, self.log, "replica")}
        self.servers[WRITER].replicates_to = self.servers[REPLICA]
        self.connect_errors = {}
        self.clock = [0.0]

        def fake_connect(**kwargs):
            host = kwargs["host"]
            if host in self.connect_errors:
                raise self.connect_errors[host]
            return FakeConn(self.servers[host])

        fake_time = SimpleNamespace(
            time_ns=lambda: 1_000_000_000_000,                    # token = 1_000_000_000 microseconds
            monotonic=lambda: self.clock[0],
            sleep=lambda s: self.clock.__setitem__(0, self.clock[0] + s),
        )
        for p in (patch.object(mysql.connector, "connect", fake_connect),
                  patch.object(replica_reader, "time", fake_time),
                  patch.dict(os.environ, ENV)):
            p.start()
            self.addCleanup(p.stop)

    def hosts(self, prefix=""):
        return [h for h, sql, _ in self.log if sql.startswith(prefix)]

    def manager(self):
        return DBManager("Brand", WRITER, "u", "p", "db1")


class DBManagerRoutingTests(ReplicaRoutingBase):
    def test_flag_off_reads_stay_on_the_writer_and_never_touch_the_replica(self):
        with patch.dict(os.environ, {"DB_READ_REPLICA_HOST": ""}):
            rows = self.manager().read_all("SELECT * FROM shopify_orders", (1,))
        self.assertEqual(rows, [{"served_by": WRITER}])
        self.assertNotIn(REPLICA, self.hosts())
        self.assertEqual(self.hosts("INSERT INTO utm_replica_heartbeat"), [])

    def test_reads_go_to_the_replica_after_the_heartbeat_barrier(self):
        db = self.manager()
        rows = db.read_all("SELECT * FROM shopify_orders", (1,))

        self.assertEqual(rows, [{"served_by": REPLICA}])
        self.assertEqual(self.hosts("INSERT INTO utm_replica_heartbeat"), [WRITER])
        self.assertEqual(self.hosts("SELECT token FROM utm_replica_heartbeat"), [REPLICA])
        order = [sql for _, sql, _ in self.log]
        self.assertLess(order.index("INSERT INTO utm_replica_heartbeat "), order.index("SELECT * FROM shopify_orders"))

    def test_barrier_runs_once_per_run_not_once_per_read(self):
        db = self.manager()
        db.read_all("SELECT 1 FROM a")
        db.read_all("SELECT 2 FROM b")
        self.assertEqual(self.hosts("INSERT INTO utm_replica_heartbeat"), [WRITER])
        self.assertEqual(len(self.hosts("SELECT token FROM utm_replica_heartbeat")), 1)

    def test_locks_and_writes_stay_on_the_writer(self):
        db = self.manager()
        db.try_lock("name", 0)
        db.read_all("SELECT * FROM shopify_orders")
        db.release_lock("name")
        self.assertEqual(self.hosts("SELECT GET_LOCK"), [WRITER])
        self.assertEqual(self.hosts("SELECT RELEASE_LOCK"), [WRITER])

    def test_waits_until_the_replica_has_the_token_then_reads(self):
        self.servers[REPLICA].polls = [0, 0, 1_000_000_000]
        rows = self.manager().read_all("SELECT * FROM shopify_orders")
        self.assertEqual(rows, [{"served_by": REPLICA}])
        self.assertEqual(len(self.hosts("SELECT token FROM utm_replica_heartbeat")), 3)

    def test_a_larger_token_from_another_container_also_satisfies_the_barrier(self):
        self.servers[REPLICA].polls = [9_999_999_999_999]
        self.assertEqual(self.manager().read_all("SELECT 1 FROM t"), [{"served_by": REPLICA}])

    def test_missing_heartbeat_table_on_the_replica_means_not_caught_up_yet(self):
        self.servers[REPLICA].polls = [mysql.connector.errors.ProgrammingError("no table", errno=1146), 1_000_000_000]
        self.assertEqual(self.manager().read_all("SELECT 1 FROM t"), [{"served_by": REPLICA}])

    def test_timeout_falls_back_to_the_writer_and_sticks_for_the_run(self):
        self.servers[REPLICA].polls = [0] * 50
        db = self.manager()
        self.assertEqual(db.read_all("SELECT 1 FROM t"), [{"served_by": WRITER}])
        polls_after_first = len(self.hosts("SELECT token FROM utm_replica_heartbeat"))
        self.assertEqual(db.read_all("SELECT 2 FROM t"), [{"served_by": WRITER}])
        self.assertEqual(len(self.hosts("SELECT token FROM utm_replica_heartbeat")), polls_after_first)

    def test_timeout_raises_when_fallback_is_disabled(self):
        self.servers[REPLICA].polls = [0] * 50
        with patch.dict(os.environ, {"READ_REPLICA_FALLBACK_TO_WRITER": "false"}):
            with self.assertRaises(replica_reader.ReplicaNotSynced):
                self.manager().read_all("SELECT 1 FROM t")

    def test_unreachable_replica_falls_back_to_the_writer(self):
        self.connect_errors[REPLICA] = mysql.connector.errors.InterfaceError("cannot connect", errno=2003)
        self.assertEqual(self.manager().read_all("SELECT 1 FROM t"), [{"served_by": WRITER}])

    def test_transient_error_during_the_replica_query_falls_back(self):
        self.servers[REPLICA].query_error = mysql.connector.errors.OperationalError("lost", errno=2013)
        self.assertEqual(self.manager().read_all("SELECT 1 FROM t"), [{"served_by": WRITER}])

    def test_sql_errors_on_the_replica_are_not_masked_by_a_fallback(self):
        self.servers[REPLICA].query_error = mysql.connector.errors.ProgrammingError("bad sql", errno=1064)
        with self.assertRaises(mysql.connector.errors.ProgrammingError):
            self.manager().read_all("SELECT 1 FROM t")

    def test_close_closes_the_replica_connection(self):
        db = self.manager()
        db.read_all("SELECT 1 FROM t")
        conn = db.replica._conn
        with patch.object(conn, "close") as closed:
            db.close()
        closed.assert_called_once()


class ProductClientRoutingTests(ReplicaRoutingBase):
    def client(self):
        return ProductUTMDBClient("Brand", WRITER, "u", "p", "db1")

    def test_fetch_all_reads_from_the_replica_but_writes_use_the_writer(self):
        client = self.client()
        self.assertEqual(client.fetch_all("SELECT * FROM mv_product_sessions_by_path_daily"), [{"served_by": REPLICA}])
        client.execute("DELETE FROM product_utm_daily WHERE date = %s", ("2026-09-20",))
        self.assertEqual(self.hosts("DELETE FROM product_utm_daily"), [WRITER])
        self.assertEqual(self.hosts("INSERT INTO utm_replica_heartbeat"), [WRITER])

    def test_flag_off_keeps_product_reads_on_the_writer(self):
        with patch.dict(os.environ, {"DB_READ_REPLICA_HOST": ""}):
            self.assertEqual(self.client().fetch_all("SELECT 1 FROM t"), [{"served_by": WRITER}])
        self.assertNotIn(REPLICA, self.hosts())


class HeartbeatSqlTests(unittest.TestCase):
    def test_upsert_keeps_the_token_monotonic(self):
        self.assertIn("GREATEST(token, VALUES(token))", replica_reader.HEARTBEAT_UPSERT)

    def test_heartbeat_table_has_a_primary_key(self):
        self.assertIn("PRIMARY KEY (id)", replica_reader.HEARTBEAT_DDL)


if __name__ == "__main__":
    unittest.main()
