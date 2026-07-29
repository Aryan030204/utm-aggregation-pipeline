from __future__ import annotations

from datetime import date

from app.product_utm.db import ProductUTMDBClient, load_query_file


class OrdersRepository:
    def __init__(self, db_client: ProductUTMDBClient):
        self.db_client = db_client
        self.template = load_query_file("orders_aggregation.sql")

    def fetch_daily_aggregates(self, start_date: date, end_date: date, product_ids: list[int], store_timezone: str) -> list[dict]:
        return self._fetch_aggregates("DATE(local_created_at) AS date", "", "date", start_date, end_date, product_ids, store_timezone)

    def fetch_hourly_aggregates(self, start_date: date, end_date: date, product_ids: list[int], store_timezone: str) -> list[dict]:
        return self._fetch_aggregates(
            "DATE(local_created_at) AS date",
            ", HOUR(local_created_at) AS hour",
            "date, hour",
            start_date,
            end_date,
            product_ids,
            store_timezone,
        )

    def _fetch_aggregates(
        self,
        date_select: str,
        extra_select: str,
        group_by_prefix: str,
        start_date: date,
        end_date: date,
        product_ids: list[int],
        store_timezone: str,
    ) -> list[dict]:
        if not product_ids:
            return []

        placeholders = ", ".join(["%s"] * len(product_ids))
        query = self.template.format(
            date_select=date_select,
            extra_select=extra_select,
            group_by_prefix=group_by_prefix,
            product_placeholders=placeholders,
        )
        params = (
            store_timezone,
            store_timezone,
            start_date.isoformat(),
            end_date.isoformat(),
            *product_ids,
        )
        return self.db_client.fetch_all(query, params)
