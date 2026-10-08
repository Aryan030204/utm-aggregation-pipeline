import unittest
from unittest.mock import patch

from app.utils import dates
from app.utils.dates import mark_dates_rebuilt, select_dates_to_rebuild
from app.utils.retry import is_transient_db_error, retry_db_operation
from app.utils.ttl_cache import TTLCache


class FakeMySQLError(Exception):
    def __init__(self, errno, msg="boom"):
        super().__init__(msg)
        self.errno = errno


class RetryTests(unittest.TestCase):
    def test_transient_classification(self):
        for errno in (1205, 1213, 2003, 2006, 2013, 2055):
            self.assertTrue(is_transient_db_error(FakeMySQLError(errno)), errno)
        self.assertTrue(is_transient_db_error(ConnectionResetError("reset")))
        self.assertTrue(is_transient_db_error(RuntimeError("MySQL Connection not available.")))
        self.assertFalse(is_transient_db_error(FakeMySQLError(1146, "Table doesn't exist")))
        self.assertFalse(is_transient_db_error(ValueError("bad value")))

    def test_non_transient_error_fails_fast_without_retry(self):
        calls = []

        @retry_db_operation(max_attempts=3, delay=0)
        def op():
            calls.append(1)
            raise FakeMySQLError(1146, "Table doesn't exist")

        with self.assertRaises(FakeMySQLError):
            op()
        self.assertEqual(len(calls), 1)

    def test_transient_error_is_retried_then_succeeds(self):
        calls = []

        @retry_db_operation(max_attempts=3, delay=0)
        def op():
            calls.append(1)
            if len(calls) < 3:
                raise FakeMySQLError(2013, "Lost connection")
            return "ok"

        self.assertEqual(op(), "ok")
        self.assertEqual(len(calls), 3)


class DatePolicyTests(unittest.TestCase):
    def setUp(self):
        dates._last_rebuilt_at.clear()
        patcher = patch.multiple(
            "app.utils.dates.Config",
            PRIOR_DAY_REBUILD_INTERVAL_SECONDS=3600,
            BACKFILL_MODE=False,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_first_run_rebuilds_everything(self):
        self.assertEqual(select_dates_to_rebuild(["2026-09-19", "2026-09-20"], now=1000.0),
                         ["2026-09-19", "2026-09-20"])

    def test_earlier_date_is_throttled_until_interval_elapses(self):
        mark_dates_rebuilt(["2026-09-19"], now=1000.0)
        days = ["2026-09-19", "2026-09-20"]
        self.assertEqual(select_dates_to_rebuild(days, now=1000.0 + 600), ["2026-09-20"])
        self.assertEqual(select_dates_to_rebuild(days, now=1000.0 + 3600), days)

    def test_latest_date_is_always_rebuilt(self):
        mark_dates_rebuilt(["2026-09-19", "2026-09-20"], now=1000.0)
        self.assertEqual(select_dates_to_rebuild(["2026-09-19", "2026-09-20"], now=1001.0), ["2026-09-20"])

    def test_new_day_rebuilds_yesterday_immediately(self):
        # Yesterday was only ever the latest date, so it was never marked and is due right away.
        mark_dates_rebuilt(["2026-09-19"], now=1000.0)
        self.assertEqual(select_dates_to_rebuild(["2026-09-20", "2026-09-21"], now=1001.0),
                         ["2026-09-20", "2026-09-21"])

    def test_zero_interval_and_backfill_disable_the_policy(self):
        mark_dates_rebuilt(["2026-09-19"], now=1000.0)
        days = ["2026-09-19", "2026-09-20"]
        with patch("app.utils.dates.Config.PRIOR_DAY_REBUILD_INTERVAL_SECONDS", 0):
            self.assertEqual(select_dates_to_rebuild(days, now=1001.0), days)
        with patch("app.utils.dates.Config.BACKFILL_MODE", True):
            self.assertEqual(select_dates_to_rebuild(days, now=1001.0), days)

    def test_tracked_dates_are_bounded(self):
        for i in range(100):
            mark_dates_rebuilt([f"d{i}"], now=float(i))
        self.assertLessEqual(len(dates._last_rebuilt_at), 30)


class TTLCacheTests(unittest.TestCase):
    def test_expiry_invalidate_and_disabled(self):
        now = [0.0]
        cache = TTLCache(10, clock=lambda: now[0])
        cache.set("a", [1])
        self.assertEqual(cache.get("a"), [1])
        now[0] = 9.9
        self.assertEqual(cache.get("a"), [1])
        now[0] = 10.0
        self.assertIsNone(cache.get("a"))

        cache.set("b", 2)
        cache.invalidate()
        self.assertIsNone(cache.get("b"))

        disabled = TTLCache(0)
        disabled.set("a", 1)
        self.assertIsNone(disabled.get("a"))

    def test_set_evicts_expired_entries(self):
        now = [0.0]
        cache = TTLCache(10, clock=lambda: now[0])
        cache.set("old", 1)
        now[0] = 50.0
        cache.set("new", 2)
        self.assertEqual(list(cache._items), ["new"])


if __name__ == "__main__":
    unittest.main()
