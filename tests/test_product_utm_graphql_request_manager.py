import unittest
from unittest.mock import patch

from app.product_utm.models import BrandContext, StageError
from app.product_utm.services.graphql_request_manager import GraphQLRequestManager


class GraphQLRequestManagerTests(unittest.TestCase):
    def test_sleeps_when_budget_low(self):
        brand = BrandContext("1", "Brand", "h", "u", "p", "d", 3306, "token", "shop.myshopify.com", "2025-10", "UTC")
        manager = GraphQLRequestManager(brand)
        payload = {
            "body": {
                "data": {"shopifyqlQuery": {"tableData": {"columns": [], "rows": []}, "parseErrors": []}},
                "extensions": {
                    "cost": {
                        "requestedQueryCost": 10,
                        "actualQueryCost": 8,
                        "throttleStatus": {
                            "currentlyAvailable": 10,
                            "restoreRate": 5,
                            "maximumAvailable": 1000,
                        },
                    }
                },
            },
            "headers": {},
        }
        with patch.object(manager, "_perform_request", return_value=payload), \
             patch("app.product_utm.services.graphql_request_manager.ProductUTMConfig.GRAPHQL_MIN_BALANCE", 20), \
             patch("app.product_utm.services.graphql_request_manager.ProductUTMConfig.GRAPHQL_SLEEP_BUFFER_SECONDS", 1), \
             patch("app.product_utm.services.graphql_request_manager.time.sleep") as mocked_sleep:
            manager.execute_shopifyql("FROM campaign_sessions SHOW campaign_sessions")

        mocked_sleep.assert_called_once()
        self.assertEqual(manager.total_cost_consumed, 8)

    def test_raises_after_retry_exhaustion(self):
        brand = BrandContext("1", "Brand", "h", "u", "p", "d", 3306, "token", "shop.myshopify.com", "2025-10", "UTC")
        manager = GraphQLRequestManager(brand)
        with patch.object(manager, "_perform_request", side_effect=StageError("Fetching Shopify Reports", "GraphQL Timeout")), \
             patch("app.product_utm.services.graphql_request_manager.ProductUTMConfig.GRAPHQL_MAX_RETRIES", 1), \
             patch("app.product_utm.services.graphql_request_manager.time.sleep"):
            with self.assertRaises(StageError):
                manager.execute_shopifyql("FROM campaign_sessions SHOW campaign_sessions")
