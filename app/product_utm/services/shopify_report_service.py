from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.product_utm.models import BrandContext
from app.product_utm.services.graphql_request_manager import GraphQLRequestManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ShopifyReportService:
    def __init__(self, brand: BrandContext, request_manager: GraphQLRequestManager):
        self.brand = brand
        self.request_manager = request_manager

    def fetch_daily_rows(self, start_date: date, end_date: date, landing_page_lookup: dict[str, int]) -> list[dict[str, Any]]:
        query = self._build_daily_shopifyql_query(start_date, end_date, sorted(landing_page_lookup))
        return self._normalize_rows(
            self.request_manager.execute_shopifyql(query),
            "daily",
            landing_page_lookup,
            default_date=end_date,
        )

    def fetch_hourly_rows(self, start_date: date, end_date: date, landing_page_lookup: dict[str, int]) -> list[dict[str, Any]]:
        query = self._build_hourly_shopifyql_query(start_date, end_date, sorted(landing_page_lookup))
        return self._normalize_rows(
            self.request_manager.execute_shopifyql(query),
            "hourly",
            landing_page_lookup,
            default_date=end_date,
        )

    def _build_daily_shopifyql_query(self, start_date: date, end_date: date, landing_page_paths: list[str]) -> str:
        path_clause = self._build_path_clause(landing_page_paths)
        if start_date == end_date:
            group_by = "landing_page_path, landing_page_type, utm_source"
        else:
            group_by = "day, landing_page_path, landing_page_type, utm_source"

        return (
            "FROM sessions "
            "SHOW sessions, sessions_with_cart_additions "
            "WHERE human_or_bot_session IN ('human','bot') "
            "AND landing_page_type = 'Product' "
            f"{path_clause} "
            f"GROUP BY {group_by} "
            f"SINCE {start_date.isoformat()} "
            f"UNTIL {end_date.isoformat()}"
        )

    def _build_hourly_shopifyql_query(self, start_date: date, end_date: date, landing_page_paths: list[str]) -> str:
        path_clause = self._build_path_clause(landing_page_paths)
        return (
            "FROM sessions "
            "SHOW sessions, sessions_with_cart_additions "
            "WHERE human_or_bot_session IN ('human','bot') "
            "AND landing_page_type = 'Product' "
            f"{path_clause} "
            "GROUP BY hour, landing_page_path, landing_page_type, utm_source "
            f"SINCE {start_date.isoformat()} "
            f"UNTIL {end_date.isoformat()}"
        )

    def _normalize_rows(
        self,
        result: dict[str, Any],
        granularity: str,
        landing_page_lookup: dict[str, int],
        default_date: date,
    ) -> list[dict[str, Any]]:
        table_data = result.get("tableData") or {}
        columns = [column["name"] for column in table_data.get("columns", [])]
        raw_rows = table_data.get("rows", []) or []
        if not raw_rows:
            logger.info("[%s] Shopify returned zero %s report rows.", self.brand.brand_name, granularity)
            return []

        normalized_rows: list[dict[str, Any]] = []
        skipped_rows = 0
        for raw_row in raw_rows:
            row = dict(zip(columns, raw_row))
            landing_page_path = row.get("landing_page_path")
            product_id = landing_page_lookup.get(landing_page_path)
            if product_id is None:
                skipped_rows += 1
                continue

            normalized = {
                "date": self._extract_date(row.get("day") or row.get("hour")) or default_date.isoformat(),
                "product_id": int(product_id),
                "utm_source": self._normalize_dimension(row.get("utm_source")),
                "sessions": int(float(row.get("sessions", 0) or 0)),
                "atc_sessions": int(float(row.get("sessions_with_cart_additions", 0) or 0)),
            }
            if granularity == "hourly":
                normalized["hour"] = self._extract_hour(row.get("hour"))
            normalized_rows.append(normalized)

        if skipped_rows:
            logger.info("[%s] Skipped %s unmapped Shopify report rows.", self.brand.brand_name, skipped_rows)
        return normalized_rows

    @staticmethod
    def _normalize_dimension(value: Any) -> str:
        if value is None:
            return "Unknown"
        text = str(value).strip()
        return text or "Unknown"

    @staticmethod
    def _extract_date(value: Any) -> str:
        if value is None:
            return ""
        text = str(value)
        if len(text) >= 10:
            return text[:10]
        return text

    @staticmethod
    def _extract_hour(value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, int):
            return value
        text = str(value).replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
            return parsed.hour
        except ValueError:
            return int(text.split("T", 1)[1][:2])

    @staticmethod
    def _build_path_clause(landing_page_paths: list[str]) -> str:
        escaped_paths = []
        for path in landing_page_paths:
            if not path:
                continue
            escaped_paths.append("'" + path.replace("\\", "\\\\").replace("'", "\\'") + "'")
        if not escaped_paths:
            return "AND landing_page_path IN ('')"
        return f"AND landing_page_path IN ({', '.join(escaped_paths)})"
