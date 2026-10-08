import unittest
from datetime import date
from unittest.mock import patch

from app.product_utm.models import BrandContext
from app.product_utm.services.worker_service import ProductUTMWorkerService


class WorkerServiceTests(unittest.TestCase):
    def setUp(self):
        ProductUTMWorkerService.reset_caches()

    def test_should_write_dataset_skips_empty_replacements(self):
        self.assertFalse(ProductUTMWorkerService._should_write_dataset("Brand", "daily", [], [{"x": 1}]))
        self.assertFalse(ProductUTMWorkerService._should_write_dataset("Brand", "daily", [{"x": 1}], []))
        self.assertTrue(ProductUTMWorkerService._should_write_dataset("Brand", "daily", [{"x": 1}], [{"x": 1}]))

    def test_run_skips_writes_when_top_products_are_empty(self):
        brand = BrandContext("1", "Brand", "h", "u", "p", "d", 3306, "token", "shop.myshopify.com", "2025-10", "UTC")
        table_service_instance = type("TableSvc", (), {"ensure_tables_exist": lambda self: None, "write_daily_rows": lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not write")), "write_hourly_rows": lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not write"))})()
        with patch("app.product_utm.services.worker_service.BrandService.get_active_brands", return_value=[brand]), \
             patch("app.product_utm.services.worker_service.ProductRepository") as product_repo_cls, \
             patch("app.product_utm.services.worker_service.OrdersRepository"), \
             patch("app.product_utm.services.worker_service.ShopifyReportService"), \
             patch("app.product_utm.services.worker_service.TableService", return_value=table_service_instance), \
             patch("app.product_utm.services.worker_service.GraphQLRequestManager"):
            product_repo_cls.return_value.fetch_top_products.return_value = []
            metrics = ProductUTMWorkerService("daily", date(2026, 7, 29)).run()

        self.assertEqual(metrics.brands_succeeded, 1)
        self.assertEqual(metrics.total_rows_deleted, 0)
        self.assertEqual(metrics.total_rows_inserted, 0)
