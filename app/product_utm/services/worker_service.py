from __future__ import annotations

import time
from datetime import date, datetime, timedelta

from app.product_utm.config import ProductUTMConfig
from app.product_utm.db import ProductUTMDBClient
from app.product_utm.models import BrandRunSummary, StageError, WorkerRunMetrics
from app.product_utm.repositories.orders_repository import OrdersRepository
from app.product_utm.repositories.product_repository import ProductRepository
from app.product_utm.services.brand_service import BrandService
from app.product_utm.services.graphql_request_manager import GraphQLRequestManager
from app.product_utm.services.merge_service import MergeService
from app.product_utm.services.shopify_report_service import ShopifyReportService
from app.product_utm.services.table_service import TableService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ProductUTMWorkerService:
    _debug_brand_selected = False

    def __init__(self, run_type: str, effective_end_date: date, retrospective_days: int | None = None):
        self.run_type = run_type
        self.effective_end_date = effective_end_date
        self.retrospective_days = retrospective_days or ProductUTMConfig.RETROSPECTIVE_DAYS

    def run(self) -> WorkerRunMetrics:
        started_at = time.perf_counter()
        metrics = WorkerRunMetrics(run_type=self.run_type)
        brands = BrandService.get_active_brands()
        metrics.brands_discovered = len(brands)

        for brand in brands:
            brand_started_at = time.perf_counter()
            summary = BrandRunSummary(
                brand_name=brand.brand_name,
                run_type=self.run_type.title(),
                run_date=self.effective_end_date.isoformat(),
            )
            metrics.brands_processed += 1
            try:
                self._run_for_brand(brand, summary, metrics)
                summary.status = "SUCCESS"
                metrics.brands_succeeded += 1
            except StageError as exc:
                summary.status = "FAILED"
                summary.stage = exc.stage
                summary.failure_reason = exc.reason
                summary.retry_count = exc.retry_count
                metrics.brands_failed += 1
                logger.error("[%s] %s", brand.brand_name, exc)
            except Exception as exc:
                summary.status = "FAILED"
                summary.stage = summary.stage or "Unknown"
                summary.failure_reason = str(exc)
                metrics.brands_failed += 1
                logger.error("[%s] Unexpected failure: %s", brand.brand_name, exc)
            finally:
                summary.execution_time_seconds = round(time.perf_counter() - brand_started_at, 2)
                self._log_brand_checkpoint(summary)

        metrics.total_execution_time_seconds = round(time.perf_counter() - started_at, 2)
        self._log_worker_summary(metrics)
        return metrics

    def _run_for_brand(self, brand, summary: BrandRunSummary, metrics: WorkerRunMetrics):
        db_client = ProductUTMDBClient(
            brand_name=brand.brand_name,
            host=brand.host,
            user=brand.user,
            password=brand.password,
            database=brand.database,
            port=brand.port,
        )
        request_manager = GraphQLRequestManager(brand)
        debug_mapping = self._should_debug_brand()
        report_service = ShopifyReportService(brand, request_manager, debug_mapping=debug_mapping)
        product_repository = ProductRepository(db_client)
        orders_repository = OrdersRepository(db_client)
        table_service = TableService(db_client, brand.brand_name)

        try:
            summary.stage = "Ensuring Tables"
            table_service.ensure_tables_exist()

            daily_start, daily_end = self._daily_window()
            hourly_start, hourly_end = self._hourly_window()

            summary.stage = "Fetching Top Products"
            top_products = product_repository.fetch_top_products(
                effective_end_date=self.effective_end_date,
                lookback_days=ProductUTMConfig.TOP_PRODUCT_LOOKBACK_DAYS,
                limit=ProductUTMConfig.TOP_PRODUCT_LIMIT,
            )
            summary.top_products_count = len(top_products)
            landing_page_lookup = self._build_landing_page_lookup(top_products, brand.brand_name)
            product_ids = [int(row["product_id"]) for row in top_products if row.get("product_id") is not None]
            if not landing_page_lookup or not product_ids:
                logger.warning("[%s] Skipping writes because no top products were resolved for the target window.", brand.brand_name)
                return

            summary.stage = "Fetching Shopify Reports"
            daily_session_rows = report_service.fetch_daily_rows(daily_start, daily_end, landing_page_lookup)
            hourly_session_rows = []
            if self.run_type == "daily":
                hourly_session_rows = report_service.fetch_hourly_rows(hourly_start, hourly_end, landing_page_lookup)
            summary.session_rows = len(daily_session_rows) + len(hourly_session_rows)
            metrics.total_session_rows += summary.session_rows

            summary.stage = "Fetching Orders"
            daily_order_rows = orders_repository.fetch_daily_aggregates(daily_start, daily_end, product_ids, brand.store_timezone)
            hourly_order_rows = []
            if self.run_type == "daily":
                hourly_order_rows = orders_repository.fetch_hourly_aggregates(hourly_start, hourly_end, product_ids, brand.store_timezone)
            summary.order_rows = len(daily_order_rows) + len(hourly_order_rows)
            metrics.total_order_rows += summary.order_rows

            summary.stage = "Merging Datasets"
            daily_merged_rows = MergeService.merge_daily(daily_session_rows, daily_order_rows)
            hourly_merged_rows = []
            if self.run_type == "daily":
                hourly_merged_rows = MergeService.merge_hourly(hourly_session_rows, hourly_order_rows)
            summary.merged_rows = len(daily_merged_rows) + len(hourly_merged_rows)

            if self._should_write_dataset(brand.brand_name, "daily", daily_session_rows, daily_merged_rows):
                summary.stage = "Writing Daily Table"
                daily_deleted, daily_inserted = table_service.write_daily_rows(daily_start, daily_end, daily_merged_rows)
                summary.daily_rows_written = daily_inserted
                metrics.total_rows_deleted += daily_deleted
                metrics.total_rows_inserted += daily_inserted

            if self.run_type == "daily" and self._should_write_dataset(brand.brand_name, "hourly", hourly_session_rows, hourly_merged_rows):
                summary.stage = "Writing Hourly Table"
                hourly_deleted, hourly_inserted = table_service.write_hourly_rows(hourly_start, hourly_end, hourly_merged_rows)
                summary.hourly_rows_written = hourly_inserted
                metrics.total_rows_deleted += hourly_deleted
                metrics.total_rows_inserted += hourly_inserted

            summary.shopify_calls = request_manager.call_count
            summary.graphql_cost_consumed = request_manager.total_cost_consumed
            summary.retry_count = request_manager.total_retries
            metrics.total_shopify_calls += request_manager.call_count
            metrics.total_graphql_cost_consumed += request_manager.total_cost_consumed
            metrics.total_throttle_sleep_time += request_manager.total_sleep_seconds
        finally:
            db_client.close()

    def _daily_window(self) -> tuple[date, date]:
        if self.run_type == "retrospective":
            return (
                self.effective_end_date - timedelta(days=max(self.retrospective_days, 1) - 1),
                self.effective_end_date,
            )
        return self.effective_end_date, self.effective_end_date

    def _hourly_window(self) -> tuple[date, date]:
        return self.effective_end_date, self.effective_end_date

    @staticmethod
    def _build_landing_page_lookup(top_products: list[dict], brand_name: str) -> dict[str, int]:
        lookup: dict[str, int] = {}
        duplicate_paths = 0
        for row in top_products:
            path = row.get("landing_page_path")
            product_id = row.get("product_id")
            if not path or product_id is None:
                continue
            if path in lookup:
                duplicate_paths += 1
                continue
            lookup[path] = int(product_id)
        if duplicate_paths:
            logger.warning("[%s] Encountered %s duplicate landing page paths in top products.", brand_name, duplicate_paths)
        return lookup

    @staticmethod
    def _should_write_dataset(brand_name: str, granularity: str, session_rows: list[dict], merged_rows: list[dict]) -> bool:
        if not session_rows:
            logger.warning("[%s] Skipping %s write because Shopify session data is empty.", brand_name, granularity)
            return False
        if not merged_rows:
            logger.warning("[%s] Skipping %s write because merged replacement data is empty.", brand_name, granularity)
            return False
        return True

    @classmethod
    def _should_debug_brand(cls) -> bool:
        if cls._debug_brand_selected:
            return False
        cls._debug_brand_selected = True
        return True

    @staticmethod
    def _log_brand_checkpoint(summary: BrandRunSummary):
        if summary.status == "SUCCESS":
            logger.info(
                "[%s]\nRun Type: %s\nRun Date: %s\nTop Products: %s\nSession Rows: %s\nOrder Rows: %s\nMerged Rows: %s\nDaily Rows Written: %s\nHourly Rows Written: %s\nExecution Time: %ss\nStatus: SUCCESS",
                summary.brand_name,
                summary.run_type,
                summary.run_date,
                summary.top_products_count,
                summary.session_rows,
                summary.order_rows,
                summary.merged_rows,
                summary.daily_rows_written,
                summary.hourly_rows_written,
                summary.execution_time_seconds,
            )
            return

        logger.error(
            "[%s]\nRun Type: %s\nRun Date: %s\nStatus: FAILED\nStage: %s\nReason: %s\nRetry Count: %s\nExecution Time: %ss",
            summary.brand_name,
            summary.run_type,
            summary.run_date,
            summary.stage,
            summary.failure_reason,
            summary.retry_count,
            summary.execution_time_seconds,
        )

    @staticmethod
    def _log_worker_summary(metrics: WorkerRunMetrics):
        logger.info(
            "Run Type: %s | Brands Discovered: %s | Processed: %s | Succeeded: %s | Failed: %s | Session Rows: %s | Order Rows: %s | Rows Deleted: %s | Rows Inserted: %s | Shopify Calls: %s | GraphQL Cost: %s | Throttle Sleep: %.2fs | Execution Time: %.2fs",
            metrics.run_type.title(),
            metrics.brands_discovered,
            metrics.brands_processed,
            metrics.brands_succeeded,
            metrics.brands_failed,
            metrics.total_session_rows,
            metrics.total_order_rows,
            metrics.total_rows_deleted,
            metrics.total_rows_inserted,
            metrics.total_shopify_calls,
            metrics.total_graphql_cost_consumed,
            metrics.total_throttle_sleep_time,
            metrics.total_execution_time_seconds,
        )


def parse_effective_date(value: str | None) -> date:
    if not value:
        return datetime.utcnow().date()
    return date.fromisoformat(value)
