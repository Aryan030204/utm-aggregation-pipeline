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
    def test_daily_query_groups_only_by_utm_source(self):
        client = FakeDBClient()
        repository = OrdersRepository(client)

        repository.fetch_daily_aggregates(date(2026, 7, 27), date(2026, 7, 28), [1, 2, 3], "Asia/Kolkata")

        self.assertIn("COALESCE(NULLIF(TRIM(utm_source), ''), 'Unknown') AS utm_source", client.query)
        self.assertIn("DATE(local_created_at) AS date", client.query)
        self.assertIn("CONVERT_TZ(created_at, '+00:00', %s)", client.query)
        self.assertIn("GROUP BY date, product_id, utm_source", client.query)
        self.assertNotIn("utm_medium", client.query)
        self.assertNotIn("utm_campaign", client.query)
        self.assertEqual(client.params, ("Asia/Kolkata", "Asia/Kolkata", "2026-07-27", "2026-07-28", 1, 2, 3))
