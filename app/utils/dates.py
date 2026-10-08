import threading
import time
from datetime import datetime, timedelta
from app.utils.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)

# When each non-latest date was last rebuilt by this process (monotonic seconds).
# In-memory on purpose: after a restart both days are rebuilt once, then throttled again.
_last_rebuilt_at: dict[str, float] = {}
_last_rebuilt_lock = threading.Lock()
_MAX_TRACKED_DATES = 30


def select_dates_to_rebuild(target_dates: list[str], now: float | None = None) -> list[str]:
    """The latest target date is rebuilt on every trigger. Earlier dates barely change
    after the first hours, so they are only rebuilt once PRIOR_DAY_REBUILD_INTERVAL_SECONDS
    has passed since their last rebuild. Backfills and an interval of 0 rebuild everything."""
    interval = Config.PRIOR_DAY_REBUILD_INTERVAL_SECONDS
    if Config.BACKFILL_MODE or interval <= 0 or len(target_dates) <= 1:
        return list(target_dates)

    now = time.monotonic() if now is None else now
    *earlier, latest = target_dates
    with _last_rebuilt_lock:
        selected = [
            d for d in earlier
            if d not in _last_rebuilt_at or now - _last_rebuilt_at[d] >= interval
        ]
    selected.append(latest)
    if len(selected) < len(target_dates):
        skipped = [d for d in earlier if d not in selected]
        logger.info(f"Skipping recent rebuild of earlier date(s) {skipped}; rebuilding {selected}.")
    return selected


def mark_dates_rebuilt(dates: list[str], now: float | None = None) -> None:
    """Record a fully successful rebuild of the given (earlier) dates."""
    now = time.monotonic() if now is None else now
    with _last_rebuilt_lock:
        for d in dates:
            _last_rebuilt_at[d] = now
        if len(_last_rebuilt_at) > _MAX_TRACKED_DATES:
            for d in sorted(_last_rebuilt_at, key=_last_rebuilt_at.get)[: len(_last_rebuilt_at) - _MAX_TRACKED_DATES]:
                del _last_rebuilt_at[d]


def generate_target_dates(completed_at: str, recompute_days: int = 2) -> list[str]:
    """
    Returns a list of 'YYYY-MM-DD' strings.
    If BACKFILL_MODE is false, returns a rolling window ending on completed_at.
    If BACKFILL_MODE is true, generates a range from BACKFILL_START_IST to BACKFILL_END_IST.
    """
    if not Config.BACKFILL_MODE:
        end_date = datetime.strptime(completed_at.split('T')[0], "%Y-%m-%d")
        days = max(1, recompute_days)
        start_date = end_date - timedelta(days=days - 1)

        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        logger.info(f"Generated {len(dates)} target dates from {start_date.date()} to {end_date.date()}.")
        return dates

    try:
        # Expected format: "2026-01-26T00:00:00"
        start_date = datetime.strptime(Config.BACKFILL_START_IST.split('T')[0], "%Y-%m-%d")
        end_date = datetime.strptime(Config.BACKFILL_END_IST.split('T')[0], "%Y-%m-%d")
        
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
            
        logger.info(f"Backfill mode active. Generated {len(dates)} dates from {start_date.date()} to {end_date.date()}.")
        return dates
    except Exception as e:
        logger.error(f"Failed to generate backfill dates: {e}")
        # fallback to normal rolling window
        return generate_target_dates(completed_at, recompute_days)

def generate_free_run_dates() -> list[str]:
    """
    Generates a list of dates based on FREE_RUN_START_DATE and FREE_RUN_END_DATE.
    """
    try:
        start_date = datetime.strptime(Config.FREE_RUN_START_DATE.split('T')[0], "%Y-%m-%d")
        end_date = datetime.strptime(Config.FREE_RUN_END_DATE.split('T')[0], "%Y-%m-%d")
        
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
            
        logger.info(f"Free run mode active. Generated {len(dates)} dates from {start_date.date()} to {end_date.date()}.")
        return dates
    except Exception as e:
        logger.error(f"Failed to generate free run dates: {e}")
        return []
