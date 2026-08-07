from typing import Dict, Any, List

from app.utils.logger import get_logger
from app.utils.retry import retry_db_operation
from app.services.db_manager import DBManager
from app.services.brand_context import build_brand_context
from app.services.query_builder import (
    build_delete_query,
    build_sessions_query,
    build_returns_lookup_query,
    build_bulk_insert_query,
    get_all_columns,
    get_dimension_columns,
)
from app.services.shopify_orders_fetcher import ShopifyOrdersFetcher
from app.services.utm_merge_service import UtmMergeService
from app.product_utm.services.graphql_request_manager import GraphQLRequestManager
from app.sql.setup import ensure_tables_exist, DAILY_TABLES, HOURLY_TABLES

logger = get_logger(__name__)

INSERT_CHUNK_SIZE = 500
RETURNS_LOOKUP_CHUNK_SIZE = 1000

class AggregateRunner:
    def __init__(self, brand_info: Dict[str, Any], target_dates: List[str]):
        self.brand_info = brand_info
        self.target_dates = target_dates
        self.db_manager = DBManager(
            brand_name=brand_info["brand_name"],
            host=brand_info["host"],
            user=brand_info["user"],
            password=brand_info["password"],
            database=brand_info["database"],
            port=brand_info.get("port", 3306)
        )
        brand_context = build_brand_context(brand_info)
        request_manager = GraphQLRequestManager(brand_context)
        self.orders_fetcher = ShopifyOrdersFetcher(brand_context, request_manager)

    @retry_db_operation()
    def initialize(self):
        """Ensures that the aggregate tables exist before we try to populate them."""
        ensure_tables_exist(self.db_manager)

    def _fetch_returns_lookup(self, order_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
        order_ids = sorted({row["order_id"] for row in order_rows if row.get("order_id")})
        if not order_ids:
            return {}

        lookup: Dict[str, Dict[str, int]] = {}
        for start in range(0, len(order_ids), RETURNS_LOOKUP_CHUNK_SIZE):
            chunk = order_ids[start:start + RETURNS_LOOKUP_CHUNK_SIZE]
            rows = self.db_manager.execute_query(
                build_returns_lookup_query(chunk), tuple(chunk), commit=False
            )
            for row in rows:
                lookup[row["order_id"]] = {
                    "is_cancelled": row["is_cancelled"],
                    "is_refunded": row["is_refunded"],
                }
        return lookup

    def _rebuild_table(self, table_name: str, is_hourly: bool, metric_date: str):
        columns = get_all_columns(table_name, is_hourly)
        dims = get_dimension_columns(table_name, is_hourly)

        # 1. Delete current day's aggregates
        delete_query = build_delete_query(table_name)
        self.db_manager.execute_query(delete_query, (metric_date,), commit=True)

        # 2. Fetch order-level rows straight from Shopify (paginated ShopifyQL)
        order_rows = (
            self.orders_fetcher.fetch_hourly_rows(metric_date) if is_hourly
            else self.orders_fetcher.fetch_daily_rows(metric_date)
        )

        # 3. Look up cancel/refund flags for exactly the orders we just fetched
        returns_lookup = self._fetch_returns_lookup(order_rows)

        # 4. Fetch session rows for the same date (unchanged source)
        session_rows = self.db_manager.execute_query(
            build_sessions_query(table_name, is_hourly), (metric_date,), commit=False
        )

        # 5. Merge order + returns + session data into the table's UTM-dimension rows
        rows = UtmMergeService.merge(dims, metric_date, order_rows, returns_lookup, session_rows)

        if not rows:
            return

        # 6. Bulk insert the merged rows into the aggregate table in chunks.
        for start in range(0, len(rows), INSERT_CHUNK_SIZE):
            chunk = rows[start:start + INSERT_CHUNK_SIZE]
            insert_query = build_bulk_insert_query(table_name, columns, len(chunk))
            params: List[Any] = []
            for row in chunk:
                params.extend(row[c] for c in columns)
            self.db_manager.execute_query(insert_query, tuple(params), commit=True)

    @retry_db_operation()
    def run_aggregations(self):
        brand_name = self.brand_info["brand_name"]
        all_tables = [(t, False) for t in DAILY_TABLES] + [(t, True) for t in HOURLY_TABLES]

        try:
            for metric_date in self.target_dates:
                logger.info(f"Starting aggregations for brand: {brand_name}, date: {metric_date}")

                for table_name, is_hourly in all_tables:
                    logger.debug(f"Rebuilding {table_name} for date {metric_date}")
                    self._rebuild_table(table_name, is_hourly, metric_date)

            logger.info(f"Successfully rebuilt all tables for {brand_name} across {len(self.target_dates)} day(s).")
        except Exception as e:
            logger.error(f"Failed to rebuild aggregate tables for {brand_name}: {e}")
            raise e
        finally:
            self.db_manager.close()
