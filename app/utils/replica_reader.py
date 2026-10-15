from __future__ import annotations

import os
import time
from typing import Any, Callable

import mysql.connector

from app.utils.logger import get_logger
from app.utils.retry import is_transient_db_error

logger = get_logger(__name__)

HEARTBEAT_TABLE = "utm_replica_heartbeat"
HEARTBEAT_DDL = f"""
CREATE TABLE IF NOT EXISTS {HEARTBEAT_TABLE} (
    id TINYINT UNSIGNED NOT NULL,
    token BIGINT NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
# GREATEST keeps the token monotonic when several containers write the same row.
HEARTBEAT_UPSERT = (
    f"INSERT INTO {HEARTBEAT_TABLE} (id, token, updated_at) VALUES (1, %s, NOW(6)) "
    "ON DUPLICATE KEY UPDATE token = GREATEST(token, VALUES(token)), updated_at = NOW(6)"
)
HEARTBEAT_SELECT = f"SELECT token FROM {HEARTBEAT_TABLE} WHERE id = 1"

_MISSING_TABLE_ERRNO = 1146
_POLL_INTERVAL_SECONDS = 1.0


def replica_host() -> str:
    return os.getenv("DB_READ_REPLICA_HOST", "").strip()


def _replica_port() -> int:
    return int(os.getenv("DB_READ_REPLICA_PORT", "3306") or 3306)


def _sync_timeout_seconds() -> float:
    return float(os.getenv("READ_REPLICA_SYNC_TIMEOUT_SECONDS", "30") or 30)


def _fallback_enabled() -> bool:
    return os.getenv("READ_REPLICA_FALLBACK_TO_WRITER", "true").strip().lower() in ("1", "true", "yes")


class ReplicaNotSynced(Exception):
    """The replica did not catch up to the run's heartbeat within the timeout."""


class ReplicaReader:
    """Serves a run's read queries from the read replica; everything else stays on the writer.

    Disabled (every read goes to the writer, exactly as before) when DB_READ_REPLICA_HOST is empty.

    Before the first read of a run it writes a heartbeat token on the writer and waits until the
    replica has it, so the replica is guaranteed to hold everything committed before the run started
    reading. If the replica is unreachable or does not catch up in time, the run's reads use the
    writer instead (unless READ_REPLICA_FALLBACK_TO_WRITER=false, which raises)."""

    def __init__(
        self,
        label: str,
        user: str,
        password: str,
        database: str,
        write_heartbeat: Callable[[int], None],
    ):
        self.label = label
        self.host = replica_host()
        self.port = _replica_port()
        self._user = user
        self._password = password
        self._database = database
        self._write_heartbeat = write_heartbeat
        self._conn = None
        self._ready = False
        self._use_writer = False

    @property
    def enabled(self) -> bool:
        return bool(self.host)

    def read(self, query: str, params: tuple | None, writer_read: Callable[[str, tuple | None], list]) -> list[dict[str, Any]]:
        if not self.enabled or self._use_writer:
            return writer_read(query, params)

        try:
            self._ensure_ready()
        except Exception as exc:
            return self._fall_back(exc, query, params, writer_read)

        try:
            return self._query(query, params)
        except Exception as exc:
            if not is_transient_db_error(exc):
                raise
            self._drop_connection()
            return self._fall_back(exc, query, params, writer_read)

    def close(self) -> None:
        self._drop_connection()

    def _fall_back(self, exc: Exception, query, params, writer_read) -> list[dict[str, Any]]:
        if not _fallback_enabled():
            raise exc
        logger.warning(
            "[%s] Read replica %s unavailable (%s); reading from the writer for the rest of this run.",
            self.label, self.host, exc,
        )
        self._use_writer = True
        return writer_read(query, params)

    def _ensure_ready(self) -> None:
        if self._ready:
            return
        self._connect()
        self._wait_until_synced()
        self._ready = True

    def _connect(self) -> None:
        if self._conn is not None and self._conn.is_connected():
            return
        self._conn = mysql.connector.connect(
            host=self.host,
            port=self.port,
            user=self._user,
            password=self._password,
            database=self._database,
            autocommit=True,
            connection_timeout=10,
        )
        info = self._query("SELECT @@read_only AS ro, @@hostname AS h", None)[0]
        if int(info["ro"]) != 1:
            logger.warning(
                "[%s] DB_READ_REPLICA_HOST %s is writable (read_only=0); it does not look like a replica.",
                self.label, self.host,
            )

    def _wait_until_synced(self) -> None:
        token = time.time_ns() // 1000
        self._write_heartbeat(token)

        started = time.monotonic()
        deadline = started + _sync_timeout_seconds()
        while True:
            try:
                rows = self._query(HEARTBEAT_SELECT, None)
                if rows and int(rows[0]["token"]) >= token:
                    logger.info(
                        "[%s] Reads served by replica %s (caught up in %.1fs).",
                        self.label, self.host, time.monotonic() - started,
                    )
                    return
            except mysql.connector.Error as exc:
                # The heartbeat table not having replicated yet just means "not caught up".
                if getattr(exc, "errno", None) != _MISSING_TABLE_ERRNO:
                    raise
            if time.monotonic() >= deadline:
                raise ReplicaNotSynced(f"replica did not catch up within {_sync_timeout_seconds():.0f}s")
            time.sleep(_POLL_INTERVAL_SECONDS)

    def _query(self, query: str, params: tuple | None) -> list[dict[str, Any]]:
        cursor = self._conn.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            cursor.close()

    def _drop_connection(self) -> None:
        if self._conn is not None:
            try:
                if self._conn.is_connected():
                    self._conn.close()
            except Exception:
                pass
        self._conn = None
