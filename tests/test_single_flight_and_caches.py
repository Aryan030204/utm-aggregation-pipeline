import threading
import time
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from app import main
from app.models.events import EtlTriggerEvent
from app.product_utm.models import BrandContext
from app.product_utm.services.brand_service import BrandService
from app.product_utm.services.worker_service import ProductUTMWorkerService
from app.services.aggregate_runner import RunLockNotAcquired
from app.services.brand_fetcher import BrandFetcher
from app.utils import dates
from app.utils.ttl_cache import TTLCache


def make_event(job_id):
    return EtlTriggerEvent(eventType="ETL_COMPLETED", jobId=job_id, completedAt="2026-09-20T00:00:00")


class SingleFlightTests(unittest.TestCase):
    def setUp(self):
        main._running = False
        main._pending = False

    def test_overlapping_triggers_coalesce_into_one_followup_run(self):
        started, release, runs = threading.Event(), threading.Event(), []

        def fake_execute(event, is_manual, run_id):
            runs.append(event.jobId)
            if len(runs) == 1:
                started.set()
                release.wait(5)

        with patch.object(main, "_execute_pipeline_run", side_effect=fake_execute):
            worker = threading.Thread(target=main.run_pipeline_task, args=(make_event("a"),))
            worker.start()
            self.assertTrue(started.wait(5))
            main.run_pipeline_task(make_event("b"))   # returns immediately, coalesced
            main.run_pipeline_task(make_event("c"))   # coalesced into the same follow-up
            release.set()
            worker.join(5)

        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0], "a")
        self.assertTrue(runs[1].startswith("coalesced_"))
        self.assertFalse(main._running)

    def test_manual_run_waits_for_the_active_run_instead_of_being_dropped(self):
        started, release, runs = threading.Event(), threading.Event(), []

        def fake_execute(event, is_manual, run_id):
            runs.append((event.jobId, is_manual, run_id))
            if len(runs) == 1:
                started.set()
                release.wait(5)

        with patch.object(main, "_execute_pipeline_run", side_effect=fake_execute):
            first = threading.Thread(target=main.run_pipeline_task, args=(make_event("a"),))
            first.start()
            self.assertTrue(started.wait(5))
            manual = threading.Thread(target=main.run_pipeline_task, args=(make_event("m"), True, "run-1"))
            manual.start()
            time.sleep(0.1)
            release.set()
            first.join(5)
            manual.join(5)

        self.assertIn(("m", True, "run-1"), runs)
        self.assertFalse(main._running)

    def test_run_state_is_released_after_a_normal_run(self):
        with patch.object(main, "_execute_pipeline_run") as execute:
            main.run_pipeline_task(make_event("a"))
            main.run_pipeline_task(make_event("b"))
        self.assertEqual(execute.call_count, 2)


class PipelineRunPolicyTests(unittest.TestCase):
    """_execute_pipeline_run wires the yesterday policy and the per-brand lock together."""

    def setUp(self):
        dates._last_rebuilt_at.clear()
        patcher = patch.multiple("app.utils.dates.Config", PRIOR_DAY_REBUILD_INTERVAL_SECONDS=3600, BACKFILL_MODE=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_once(self, on_run=None):
        seen = []

        class FakeRunner:
            def __init__(self, brand, target_dates, *args, **kwargs):
                seen.append(list(target_dates))

            def initialize(self):
                pass

            def run_aggregations(self):
                if on_run:
                    on_run()

        with patch.object(main, "AggregateRunner", FakeRunner), \
             patch.object(main.BrandFetcher, "get_all_brands", return_value=[{"brand_name": "B"}]):
            main._execute_pipeline_run(make_event("x"))   # completedAt 2026-09-20, recomputeDays 2
        return seen

    def test_second_trigger_rebuilds_only_the_latest_date(self):
        self.assertEqual(self.run_once(), [["2026-09-19", "2026-09-20"]])
        self.assertEqual(self.run_once(), [["2026-09-20"]])

    def test_a_skipped_brand_does_not_mark_the_earlier_date_as_rebuilt(self):
        def busy():
            raise RunLockNotAcquired("busy")

        self.run_once(on_run=busy)
        self.assertEqual(self.run_once(), [["2026-09-19", "2026-09-20"]])

    def test_a_failed_brand_does_not_mark_the_earlier_date_as_rebuilt(self):
        def boom():
            raise RuntimeError("db down")

        self.run_once(on_run=boom)
        self.assertEqual(self.run_once(), [["2026-09-19", "2026-09-20"]])


class BrandCacheTests(unittest.TestCase):
    def test_brand_fetcher_caches_non_empty_results_and_invalidates(self):
        brands = [{"brand_id": "1", "brand_name": "A"}]
        with patch.object(BrandFetcher, "_cache", TTLCache(60)), \
             patch("app.services.brand_fetcher.Config.TEST_MODE", False), \
             patch("app.services.brand_fetcher.Config.BACKFILL_MODE", False), \
             patch.object(BrandFetcher, "_get_brands_from_api", return_value=brands) as fetch:
            BrandFetcher.get_all_brands()
            BrandFetcher.get_all_brands()
            self.assertEqual(fetch.call_count, 1)
            BrandFetcher.invalidate_cache()
            BrandFetcher.get_all_brands()
            self.assertEqual(fetch.call_count, 2)

    def test_brand_fetcher_never_caches_an_empty_result(self):
        with patch.object(BrandFetcher, "_cache", TTLCache(60)), \
             patch("app.services.brand_fetcher.Config.TEST_MODE", False), \
             patch("app.services.brand_fetcher.Config.BACKFILL_MODE", False), \
             patch.object(BrandFetcher, "_get_brands_from_api", return_value=[]) as fetch:
            BrandFetcher.get_all_brands()
            BrandFetcher.get_all_brands()
            self.assertEqual(fetch.call_count, 2)

    def test_backfill_filter_still_applies_to_cached_brands(self):
        brands = [{"brand_id": "1", "brand_name": "A"}, {"brand_id": "2", "brand_name": "B"}]
        with patch.object(BrandFetcher, "_cache", TTLCache(60)), \
             patch("app.services.brand_fetcher.Config.TEST_MODE", False), \
             patch.object(BrandFetcher, "_get_brands_from_api", return_value=brands):
            with patch("app.services.brand_fetcher.Config.BACKFILL_MODE", False):
                self.assertEqual(len(BrandFetcher.get_all_brands()), 2)
            with patch("app.services.brand_fetcher.Config.BACKFILL_MODE", True), \
                 patch("app.services.brand_fetcher.Config.BACKFILL_BRAND_INDICES", "2"):
                self.assertEqual(BrandFetcher.get_all_brands(), [brands[1]])

    def test_brand_service_caches_and_invalidates(self):
        brand = BrandContext("1", "A", "h", "u", "p", "d", 3306, "tok", "shop", "2025-10", "UTC")
        with patch.object(BrandService, "_cache", TTLCache(60)), \
             patch.object(BrandService, "_fetch_active_brands", return_value=[brand]) as fetch:
            self.assertEqual(BrandService.get_active_brands(), [brand])
            BrandService.get_active_brands()
            self.assertEqual(fetch.call_count, 1)
            BrandService.invalidate_cache()
            BrandService.get_active_brands()
            self.assertEqual(fetch.call_count, 2)


class TopProductsCacheTests(unittest.TestCase):
    BRAND = BrandContext("1", "A", "h", "u", "p", "db1", 3306, "tok", "shop", "2025-10", "UTC")

    def test_top_products_are_fetched_once_per_brand_and_date(self):
        repo = MagicMock()
        repo.fetch_top_products.return_value = [{"product_id": 1, "landing_page_path": "/p/1"}]
        service = ProductUTMWorkerService("daily", date(2026, 9, 20))

        with patch.object(ProductUTMWorkerService, "_top_products_cache", TTLCache(60)):
            self.assertEqual(service._get_top_products(self.BRAND, repo), repo.fetch_top_products.return_value)
            service._get_top_products(self.BRAND, repo)
            self.assertEqual(repo.fetch_top_products.call_count, 1)

            ProductUTMWorkerService("daily", date(2026, 9, 21))._get_top_products(self.BRAND, repo)
            self.assertEqual(repo.fetch_top_products.call_count, 2)

    def test_empty_top_products_are_not_cached(self):
        repo = MagicMock()
        repo.fetch_top_products.return_value = []
        service = ProductUTMWorkerService("daily", date(2026, 9, 20))

        with patch.object(ProductUTMWorkerService, "_top_products_cache", TTLCache(60)):
            service._get_top_products(self.BRAND, repo)
            service._get_top_products(self.BRAND, repo)
            self.assertEqual(repo.fetch_top_products.call_count, 2)


if __name__ == "__main__":
    unittest.main()
