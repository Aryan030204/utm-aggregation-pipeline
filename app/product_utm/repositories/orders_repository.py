from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from app.product_utm.db import ProductUTMDBClient, load_query_file


class OrdersRepository:
    def __init__(self, db_client: ProductUTMDBClient):
        self.db_client = db_client
        self.template = load_query_file("orders_aggregation.sql")

    def fetch_hourly_aggregates(self, start_date: date, end_date: date, product_ids: list[int], store_timezone: str) -> list[dict]:
        if not product_ids:
            return []
        local_start, local_end = self._compute_local_window(start_date, end_date)
        return self._fetch_hourly_aggregates(product_ids, local_start, local_end)

    def derive_daily_aggregates(self, hourly_rows: list[dict]) -> list[dict]:
        aggregated: dict[tuple[str, int, str], dict] = {}

        for row in hourly_rows:
            key = (self._normalize_date(row.get("date")), int(row.get("product_id")), self._normalize_source(row.get("utm_source")))
            target = aggregated.setdefault(
                key,
                {
                    "date": key[0],
                    "product_id": key[1],
                    "utm_source": key[2],
                    "orders": 0,
                    "sales": Decimal("0.00"),
                    "cod_orders": 0,
                    "prepaid_orders": 0,
                    "partially_prepaid_orders": 0,
                    "cancelled_orders": 0,
                    "refunded_orders": 0,
                },
            )
            target["orders"] += int(row.get("orders", 0) or 0)
            target["sales"] += Decimal(str(row.get("sales", 0) or 0))
            target["cod_orders"] += int(row.get("cod_orders", 0) or 0)
            target["prepaid_orders"] += int(row.get("prepaid_orders", 0) or 0)
            target["partially_prepaid_orders"] += int(row.get("partially_prepaid_orders", 0) or 0)
            target["cancelled_orders"] += int(row.get("cancelled_orders", 0) or 0)
            target["refunded_orders"] += int(row.get("refunded_orders", 0) or 0)

        daily_rows: list[dict] = []
        for row in aggregated.values():
            orders = row["orders"]
            sales = row["sales"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            daily_rows.append(
                {
                    **row,
                    "sales": sales,
                    "average_order_value": (sales / orders).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if orders
                    else Decimal("0.00"),
                }
            )

        return sorted(daily_rows, key=lambda row: (row["date"], row["product_id"], row["utm_source"]))

    def fetch_daily_aggregates(self, start_date: date, end_date: date, product_ids: list[int], store_timezone: str) -> list[dict]:
        return self.derive_daily_aggregates(
            self.fetch_hourly_aggregates(start_date, end_date, product_ids, store_timezone)
        )

    def _fetch_hourly_aggregates(
        self,
        product_ids: list[int],
        local_start: date,
        local_end: date,
    ) -> list[dict]:
        return self._execute_aggregate_query(
            "DATE(local_created_at) AS date",
            ", HOUR(local_created_at) AS hour",
            "date, hour",
            product_ids,
            local_start,
            local_end,
        )

    def _execute_aggregate_query(
        self,
        date_select: str,
        extra_select: str,
        group_by_prefix: str,
        product_ids: list[int],
        local_start: date,
        local_end: date,
    ) -> list[dict]:
        placeholders = ", ".join(["%s"] * len(product_ids))
        query = self.template.format(
            date_select=date_select,
            extra_select=extra_select,
            group_by_prefix=group_by_prefix,
            product_placeholders=placeholders,
        )
        # Whole-day window as plain dates: the query filters on the indexed created_dt column
        # (created_at has no index, so filtering on it scans the entire shopify_orders table).
        params = (
            local_start.isoformat(),
            local_end.isoformat(),
            *product_ids,
        )
        return self.db_client.fetch_all(query, params)

    @staticmethod
    def _compute_local_window(start_date: date, end_date: date) -> tuple[date, date]:
        """[start_date, end_date + 1 day) -- half-open, in whole days."""
        return start_date, end_date + timedelta(days=1)

    @staticmethod
    def _normalize_date(value: object) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _normalize_source(value: object) -> str:
        if value is None:
            return "direct"
        text = str(value).strip()
        return text or "direct"
