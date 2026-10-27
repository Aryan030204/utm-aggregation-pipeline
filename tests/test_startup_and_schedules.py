import threading
import unittest
from unittest import mock

from app.utils import self_scheduler
from app.utils.config import Config
from app.product_utm.config import ProductUTMConfig


class RunForeverStartupTests(unittest.TestCase):
    def _run(self, job, delay):
        scheduler = mock.Mock()
        with mock.patch.object(self_scheduler, "BlockingScheduler", return_value=scheduler):
            self_scheduler.run_forever(job, "7 * * * *", job_id="t", startup_delay_s=delay)
        return scheduler

    def test_job_is_not_run_inline_at_startup(self):
        calls = []
        scheduler = self._run(lambda: calls.append(1), 120)

        self.assertEqual(calls, [])
        scheduler.start.assert_called_once()

    def test_catch_up_run_is_scheduled_after_the_delay(self):
        from datetime import datetime, timedelta

        before = datetime.now()
        scheduler = self._run(lambda: None, 120)

        startup = [c for c in scheduler.add_job.call_args_list if c.kwargs.get("id") == "t_startup"]
        self.assertEqual(len(startup), 1)
        self.assertEqual(startup[0].args[1], "date")
        self.assertGreaterEqual(startup[0].kwargs["run_date"], before + timedelta(seconds=119))
        cron = [c for c in scheduler.add_job.call_args_list if c.kwargs.get("id") == "t"]
        self.assertEqual(len(cron), 1, "the recurring cron job is still registered")

    def test_overlapping_triggers_of_one_job_are_skipped(self):
        started, release, count = threading.Event(), threading.Event(), []

        def slow():
            count.append(1)
            started.set()
            release.wait(3)

        scheduler = self._run(slow, 0)
        guarded = scheduler.add_job.call_args_list[0].args[0]

        t = threading.Thread(target=guarded)
        t.start()
        self.assertTrue(started.wait(2))
        guarded()  # second trigger while the first is still running
        release.set()
        t.join(3)

        self.assertEqual(len(count), 1)

    def test_a_failing_run_is_swallowed_and_releases_the_guard(self):
        runs = []

        def flaky():
            runs.append(1)
            if len(runs) == 1:
                raise RuntimeError("boom")

        scheduler = self._run(flaky, 0)
        guarded = scheduler.add_job.call_args_list[0].args[0]
        guarded()
        guarded()
        self.assertEqual(len(runs), 2)

    def test_env_delay_is_used_and_bad_values_fall_back(self):
        with mock.patch.dict("os.environ", {"STARTUP_DELAY_SECONDS": "45"}):
            self.assertEqual(self_scheduler.startup_delay_seconds(), 45)
        with mock.patch.dict("os.environ", {"STARTUP_DELAY_SECONDS": "abc"}):
            self.assertEqual(self_scheduler.startup_delay_seconds(default=60), 60)


class ScheduleTests(unittest.TestCase):
    def test_global_retrospective_moves_out_of_the_midnight_cluster(self):
        import os
        import re
        from apscheduler.triggers.cron import CronTrigger

        compose = open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "docker-compose.yml"), encoding="utf-8").read()
        # 18:57 UTC == 00:27 IST (was 18:35 UTC == 00:05 IST). Compose beats the .env value.
        match = re.search(r"GLOBAL_RETROSPECTIVE_CRON: \$\{UTM_GLOBAL_RETRO_CRON:-([^}]+)\}", compose)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "57 18 * * *")
        CronTrigger.from_crontab(match.group(1))
        CronTrigger.from_crontab(Config.GLOBAL_RETROSPECTIVE_CRON)  # the env/default value stays valid

    def test_each_utm_container_has_its_own_startup_delay(self):
        import os
        import re

        compose = open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "docker-compose.yml"), encoding="utf-8").read()
        delays = re.findall(r"STARTUP_DELAY_SECONDS: \$\{\w+:-(\d+)\}", compose)
        self.assertEqual(len(delays), 4)
        self.assertEqual(len(set(delays)), 4, "startup runs must be staggered, not simultaneous")


if __name__ == "__main__":
    unittest.main()
