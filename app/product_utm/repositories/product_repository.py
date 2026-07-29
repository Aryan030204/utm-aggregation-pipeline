from __future__ import annotations

from datetime import date, timedelta

from app.product_utm.db import ProductUTMDBClient, load_query_file


class ProductRepository:
    def __init__(self, db_client: ProductUTMDBClient):
        self.db_client = db_client
        self.query = load_query_file("top_products.sql")

    def fetch_top_products(self, effective_end_date: date, lookback_days: int, limit: int) -> list[dict]:
        start_date = effective_end_date - timedelta(days=max(lookback_days, 1) - 1)
        return self.db_client.fetch_all(
            self.query,
            (
                start_date.isoformat(),
                effective_end_date.isoformat(),
                limit,
            ),
        )
