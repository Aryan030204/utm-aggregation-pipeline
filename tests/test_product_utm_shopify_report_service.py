import unittest

from app.product_utm.models import BrandContext
from app.product_utm.services.shopify_report_service import ShopifyReportService


class DummyRequestManager:
    def __init__(self, payload):
        self.payload = payload
        self.last_query = None

    def execute_shopifyql(self, shopifyql_query):
        self.last_query = shopifyql_query
        return self.payload


class ShopifyReportServiceTests(unittest.TestCase):
    def test_zero_rows_returns_successful_empty_list(self):
        brand = BrandContext("1", "Brand", "h", "u", "p", "d", 3306, "token", "shop.myshopify.com", "2025-10", "UTC")
        service = ShopifyReportService(
            brand=brand,
            request_manager=DummyRequestManager({"tableData": {"columns": [], "rows": []}, "parseErrors": []}),
        )
        rows = service.fetch_daily_rows(__import__("datetime").date(2026, 7, 28), __import__("datetime").date(2026, 7, 28), {})
        self.assertEqual(rows, [])

    def test_unmapped_rows_are_skipped(self):
        brand = BrandContext("1", "Brand", "h", "u", "p", "d", 3306, "token", "shop.myshopify.com", "2025-10", "UTC")
        payload = {
            "tableData": {
                "columns": [
                    {"name": "landing_page_path"},
                    {"name": "landing_page_type"},
                    {"name": "utm_source"},
                    {"name": "sessions"},
                    {"name": "sessions_with_cart_additions"},
                ],
                "rows": [
                    ["/products/a", "Product", "google", 5, 1],
                    ["/products/b", "Product", "meta", 7, 2],
                ],
            },
            "parseErrors": [],
        }
        service = ShopifyReportService(brand=brand, request_manager=DummyRequestManager(payload))
        rows = service.fetch_daily_rows(__import__("datetime").date(2026, 7, 28), __import__("datetime").date(2026, 7, 28), {"/products/a": 99})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["product_id"], 99)
        self.assertEqual(rows[0]["utm_source"], "google")
        self.assertNotIn("utm_medium", rows[0])
        self.assertNotIn("utm_campaign", rows[0])

    def test_queries_are_target_date_scoped_and_landing_page_scoped(self):
        brand = BrandContext("1", "Brand", "h", "u", "p", "d", 3306, "token", "shop.myshopify.com", "2025-10", "UTC")
        request_manager = DummyRequestManager({"tableData": {"columns": [], "rows": []}, "parseErrors": []})
        service = ShopifyReportService(brand=brand, request_manager=request_manager)

        service.fetch_daily_rows(
            __import__("datetime").date(2026, 7, 27),
            __import__("datetime").date(2026, 7, 28),
            {"/products/a": 1, "/products/b": 2},
        )

        self.assertIn("SINCE '2026-07-27'", request_manager.last_query)
        self.assertIn("UNTIL '2026-07-28'", request_manager.last_query)
        self.assertIn("landing_page_path IN ('/products/a', '/products/b')", request_manager.last_query)
        self.assertNotIn("LIMIT 1000", request_manager.last_query)
