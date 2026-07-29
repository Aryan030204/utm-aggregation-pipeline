import unittest
from datetime import date

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

    def test_merge_normalizes_date_objects_from_order_rows(self):
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
                "date": date(2026, 7, 28),
                "product_id": 1,
                "utm_source": "google",
                "orders": 2,
                "sales": "40.00",
                "cod_orders": 0,
                "prepaid_orders": 2,
                "partially_prepaid_orders": 0,
                "cancelled_orders": 0,
                "refunded_orders": 0,
            }
        ]

        merged = MergeService.merge_daily(sessions, orders)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["date"], "2026-07-28")
        self.assertEqual(merged[0]["orders"], 2)

    def test_merge_normalizes_numeric_string_dimensions(self):
        sessions = [
            {
                "date": "2026-07-28",
                "hour": "7",
                "product_id": "101",
                "utm_source": "google",
                "sessions": 4,
                "atc_sessions": 1,
            }
        ]
        orders = [
            {
                "date": "2026-07-28",
                "hour": 7,
                "product_id": 101,
                "utm_source": "google",
                "orders": 1,
                "sales": "20.00",
                "cod_orders": 0,
                "prepaid_orders": 1,
                "partially_prepaid_orders": 0,
                "cancelled_orders": 0,
                "refunded_orders": 0,
            }
        ]

        merged = MergeService.merge_hourly(sessions, orders)

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["hour"], 7)
        self.assertEqual(merged[0]["product_id"], 101)
        self.assertEqual(merged[0]["orders"], 1)
