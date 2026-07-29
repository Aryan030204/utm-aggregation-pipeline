import unittest
from datetime import date

from app.product_utm.models import StageError
from app.product_utm.services.table_service import TableService


class FakeDBClient:
    def __init__(self, fail_insert=False):
        self.fail_insert = fail_insert
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append(("execute", query.strip(), params))
        return 5

    def execute_many(self, query, rows):
        self.calls.append(("execute_many", query.strip(), rows))
        if self.fail_insert:
            raise RuntimeError("insert failed")
        return len(list(rows))

    def begin(self):
        self.calls.append(("begin",))

    def commit(self):
        self.calls.append(("commit",))

    def rollback(self):
        self.calls.append(("rollback",))


class TableServiceTests(unittest.TestCase):
    def test_write_daily_rows_commits_transaction(self):
        client = FakeDBClient()
        service = TableService(client, "Brand")
        deleted, inserted = service.write_daily_rows(
            date(2026, 7, 28),
            date(2026, 7, 28),
            [{
                "date": "2026-07-28",
                "product_id": 1,
                "utm_source": "google",
                "sessions": 1,
                "atc_sessions": 1,
                "orders": 1,
                "sales": 10,
                "average_order_value": 10,
                "cod_orders": 0,
                "prepaid_orders": 1,
                "partially_prepaid_orders": 0,
                "cancelled_orders": 0,
                "refunded_orders": 0,
            }],
        )
        self.assertEqual((deleted, inserted), (5, 1))
        self.assertIn(("commit",), client.calls)

    def test_write_daily_rows_rolls_back_on_failure(self):
        client = FakeDBClient(fail_insert=True)
        service = TableService(client, "Brand")
        with self.assertRaises(StageError):
            service.write_daily_rows(date(2026, 7, 28), date(2026, 7, 28), [{"date": "2026-07-28", "product_id": 1, "utm_source": "s", "sessions": 1, "atc_sessions": 1, "orders": 1, "sales": 1, "average_order_value": 1, "cod_orders": 0, "prepaid_orders": 0, "partially_prepaid_orders": 0, "cancelled_orders": 0, "refunded_orders": 0}])
        self.assertIn(("rollback",), client.calls)
