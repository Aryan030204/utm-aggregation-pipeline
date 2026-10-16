import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.utils.logger import get_logger
from app.utils.retry import retry_db_operation, is_transient_db_error
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
WRITE_MAX_ATTEMPTS = 2


class RunLockNotAcquired(Exception):
    """Another process is already aggregating this brand's database."""


class AggregateRunner:
    def __init__(self, brand_info: Dict[str, Any], target_dates: List[str], lock_wait_seconds: int = 0):
        self.brand_info = brand_info
        self.target_dates = target_dates
        # 0 = don't wait: skip if another run (API trigger / global worker) holds the brand lock.
        self.lock_wait_seconds = lock_wait_seconds
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

    def _write_table(self, table_name: str, columns: List[str], rows: List[Dict[str, Any]], metric_date: str):
        """DELETE + INSERT in one transaction so readers never see an empty or partial
        day, with a single commit. Retried only on transient DB errors."""
        for attempt in range(1, WRITE_MAX_ATTEMPTS + 1):
            try:
                self.db_manager.begin()
                self.db_manager.execute_write(build_delete_query(table_name), (metric_date,))
                for start in range(0, len(rows), INSERT_CHUNK_SIZE):
                    chunk = rows[start:start + INSERT_CHUNK_SIZE]
                    insert_query = build_bulk_insert_query(table_name, columns, len(chunk))
                    params: List[Any] = []
                    for row in chunk:
                        params.extend(row[c] for c in columns)
                    self.db_manager.execute_write(insert_query, tuple(params))
                self.db_manager.commit()
                return
            except Exception as exc:
                self.db_manager.rollback()
                if attempt >= WRITE_MAX_ATTEMPTS or not is_transient_db_error(exc):
                    raise
                logger.warning(f"Write to {table_name} failed transiently ({exc}); retrying...")
                time.sleep(2 * attempt)

    def _rebuild_table(
        self,
        table_name: str,
        is_hourly: bool,
        metric_date: str,
        finest_order_rows: List[Dict[str, Any]],
        session_rows: List[Dict[str, Any]],
    ):
        columns = get_all_columns(table_name, is_hourly)
        dims = get_dimension_columns(table_name, is_hourly)

        order_rows = UtmMergeService.rollup_orders(finest_order_rows, dims)
        rows = UtmMergeService.merge(dims, metric_date, order_rows, session_rows)
        self._write_table(table_name, columns, rows, metric_date)

    def run_aggregations(self):
        brand_name = self.brand_info["brand_name"]
        lock_name = DBManager.lock_name(self.brand_info["database"])
        lock_held = False

        try:
            lock_held = self.db_manager.try_lock(lock_name, self.lock_wait_seconds)
            if not lock_held:
                raise RunLockNotAcquired(
                    f"[{brand_name}] another run holds the aggregation lock (waited {self.lock_wait_seconds}s)"
                )

            for metric_date in self.target_dates:
                logger.info(f"Starting aggregations for brand: {brand_name}, date: {metric_date}")

                # Shopify first: if it fails we haven't spent any DB time on this date.
                # Sessions are grouped by utm_source/medium/campaign (+hour) regardless of
                # which table is being rebuilt, so each granularity is fetched once per date.
                daily_session_rows = self.sessions_fetcher.fetch_daily_rows(metric_date)
                hourly_session_rows = self.sessions_fetcher.fetch_hourly_rows(metric_date)

                # One orders/returns query per date; every table below is rolled up from it.
                # Plain dates (not datetimes): the query filters on the indexed created_dt column.
                next_date = (datetime.strptime(metric_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                finest_order_rows = self.db_manager.read_all(build_orders_query(), (metric_date, next_date))

                for table_name in DAILY_TABLES:
                    logger.debug(f"Rebuilding {table_name} for date {metric_date}")
                    self._rebuild_table(table_name, False, metric_date, finest_order_rows, daily_session_rows)

                for table_name in HOURLY_TABLES:
                    logger.debug(f"Rebuilding {table_name} for date {metric_date}")
                    self._rebuild_table(table_name, True, metric_date, finest_order_rows, hourly_session_rows)

            logger.info(f"Successfully rebuilt all tables for {brand_name} across {len(self.target_dates)} day(s).")
        except RunLockNotAcquired:
            raise
        except Exception as e:
            logger.error(f"Failed to rebuild aggregate tables for {brand_name}: {e}")
            raise e
        finally:
            if lock_held:
                self.db_manager.release_lock(lock_name)
            self.db_manager.close()
