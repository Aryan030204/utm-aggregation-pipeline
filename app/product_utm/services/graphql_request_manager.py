from __future__ import annotations

import time
from typing import Any

import requests

from app.product_utm.config import ProductUTMConfig
from app.product_utm.models import BrandContext, StageError
from app.utils.logger import get_logger

logger = get_logger(__name__)

GRAPHQL_WRAPPER_QUERY = """
query RunShopifyQL($query: String!) {
  shopifyqlQuery(query: $query) {
    tableData {
      columns {
        name
        dataType
        displayName
      }
      rows
    }
    parseErrors
  }
}
"""


class GraphQLRequestManager:
    def __init__(self, brand: BrandContext):
        self.brand = brand
        self.call_count = 0
        self.total_cost_consumed = 0
        self.total_sleep_seconds = 0.0
        self.total_retries = 0

    def execute_shopifyql(self, shopifyql_query: str) -> dict[str, Any]:
        retry_count = 0
        while True:
            try:
                result = self._perform_request(shopifyql_query)
                cost_info = self._extract_cost_info(result)
                self._log_cost(cost_info)
                self.total_cost_consumed += cost_info["actual_cost"]
                self._sleep_if_needed(cost_info)

                body = result["body"]
                errors = body.get("errors") or []
                if errors and self._is_throttled(errors):
                    raise StageError("Fetching Shopify Reports", "GraphQL throttled", retry_count=retry_count)

                data = body.get("data", {}).get("shopifyqlQuery")
                if data is None:
                    raise StageError("Fetching Shopify Reports", "Missing shopifyqlQuery response", retry_count=retry_count)
                if data.get("parseErrors"):
                    raise StageError(
                        "Fetching Shopify Reports",
                        f"ShopifyQL parse errors: {', '.join(data['parseErrors'])}",
                        retry_count=retry_count,
                        retryable=False,
                    )
                return data
            except StageError as exc:
                # A malformed query fails identically every time; retrying only burns API cost.
                if not exc.retryable or retry_count >= ProductUTMConfig.GRAPHQL_MAX_RETRIES:
                    raise
                retry_count += 1
                self.total_retries += 1
                sleep_seconds = ProductUTMConfig.GRAPHQL_BASE_BACKOFF_SECONDS * (2 ** (retry_count - 1))
                logger.warning("[%s] GraphQL retry %s after %ss: %s", self.brand.brand_name, retry_count, sleep_seconds, exc.reason)
                time.sleep(sleep_seconds)
                self.total_sleep_seconds += sleep_seconds
            except requests.RequestException as exc:
                if retry_count >= ProductUTMConfig.GRAPHQL_MAX_RETRIES:
                    raise StageError("Fetching Shopify Reports", str(exc), retry_count=retry_count, original_exception=exc)
                retry_count += 1
                self.total_retries += 1
                sleep_seconds = ProductUTMConfig.GRAPHQL_BASE_BACKOFF_SECONDS * (2 ** (retry_count - 1))
                logger.warning("[%s] Request retry %s after %ss: %s", self.brand.brand_name, retry_count, sleep_seconds, exc)
                time.sleep(sleep_seconds)
                self.total_sleep_seconds += sleep_seconds

    def _perform_request(self, shopifyql_query: str) -> dict[str, Any]:
        response = requests.post(
            f"https://{self.brand.shop_name}.myshopify.com/admin/api/{self.brand.api_version}/graphql.json",
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": self.brand.access_token,
            },
            json={
                "query": GRAPHQL_WRAPPER_QUERY,
                "variables": {"query": shopifyql_query},
            },
            timeout=60,
        )
        self.call_count += 1
        if response.status_code == 429:
            raise StageError("Fetching Shopify Reports", "GraphQL Timeout", retry_count=self.total_retries)
        response.raise_for_status()
        return {"body": response.json(), "headers": response.headers}

    def _extract_cost_info(self, result: dict[str, Any]) -> dict[str, Any]:
        extensions = result["body"].get("extensions", {})
        cost = extensions.get("cost", {})
        throttle_status = cost.get("throttleStatus", {}) or {}
        return {
            "requested_cost": int(cost.get("requestedQueryCost", 0) or 0),
            "actual_cost": int(cost.get("actualQueryCost", 0) or 0),
            "currently_available": int(throttle_status.get("currentlyAvailable", 0) or 0),
            "restore_rate": int(throttle_status.get("restoreRate", 0) or 0),
            "maximum_available": int(throttle_status.get("maximumAvailable", 0) or 0),
        }

    def _sleep_if_needed(self, cost_info: dict[str, Any]):
        remaining = cost_info["currently_available"]
        restore_rate = max(cost_info["restore_rate"], 1)
        if remaining >= ProductUTMConfig.GRAPHQL_MIN_BALANCE:
            return

        deficit = ProductUTMConfig.GRAPHQL_MIN_BALANCE - remaining
        sleep_seconds = (deficit / restore_rate) + ProductUTMConfig.GRAPHQL_SLEEP_BUFFER_SECONDS
        logger.info(
            "[%s] GraphQL low budget. requested=%s actual=%s remaining=%s restore_rate=%s sleeping=%ss",
            self.brand.brand_name,
            cost_info["requested_cost"],
            cost_info["actual_cost"],
            remaining,
            restore_rate,
            round(sleep_seconds, 2),
        )
        time.sleep(sleep_seconds)
        self.total_sleep_seconds += sleep_seconds

    def _log_cost(self, cost_info: dict[str, Any]):
        logger.info(
            "[%s] GraphQL cost requested=%s actual=%s remaining=%s restore_rate=%s max=%s",
            self.brand.brand_name,
            cost_info["requested_cost"],
            cost_info["actual_cost"],
            cost_info["currently_available"],
            cost_info["restore_rate"],
            cost_info["maximum_available"],
        )

    @staticmethod
    def _is_throttled(errors: list[dict[str, Any]]) -> bool:
        return any("THROTTLED" in str(error) for error in errors)
