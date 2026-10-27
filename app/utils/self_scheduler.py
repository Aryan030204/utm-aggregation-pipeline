from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.utils.logger import get_logger

logger = get_logger(__name__)


def startup_delay_seconds(default: int = 60) -> int:
    """STARTUP_DELAY_SECONDS: how long a container waits after starting before its catch-up run.
    docker-compose gives each UTM container a different value so a host restart does not start
    them all at once."""
    try:
        return max(0, int(os.getenv("STARTUP_DELAY_SECONDS", str(default))))
    except ValueError:
        return default


def run_forever(
    job_fn: Callable[[], None],
    cron_expr: str,
    job_id: str,
    startup_delay_s: Optional[int] = None,
) -> None:
    """Fires job_fn on the given cron schedule forever, plus one catch-up run shortly after
    start (so a container reboot/rebuild doesn't have to wait for the next cron tick).
    Mirrors the self-scheduling pattern already used by app/main.py's SELF_RUN mode, for
    workers that now run as long-lived Docker containers instead of one-shot CI jobs.

    The catch-up run is delayed by `startup_delay_s` (default: STARTUP_DELAY_SECONDS) instead of
    running the moment the process starts, and it never overlaps a scheduled run of the same job.

    A failed run is logged and swallowed here so one bad cycle doesn't kill the
    container -- the next scheduled run still fires."""

    running = threading.Lock()

    def _guarded_job():
        if not running.acquire(blocking=False):
            logger.info(f"[{job_id}] Previous run still in progress; skipping this trigger.")
            return
        try:
            job_fn()
        except Exception as exc:
            logger.error(f"[{job_id}] Run failed: {exc}")
        finally:
            running.release()

    delay = startup_delay_seconds() if startup_delay_s is None else max(0, int(startup_delay_s))
    logger.info(f"[{job_id}] Starting self-scheduled loop with cron pattern: {cron_expr}")
    scheduler = BlockingScheduler()
    scheduler.add_job(_guarded_job, CronTrigger.from_crontab(cron_expr), id=job_id)
    logger.info(f"[{job_id}] Startup catch-up run in {delay}s")
    scheduler.add_job(
        _guarded_job, "date", run_date=datetime.now() + timedelta(seconds=delay), id=f"{job_id}_startup"
    )
    scheduler.start()
