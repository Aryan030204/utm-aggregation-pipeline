import os
from dotenv import load_dotenv

# Load .env first
load_dotenv(".env")
# Then load .env.local to override/supplement variables
load_dotenv(".env.local")

class Config:
    KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
    KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "pipeline-topic")
    KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "utm-aggregate-worker")

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

    # Free Run (runs autonomously without Kafka)
    FREE_RUN = os.getenv("FREE_RUN", "false").lower() == "true"
    FREE_RUN_START_DATE = os.getenv("FREE_RUN_START_DATE", "")
    FREE_RUN_END_DATE = os.getenv("FREE_RUN_END_DATE", "")
