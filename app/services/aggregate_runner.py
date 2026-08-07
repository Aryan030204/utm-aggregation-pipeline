from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.utils.logger import get_logger
from app.utils.retry import retry_db_operation
from app.services.db_manager import DBManager
from app.services.brand_context import build_brand_context
from app.services.query_builder import (
    build_delete_query,
    build_orders_query,
    build_bulk_insert_query,
    get_all_columns,
    get_dimension_columns,
)
from app.services.shopify_sessions_fetcher import ShopifySessionsFetcher
from app.services.utm_merge_service import UtmMergeService
from app.product_utm.services.graphql_request_manager import GraphQLRequestManager
from app.sql.setup import ensure_tables_exist, DAILY_TABLES, HOURLY_TABLES

logger = get_logger(__name__)

INSERT_CHUNK_SIZE = 500

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
        self.sessions_fetcher = ShopifySessionsFetcher(brand_context, request_manager)

    @retry_db_operation()
    def initialize(self):
        """Ensures that the aggregate tables exist before we try to populate them."""
        ensure_tables_exist(self.db_manager)

    def _rebuild_table(
        self,
        table_name: str,
        is_hourly: bool,
        metric_date: str,
        session_rows: List[Dict[str, Any]],
    ):
        columns = get_all_columns(table_name, is_hourly)
        dims = get_dimension_columns(table_name, is_hourly)

        # 1. Delete current day's aggregates
        delete_query = build_delete_query(table_name)
        self.db_manager.execute_query(delete_query, (metric_date,), commit=True)

        # 2. Orders + sales + payment split + cancel/refund, from MySQL (shopify_orders + returns_fact)
        start_dt = f"{metric_date} 00:00:00"
        next_date = (datetime.strptime(metric_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        end_dt = f"{next_date} 00:00:00"

        order_rows = self.db_manager.execute_query(
            build_orders_query(table_name, is_hourly), (start_dt, end_dt), commit=False
        )

        # 3. Merge orders with the (already-fetched, shared-across-tables) session rows
        rows = UtmMergeService.merge(dims, metric_date, order_rows, session_rows)

        if not rows:
            return

        # 4. Bulk insert the merged rows into the aggregate table in chunks.
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

        try:
            for metric_date in self.target_dates:
                logger.info(f"Starting aggregations for brand: {brand_name}, date: {metric_date}")

                # Sessions/atc_sessions are grouped by utm_source/utm_medium/utm_campaign
                # (+hour) regardless of which of the 7 daily/7 hourly tables is being
                # rebuilt, so fetch each granularity from Shopify once per date and
                # reuse it across all tables of that granularity, instead of re-fetching
                # (and re-paginating) the same data 7x over.
                daily_session_rows = self.sessions_fetcher.fetch_daily_rows(metric_date)
                hourly_session_rows = self.sessions_fetcher.fetch_hourly_rows(metric_date)

                for table_name in DAILY_TABLES:
                    logger.debug(f"Rebuilding {table_name} for date {metric_date}")
                    self._rebuild_table(table_name, False, metric_date, daily_session_rows)

                for table_name in HOURLY_TABLES:
                    logger.debug(f"Rebuilding {table_name} for date {metric_date}")
                    self._rebuild_table(table_name, True, metric_date, hourly_session_rows)

            logger.info(f"Successfully rebuilt all tables for {brand_name} across {len(self.target_dates)} day(s).")
        except Exception as e:
            logger.error(f"Failed to rebuild aggregate tables for {brand_name}: {e}")
            raise e
        finally:
            self.db_manager.close()
