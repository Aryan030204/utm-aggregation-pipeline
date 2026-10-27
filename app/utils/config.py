import os
from dotenv import load_dotenv

# Load .env first
load_dotenv(".env")

# Only load .env.local for TEST_MODE to avoid overriding production values.
_test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
if _test_mode:
    load_dotenv(".env.local")

class Config:
    PORT = int(os.getenv("PORT", "8000"))
    HOST = os.getenv("HOST", "0.0.0.0")

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))

    # Multi-brand and Test Mode
    TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"
    GET_BRANDS_API = os.getenv("GET_BRANDS_API", "")
    PIPELINE_AUTH_HEADER = os.getenv("PIPELINE_AUTH_HEADER", "")
    PASSWORD_AES_KEY = os.getenv("PASSWORD_AES_KEY", "")
    ACTIVE_BRAND_IDS = os.getenv("ACTIVE_BRAND_IDS", "")

    # Backfill
    BACKFILL_MODE = os.getenv("BACKFILL_MODE", "false").lower() == "true"
    BACKFILL_START_IST = os.getenv("BACKFILL_START_IST", "")
    BACKFILL_END_IST = os.getenv("BACKFILL_END_IST", "")
    BACKFILL_BRAND_INDICES = os.getenv("BACKFILL_BRAND_INDICES", "")

    # Free Run (runs autonomously without Kafka)
    FREE_RUN = os.getenv("FREE_RUN", "false").lower() == "true"
    FREE_RUN_START_DATE = os.getenv("FREE_RUN_START_DATE", "")
    FREE_RUN_END_DATE = os.getenv("FREE_RUN_END_DATE", "")

    # Self Run (internal scheduler)
    SELF_RUN = os.getenv("SELF_RUN", "true").lower() == "true"
    PIPELINE_SCHEDULE = os.getenv("PIPELINE_SCHEDULE", "0 * * * *")  # Default: Hourly

    # Manager Endpoints
    MANAGER_STARTED_ENDPOINT = os.getenv("MANAGER_STARTED_ENDPOINT", "")
    MANAGER_COMPLETED_ENDPOINT = os.getenv("MANAGER_COMPLETED_ENDPOINT", "")
    MANAGER_FAILED_ENDPOINT = os.getenv("MANAGER_FAILED_ENDPOINT", "")
    PIPELINE_ID = os.getenv("PIPELINE_ID", "")

    # Global Retrospective Worker Settings
    GLOBAL_RETROSPECTIVE_CRON = os.getenv("GLOBAL_RETROSPECTIVE_CRON", "57 18 * * *")  # Default: 00:27 AM IST / 18:57 UTC (was 00:05, moved off the midnight cluster)
    GLOBAL_RETROSPECTIVE_LOOKBACK_DAYS = int(os.getenv("GLOBAL_RETROSPECTIVE_LOOKBACK_DAYS", "2"))
    MAX_BRAND_RETRIES = int(os.getenv("MAX_BRAND_RETRIES", "3"))

    # Load-reduction knobs (safe defaults; 0 disables where noted)
    # Seconds between rebuilds of dates older than the latest target date on the webhook pipeline. 0 = rebuild every trigger.
    PRIOR_DAY_REBUILD_INTERVAL_SECONDS = int(os.getenv("PRIOR_DAY_REBUILD_INTERVAL_SECONDS", "3600"))
    # How long the global retrospective worker waits for a brand's aggregation lock held by another run.
    GLOBAL_WORKER_LOCK_WAIT_SECONDS = int(os.getenv("GLOBAL_WORKER_LOCK_WAIT_SECONDS", "900"))
    # TTL for the cached brand list. 0 disables caching.
    BRANDS_CACHE_TTL_SECONDS = int(os.getenv("BRANDS_CACHE_TTL_SECONDS", "1800"))

