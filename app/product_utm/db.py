from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import mysql.connector
from mysql.connector import Error

from app.product_utm.config import ProductUTMConfig
from app.utils.logger import get_logger
from app.utils.replica_reader import ReplicaReader, HEARTBEAT_UPSERT

logger = get_logger(__name__)


class ProductUTMDBClient:
    """Writer connection for writes/DDL; fetch_all() (reads only) is served by the read replica
    when DB_READ_REPLICA_HOST is set."""

    def __init__(self, brand_name: str, host: str, user: str, password: str, database: str, port: int = 3306):
        self.brand_name = brand_name
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.connection = None
        self.replica = ReplicaReader(brand_name, user, password, database, write_heartbeat=self._write_heartbeat)

    def connect(self):
        if self.connection and self.connection.is_connected():
            return self.connection

        self.connection = mysql.connector.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            autocommit=True,
        )
        return self.connection

    def close(self):
        self.replica.close()
        if self.connection and self.connection.is_connected():
            self.connection.close()

    def fetch_all(self, query: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        return self.replica.read(query, params, self._fetch_all_from_writer)

    def _write_heartbeat(self, token: int) -> None:
        self.execute(HEARTBEAT_UPSERT, (token,), commit=True)

    def _fetch_all_from_writer(self, query: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        connection = self.connect()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            cursor.close()

    def execute(self, query: str, params: tuple[Any, ...] | None = None, commit: bool = False) -> int:
        connection = self.connect()
        cursor = connection.cursor()
        try:
            cursor.execute(query, params)
            if commit:
                connection.commit()
            return cursor.rowcount
        finally:
            cursor.close()

    def execute_many(self, query: str, rows: Iterable[tuple[Any, ...]], commit: bool = False) -> int:
        connection = self.connect()
        cursor = connection.cursor()
        try:
            row_list = list(rows)
            if not row_list:
                return 0
            cursor.executemany(query, row_list)
            if commit:
                connection.commit()
            return cursor.rowcount
        finally:
            cursor.close()

    def begin(self):
        self.connect().start_transaction()

    def commit(self):
        self.connect().commit()

    def rollback(self):
        if self.connection and self.connection.is_connected():
            self.connection.rollback()


def load_query_file(name: str) -> str:
    query_path = Path(__file__).resolve().parent / "queries" / name
    return query_path.read_text(encoding="utf-8")


INSERT_COLUMNS_DAILY = (
    "date",
    "product_id",
    "utm_source",
    "sessions",
    "atc_sessions",
    "orders",
    "sales",
    "average_order_value",
    "cod_orders",
    "prepaid_orders",
    "partially_prepaid_orders",
    "cancelled_orders",
    "refunded_orders",
)

INSERT_COLUMNS_HOURLY = (
    "date",
    "hour",
    "product_id",
    "utm_source",
    "sessions",
    "atc_sessions",
    "orders",
    "sales",
    "average_order_value",
    "cod_orders",
    "prepaid_orders",
    "partially_prepaid_orders",
    "cancelled_orders",
    "refunded_orders",
)


def chunk_rows(rows: list[dict[str, Any]], batch_size: int | None = None) -> list[list[dict[str, Any]]]:
    size = batch_size or ProductUTMConfig.DB_BATCH_SIZE
    return [rows[index:index + size] for index in range(0, len(rows), size)]
