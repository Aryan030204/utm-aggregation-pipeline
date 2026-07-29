from __future__ import annotations

from datetime import date
from typing import Iterable

from app.product_utm.config import ProductUTMConfig
from app.product_utm.db import (
    INSERT_COLUMNS_DAILY,
    INSERT_COLUMNS_HOURLY,
    ProductUTMDBClient,
    chunk_rows,
    load_query_file,
)
from app.product_utm.models import StageError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TableService:
    def __init__(self, db_client: ProductUTMDBClient, brand_name: str):
        self.db_client = db_client
        self.brand_name = brand_name

    def ensure_tables_exist(self):
        self.db_client.execute(load_query_file("create_product_utm_daily.sql"))
        self.db_client.execute(load_query_file("create_product_utm_hourly.sql"))

    def write_daily_rows(self, start_date: date, end_date: date, rows: list[dict]) -> tuple[int, int]:
        return self._write_rows(
            table_name="product_utm_daily",
            columns=INSERT_COLUMNS_DAILY,
            stage="Writing Daily Table",
            start_date=start_date,
            end_date=end_date,
            rows=rows,
        )

    def write_hourly_rows(self, start_date: date, end_date: date, rows: list[dict]) -> tuple[int, int]:
        return self._write_rows(
            table_name="product_utm_hourly",
            columns=INSERT_COLUMNS_HOURLY,
            stage="Writing Hourly Table",
            start_date=start_date,
            end_date=end_date,
            rows=rows,
        )

    def _write_rows(
        self,
        table_name: str,
        columns: tuple[str, ...],
        stage: str,
        start_date: date,
        end_date: date,
        rows: list[dict],
    ) -> tuple[int, int]:
        placeholders = ", ".join(["%s"] * len(columns))
        insert_sql = f"""
            INSERT INTO {table_name} ({", ".join(columns)}, created_at, updated_at)
            VALUES ({placeholders}, NOW(), NOW())
        """
        delete_sql = f"DELETE FROM {table_name} WHERE date BETWEEN %s AND %s"

        deleted_rows = 0
        inserted_rows = 0
        try:
            self.db_client.begin()
            deleted_rows = self.db_client.execute(delete_sql, (start_date.isoformat(), end_date.isoformat()))
            for chunk in chunk_rows(rows, ProductUTMConfig.DB_BATCH_SIZE):
                prepared_rows = [tuple(row[column] for column in columns) for row in chunk]
                inserted_rows += self.db_client.execute_many(insert_sql, prepared_rows)
            self.db_client.commit()
            return deleted_rows, inserted_rows
        except Exception as exc:
            self.db_client.rollback()
            raise StageError(stage, str(exc), original_exception=exc)
