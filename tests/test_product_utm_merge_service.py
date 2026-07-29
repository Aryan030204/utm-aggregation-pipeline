import unittest

from app.product_utm.services.merge_service import MergeService


class MergeServiceTests(unittest.TestCase):
    def test_merge_daily_preserves_session_only_and_order_only_rows(self):
        sessions = [
            {
                "date": "2026-07-28",
                "product_id": 1,
                "utm_source": "google",
                "sessions": 10,
                "atc_sessions": 2,
            }
        ]
        orders = [
            {
                "date": "2026-07-28",
                "product_id": 2,
                "utm_source": "meta",
                "orders": 3,
                "sales": "99.90",
                "cod_orders": 1,
                "prepaid_orders": 1,
                "partially_prepaid_orders": 1,
                "cancelled_orders": 0,
                "refunded_orders": 0,
            }
        ]

        merged = MergeService.merge_daily(sessions, orders)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["sessions"], 10)
        self.assertEqual(merged[1]["orders"], 3)
        self.assertEqual(str(merged[1]["average_order_value"]), "33.30")
