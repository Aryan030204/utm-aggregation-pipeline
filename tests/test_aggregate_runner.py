import unittest
from unittest.mock import patch

from app.services.aggregate_runner import AggregateRunner, RunLockNotAcquired
from app.sql.setup import DAILY_TABLES, HOURLY_TABLES

BRAND_INFO = {
    "brand_id": "1", "brand_name": "Brand", "host": "h", "user": "u", "password": "p",
    "database": "db1", "port": 3306, "access_token": "tok", "shop_name": "shop",
}


class TransientError(Exception):
    errno = 2013


class FakeDB:
    def __init__(self, events, lock_ok=True, write_failures=None):
        self.events = events
        self.lock_ok = lock_ok
        self.write_failures = list(write_failures or [])

    def try_lock(self, name, timeout):
        self.events.append(("lock", timeout))
        return self.lock_ok

    def release_lock(self, name):
        self.events.append(("unlock",))

    def read_all(self, query, params=None):
        self.events.append(("orders_query", params))
        return [{
            "metric_date": "d", "metric_hour": 9, "utm_source": "google", "utm_medium": "cpc",
            "utm_campaign": "spring", "orders": 2, "sales": 30, "prepaid_orders": 1, "cod_orders": 1,
            "ppcod_orders": 0, "cancelled_orders": 0, "refunded_orders": 0,
        }]

    def begin(self):
        self.events.append(("begin",))

    def execute_write(self, query, params=None):
        if self.write_failures:
            raise self.write_failures.pop(0)
        self.events.append(("write", query.strip().split()[0]))

    def commit(self):
        self.events.append(("commit",))

    def rollback(self):
        self.events.append(("rollback",))

    def close(self):
        self.events.append(("close",))


class FakeSessions:
    def __init__(self, events):
        self.events = events

    def fetch_daily_rows(self, metric_date):
        self.events.append(("sessions_daily", metric_date))
        return [{"hour": None, "utm_source": "google", "utm_medium": "cpc", "utm_campaign": "spring", "sessions": 10, "atc_sessions": 1}]

    def fetch_hourly_rows(self, metric_date):
        self.events.append(("sessions_hourly", metric_date))
        return [{"hour": 9, "utm_source": "google", "utm_medium": "cpc", "utm_campaign": "spring", "sessions": 10, "atc_sessions": 1}]


def make_runner(events, dates=("2026-09-19", "2026-09-20"), **db_kwargs):
    runner = AggregateRunner(BRAND_INFO, list(dates))
    runner.db_manager = FakeDB(events, **db_kwargs)
    runner.sessions_fetcher = FakeSessions(events)
    return runner


class RunAggregationsTests(unittest.TestCase):
    def test_one_orders_query_and_one_transaction_per_table_per_date(self):
        events = []
        make_runner(events).run_aggregations()
        names = [e[0] for e in events]
        tables = len(DAILY_TABLES) + len(HOURLY_TABLES)

        self.assertEqual(names.count("orders_query"), 2)          # once per date, not 14x per date
        self.assertEqual(names.count("sessions_daily"), 2)
        self.assertEqual(names.count("sessions_hourly"), 2)
        self.assertEqual(names.count("begin"), 2 * tables)
        self.assertEqual(names.count("commit"), 2 * tables)
        self.assertNotIn("rollback", names)

        # DELETE and INSERT sit inside the same transaction, with one commit.
        first_tx = events[events.index(("begin",)):events.index(("commit",)) + 1]
        self.assertEqual(first_tx, [("begin",), ("write", "DELETE"), ("write", "INSERT"), ("commit",)])

    def test_orders_query_is_called_with_plain_dates_for_the_indexed_window(self):
        events = []
        make_runner(events, dates=("2026-09-19", "2026-09-20")).run_aggregations()
        self.assertEqual([e[1] for e in events if e[0] == "orders_query"],
                         [("2026-09-19", "2026-09-20"), ("2026-09-20", "2026-09-21")])

    def test_orders_sql_filters_on_created_dt_not_the_unindexed_created_at(self):
        from app.services.query_builder import build_orders_query
        sql = build_orders_query()
        self.assertIn("WHERE created_dt >= %s AND created_dt < %s", sql)
        self.assertNotIn("created_at >=", sql)
        self.assertNotIn("created_at <", sql)

    def test_shopify_is_fetched_before_the_database_is_queried(self):
        events = []
        make_runner(events, dates=("2026-09-20",)).run_aggregations()
        names = [e[0] for e in events]
        self.assertLess(names.index("sessions_hourly"), names.index("orders_query"))

    def test_lock_is_taken_and_released(self):
        events = []
        make_runner(events).run_aggregations()
        self.assertEqual(events[0], ("lock", 0))
        self.assertEqual(events[-2:], [("unlock",), ("close",)])

    def test_lock_held_elsewhere_skips_all_work(self):
        events = []
        runner = make_runner(events, lock_ok=False)
        with self.assertRaises(RunLockNotAcquired):
            runner.run_aggregations()
        self.assertEqual(events, [("lock", 0), ("close",)])


class WriteTableTests(unittest.TestCase):
    ROWS = [{"metric_date": "d", "utm_source": "google"}]

    def run_write(self, failures):
        events = []
        runner = make_runner(events, write_failures=failures)
        columns = ["metric_date", "utm_source"]
        with patch("app.services.aggregate_runner.time.sleep"):
            return events, lambda: runner._write_table("utm_source_daily", columns, self.ROWS, "d")

    def test_transient_error_rolls_back_and_retries_once(self):
        events, write = self.run_write([TransientError("lost connection")])
        write()
        names = [e[0] for e in events]
        self.assertEqual(names.count("begin"), 2)
        self.assertEqual(names.count("rollback"), 1)
        self.assertEqual(names.count("commit"), 1)

    def test_non_transient_error_rolls_back_and_raises_without_retry(self):
        events, write = self.run_write([ValueError("bad sql")])
        with self.assertRaises(ValueError):
            write()
        names = [e[0] for e in events]
        self.assertEqual(names.count("begin"), 1)
        self.assertEqual(names.count("rollback"), 1)
        self.assertEqual(names.count("commit"), 0)


if __name__ == "__main__":
    unittest.main()
