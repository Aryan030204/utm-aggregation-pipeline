from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.product_utm.models import BrandContext
from app.product_utm.services.graphql_request_manager import GraphQLRequestManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ShopifyReportService:
    def __init__(self, brand: BrandContext, request_manager: GraphQLRequestManager, debug_mapping: bool = False):
        self.brand = brand
        self.request_manager = request_manager
        self.debug_mapping = debug_mapping

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
        seen_shopify_paths: list[str] = []
        mapped_paths: set[str] = set()
        lookup_events: list[tuple[str, str, bool]] = []
        for raw_row in raw_rows:
            row = dict(zip(columns, raw_row))
            landing_page_path = row.get("landing_page_path")
            normalized_key = self._normalize_for_diagnostics(landing_page_path)
            if isinstance(landing_page_path, str) and len(seen_shopify_paths) < 50:
                seen_shopify_paths.append(landing_page_path)
            product_id = landing_page_lookup.get(landing_page_path)
            if self.debug_mapping and len(lookup_events) < 50:
                lookup_events.append((str(landing_page_path), normalized_key, product_id is not None))
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
            if isinstance(landing_page_path, str):
                mapped_paths.add(landing_page_path)

        if skipped_rows:
            logger.info("[%s] Skipped %s unmapped Shopify report rows.", self.brand.brand_name, skipped_rows)
        if self.debug_mapping:
            self._log_mapping_diagnostics(
                granularity=granularity,
                raw_rows=raw_rows,
                landing_page_lookup=landing_page_lookup,
                seen_shopify_paths=seen_shopify_paths,
                lookup_events=lookup_events,
                normalized_rows=normalized_rows,
                mapped_paths=mapped_paths,
            )
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

    @staticmethod
    def _normalize_for_diagnostics(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if "://" in text:
            text = text.split("://", 1)[1]
            if "/" in text:
                text = "/" + text.split("/", 1)[1]
            else:
                text = "/"
        if "?" in text:
            text = text.split("?", 1)[0]
        if "#" in text:
            text = text.split("#", 1)[0]
        text = text.replace("%2F", "/").replace("%2f", "/")
        if text != "/" and text.endswith("/"):
            text = text.rstrip("/")
        return text.lower()

    def _log_mapping_diagnostics(
        self,
        granularity: str,
        raw_rows: list[Any],
        landing_page_lookup: dict[str, int],
        seen_shopify_paths: list[str],
        lookup_events: list[tuple[str, str, bool]],
        normalized_rows: list[dict[str, Any]],
        mapped_paths: set[str],
    ) -> None:
        logger.info("[%s] %s debug top-product map: %s", self.brand.brand_name, granularity, list(landing_page_lookup.items())[:10])
        logger.info("[%s] %s first Shopify landing_page_path values: %s", self.brand.brand_name, granularity, seen_shopify_paths[:50])
        for raw_value, normalized_key, is_hit in lookup_events:
            logger.info(
                "[%s] %s lookup raw=%s normalized=%s result=%s",
                self.brand.brand_name,
                granularity,
                raw_value,
                normalized_key,
                "HIT" if is_hit else "MISS",
            )

        unique_shopify_paths = {str(path) for path in seen_shopify_paths if path}
        logger.info(
            "[%s] %s mapping summary total_shopify_rows=%s total_mapped_rows=%s total_unmapped_rows=%s unique_shopify_paths=%s unique_mapped_paths=%s",
            self.brand.brand_name,
            granularity,
            len(raw_rows),
            len(normalized_rows),
            len(raw_rows) - len(normalized_rows),
            len(unique_shopify_paths),
            len(mapped_paths),
        )

        if lookup_events and all(not is_hit for _, _, is_hit in lookup_events):
            db_paths = list(landing_page_lookup.keys())
            normalized_db = {self._normalize_for_diagnostics(path): path for path in db_paths}
            normalized_shopify = {self._normalize_for_diagnostics(path): path for path in unique_shopify_paths}
            overlap = sorted(set(normalized_db).intersection(normalized_shopify))
            examples: list[str] = []
            for shopify_path in list(unique_shopify_paths)[:10]:
                normalized = self._normalize_for_diagnostics(shopify_path)
                mismatch_types: list[str] = []
                if "://" in shopify_path:
                    mismatch_types.append("full URL vs path")
                if "?" in shopify_path:
                    mismatch_types.append("query parameters")
                if "#" in shopify_path:
                    mismatch_types.append("fragment")
                if shopify_path != "/" and shopify_path.endswith("/"):
                    mismatch_types.append("trailing slash")
                if shopify_path != shopify_path.lower():
                    mismatch_types.append("case difference")
                if "%" in shopify_path:
                    mismatch_types.append("URL encoding")
                matching_db = normalized_db.get(normalized)
                if matching_db and shopify_path != matching_db:
                    if "://" not in shopify_path and "full URL vs path" not in mismatch_types:
                        mismatch_types.append("format difference after normalization")
                examples.append(f"shopify={shopify_path} normalized={normalized} db_match={matching_db} mismatches={', '.join(mismatch_types) or 'none'}")

            logger.warning(
                "[%s] %s all sampled lookups missed. normalized_overlap_count=%s sample_diagnostics=%s",
                self.brand.brand_name,
                granularity,
                len(overlap),
                examples,
            )
