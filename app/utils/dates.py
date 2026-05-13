from datetime import datetime, timedelta
from app.utils.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)

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
