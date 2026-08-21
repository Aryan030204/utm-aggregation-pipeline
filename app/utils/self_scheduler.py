from __future__ import annotations

from typing import Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.utils.logger import get_logger

logger = get_logger(__name__)


def run_forever(job_fn: Callable[[], None], cron_expr: str, job_id: str) -> None:
    """Blocks and fires job_fn on the given cron schedule, forever. Mirrors the
    self-scheduling pattern already used by app/main.py's SELF_RUN mode, for workers
    that now run as long-lived Docker containers instead of one-shot CI jobs.

    A failed run is logged and swallowed here so one bad cycle doesn't kill the
    container -- the next scheduled run still fires."""

    def _guarded_job():
        try:
            job_fn()
        except Exception as exc:
            logger.error(f"[{job_id}] Scheduled run failed: {exc}")

    logger.info(f"[{job_id}] Starting self-scheduled loop with cron pattern: {cron_expr}")
    scheduler = BlockingScheduler()
    scheduler.add_job(_guarded_job, CronTrigger.from_crontab(cron_expr), id=job_id)
    scheduler.start()
