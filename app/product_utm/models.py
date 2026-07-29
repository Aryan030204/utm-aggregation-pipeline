from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BrandContext:
    brand_id: str
    brand_name: str
    host: str
    user: str
    password: str
    database: str
    port: int
    access_token: str
    shop_name: str
    api_version: str
    store_timezone: str


@dataclass
class BrandRunSummary:
    brand_name: str
    run_type: str
    run_date: str
    top_products_count: int = 0
    session_rows: int = 0
    order_rows: int = 0
    merged_rows: int = 0
    daily_rows_written: int = 0
    hourly_rows_written: int = 0
    shopify_calls: int = 0
    graphql_cost_consumed: int = 0
    retry_count: int = 0
    stage: str = "Initializing"
    status: str = "SUCCESS"
    failure_reason: str = ""
    execution_time_seconds: float = 0.0


@dataclass
class WorkerRunMetrics:
    run_type: str
    brands_discovered: int = 0
    brands_processed: int = 0
    brands_succeeded: int = 0
    brands_failed: int = 0
    total_session_rows: int = 0
    total_order_rows: int = 0
    total_rows_deleted: int = 0
    total_rows_inserted: int = 0
    total_shopify_calls: int = 0
    total_graphql_cost_consumed: int = 0
    total_throttle_sleep_time: float = 0.0
    total_execution_time_seconds: float = 0.0


@dataclass
class StageError(Exception):
    stage: str
    reason: str
    retry_count: int = 0
    original_exception: Optional[Exception] = None

    def __str__(self) -> str:
        return f"{self.stage}: {self.reason}"

