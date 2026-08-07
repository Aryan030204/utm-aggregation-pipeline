from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Callable

from app.product_utm.config import ProductUTMConfig
from app.product_utm.models import BrandContext, StageError
from app.product_utm.services.graphql_request_manager import GraphQLRequestManager
from app.services.payment_classifier import classify_payment_type
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ShopifyOrdersFetcher:
    """Fetches order-level UTM/sales rows from Shopify via ShopifyQL, paginated with
    LIMIT/OFFSET. Rows are grouped by order_id (in addition to the UTM dimensions and
    payment_gateway_names) so each row stays joinable against returns_fact by order_id
    before being collapsed into the final UTM-dimension buckets in UtmMergeService."""

    def __init__(self, brand: BrandContext, request_manager: GraphQLRequestManager):
        self.brand = brand
        self.request_manager = request_manager

    def fetch_daily_rows(self, metric_date: str) -> list[dict[str, Any]]:
        return self._fetch_all_pages(
            lambda page_size, offset: self._build_query(metric_date, hourly=False, page_size=page_size, offset=offset)
        )

    def fetch_hourly_rows(self, metric_date: str) -> list[dict[str, Any]]:
        return self._fetch_all_pages(
            lambda page_size, offset: self._build_query(metric_date, hourly=True, page_size=page_size, offset=offset)
        )

    def _fetch_all_pages(self, build_query: Callable[[int, int], str]) -> list[dict[str, Any]]:
        page_size = ProductUTMConfig.SHOPIFYQL_ORDERS_PAGE_SIZE
        max_pages = ProductUTMConfig.SHOPIFYQL_ORDERS_MAX_PAGES
        rows: list[dict[str, Any]] = []

        for page in range(max_pages):
            offset = page * page_size
            query = build_query(page_size, offset)
            page_rows = self._fetch_page_with_retry(query)
            rows.extend(page_rows)
            if len(page_rows) < page_size:
                return rows

        raise StageError(
            "Fetching Shopify Orders",
            f"[{self.brand.brand_name}] Exceeded max page ceiling ({max_pages}) "
            "without reaching the end of the orders dataset.",
        )

    def _fetch_page_with_retry(self, query: str) -> list[dict[str, Any]]:
        last_exc: Exception | None = None
        max_retries = ProductUTMConfig.SHOPIFYQL_PAGE_FETCH_MAX_RETRIES
        for attempt in range(1, max_retries + 1):
            try:
                result = self.request_manager.execute_shopifyql(query)
                return self._normalize_rows(result)
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    sleep_seconds = ProductUTMConfig.SHOPIFYQL_PAGE_FETCH_BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        "[%s] Orders page fetch attempt %s/%s failed: %s. Retrying in %ss...",
                        self.brand.brand_name, attempt, max_retries, exc, sleep_seconds,
                    )
                    time.sleep(sleep_seconds)

        raise StageError(
            "Fetching Shopify Orders",
            f"[{self.brand.brand_name}] Exhausted {max_retries} page-fetch retries.",
            original_exception=last_exc,
        )

    @staticmethod
    def _build_query(metric_date: str, hourly: bool, page_size: int, offset: int) -> str:
        group_dims = (["hour"] if hourly else []) + [
            "order_id", "utm_source", "utm_medium", "utm_campaign", "payment_gateway_names",
        ]
        group_by = ", ".join(group_dims)
        return (
            "FROM sales "
            "SHOW orders, total_sales "
            f"GROUP BY {group_by} "
            f"SINCE {metric_date} UNTIL {metric_date} "
            f"ORDER BY {group_by} "
            f"LIMIT {page_size} OFFSET {offset}"
        )

    def _normalize_rows(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        table_data = result.get("tableData") or {}
        columns = [column["name"] for column in table_data.get("columns", [])]
        raw_rows = table_data.get("rows", []) or []

        normalized: list[dict[str, Any]] = []
        for raw_row in raw_rows:
            row = self._coerce_row_to_dict(columns, raw_row)
            normalized.append({
                "order_id": row.get("order_id"),
                "hour": self._extract_hour(row.get("hour")) if "hour" in row else None,
                "utm_source": self._normalize_dimension(row.get("utm_source")),
                "utm_medium": self._normalize_dimension(row.get("utm_medium")),
                "utm_campaign": self._normalize_dimension(row.get("utm_campaign")),
                "payment_type": classify_payment_type(row.get("payment_gateway_names")),
                "sales": float(row.get("total_sales", 0) or 0),
            })
        return normalized

    @staticmethod
    def _normalize_dimension(value: Any) -> str:
        if value is None:
            return "Unknown"
        text = str(value).strip()
        return text if text else "Unknown"

    @staticmethod
    def _extract_hour(value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, int):
            return value
        text = str(value).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text).hour
        except ValueError:
            return int(text.split("T", 1)[1][:2])

    @staticmethod
    def _coerce_row_to_dict(columns: list[str], raw_row: Any) -> dict[str, Any]:
        if isinstance(raw_row, dict):
            if "values" in raw_row and isinstance(raw_row["values"], list):
                return ShopifyOrdersFetcher._coerce_row_to_dict(columns, raw_row["values"])
            if "cells" in raw_row and isinstance(raw_row["cells"], list):
                return ShopifyOrdersFetcher._coerce_row_to_dict(columns, raw_row["cells"])
            return raw_row

        if isinstance(raw_row, (list, tuple)):
            extracted_values = [ShopifyOrdersFetcher._extract_cell_value(cell) for cell in raw_row]
            return dict(zip(columns, extracted_values))

        return {columns[0]: ShopifyOrdersFetcher._extract_cell_value(raw_row)} if columns else {}

    @staticmethod
    def _extract_cell_value(cell: Any) -> Any:
        if isinstance(cell, dict):
            for key in ("value", "rawValue", "displayValue", "text"):
                if key in cell:
                    return cell[key]
        return cell
