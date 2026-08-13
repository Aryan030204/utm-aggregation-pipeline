import unittest
from datetime import date

from app.product_utm.repositories.orders_repository import OrdersRepository


class FakeDBClient:
    def __init__(self):
        self.query = None
        self.params = None

    def fetch_all(self, query, params):
        self.query = query
        self.params = params
        return []


class OrdersRepositoryTests(unittest.TestCase):
    def test_hourly_query_uses_sargable_local_window(self):
        client = FakeDBClient()
        repository = OrdersRepository(client)

        repository.fetch_hourly_aggregates(date(2026, 7, 27), date(2026, 7, 28), [1, 2, 3], "(GMT+05:30) Asia/Kolkata")

        self.assertIn("COALESCE(NULLIF(TRIM(utm_source), ''), 'direct') AS utm_source", client.query)
        self.assertIn("DATE(local_created_at) AS date", client.query)
        self.assertIn("created_at AS local_created_at", client.query)
        self.assertIn("so.created_at >= %s", client.query)
        self.assertIn("so.created_at < %s", client.query)
        self.assertIn("GROUP BY date, hour, product_id, utm_source", client.query)
        self.assertNotIn("CONVERT_TZ(created_at", client.query)
        self.assertNotIn("utm_medium", client.query)
        self.assertNotIn("utm_campaign", client.query)
        self.assertEqual(client.params, ("2026-07-27 00:00:00", "2026-07-29 00:00:00", 1, 2, 3))

    def test_daily_aggregates_are_derived_from_hourly_rows(self):
        repository = OrdersRepository(FakeDBClient())

        daily_rows = repository.derive_daily_aggregates(
            [
                {
                    "date": "2026-07-29",
                    "hour": 10,
                    "product_id": 101,
                    "utm_source": "google",
                    "orders": 2,
                    "sales": "30.00",
                    "cod_orders": 1,
                    "prepaid_orders": 1,
                    "partially_prepaid_orders": 0,
                    "cancelled_orders": 0,
                    "refunded_orders": 0,
                },
                {
                    "date": "2026-07-29",
                    "hour": 11,
                    "product_id": 101,
                    "utm_source": "google",
                    "orders": 1,
                    "sales": "15.00",
                    "cod_orders": 0,
                    "prepaid_orders": 1,
                    "partially_prepaid_orders": 0,
                    "cancelled_orders": 1,
                    "refunded_orders": 0,
                },
            ]
        )

        self.assertEqual(len(daily_rows), 1)
        self.assertEqual(daily_rows[0]["orders"], 3)
        self.assertEqual(str(daily_rows[0]["sales"]), "45.00")
        self.assertEqual(str(daily_rows[0]["average_order_value"]), "15.00")
        self.assertEqual(daily_rows[0]["cancelled_orders"], 1)
