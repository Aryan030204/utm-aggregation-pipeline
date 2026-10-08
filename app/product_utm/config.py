import os
from dotenv import load_dotenv

load_dotenv(".env")


class ProductUTMConfig:
    GET_BRANDS_API = os.getenv("GET_BRANDS_API", "")
    PIPELINE_AUTH_HEADER = os.getenv("PIPELINE_AUTH_HEADER", "")
    PASSWORD_AES_KEY = os.getenv("PASSWORD_AES_KEY", "")

    TOP_PRODUCT_LIMIT = int(os.getenv("TOP_PRODUCT_LIMIT", "10"))
    TOP_PRODUCT_LOOKBACK_DAYS = int(os.getenv("TOP_PRODUCT_LOOKBACK_DAYS", "30"))
    RETROSPECTIVE_DAYS = int(os.getenv("RETROSPECTIVE_DAYS", "2"))

    DAILY_WORKER_CRON = os.getenv("DAILY_WORKER_CRON", "0 * * * *")
    RETROSPECTIVE_WORKER_CRON = os.getenv("RETROSPECTIVE_WORKER_CRON", "0 0 */2 * *")

    GRAPHQL_MIN_BALANCE = int(os.getenv("GRAPHQL_MIN_BALANCE", "100"))
    GRAPHQL_MAX_RETRIES = int(os.getenv("GRAPHQL_MAX_RETRIES", "3"))
    GRAPHQL_BASE_BACKOFF_SECONDS = float(os.getenv("GRAPHQL_BASE_BACKOFF_SECONDS", "2"))
    GRAPHQL_SLEEP_BUFFER_SECONDS = float(os.getenv("GRAPHQL_SLEEP_BUFFER_SECONDS", "1"))

    DB_BATCH_SIZE = int(os.getenv("DB_BATCH_SIZE", "500"))
    WORKFLOW_TIMEOUT_MINUTES = int(os.getenv("WORKFLOW_TIMEOUT_MINUTES", "60"))

    # Caching (0 disables)
    BRANDS_CACHE_TTL_SECONDS = int(os.getenv("BRANDS_CACHE_TTL_SECONDS", "1800"))
    TOP_PRODUCTS_CACHE_TTL_SECONDS = int(os.getenv("TOP_PRODUCTS_CACHE_TTL_SECONDS", "3600"))

    # Global UTM retrospective worker: paginated ShopifyQL order/sales fetch
    SHOPIFYQL_ORDERS_PAGE_SIZE = int(os.getenv("SHOPIFYQL_ORDERS_PAGE_SIZE", "250"))
    SHOPIFYQL_ORDERS_MAX_PAGES = int(os.getenv("SHOPIFYQL_ORDERS_MAX_PAGES", "200"))
    # GraphQLRequestManager already retries with throttle-aware backoff, so keep this outer layer at 1.
    SHOPIFYQL_PAGE_FETCH_MAX_RETRIES = int(os.getenv("SHOPIFYQL_PAGE_FETCH_MAX_RETRIES", "1"))
    SHOPIFYQL_PAGE_FETCH_BASE_BACKOFF_SECONDS = float(os.getenv("SHOPIFYQL_PAGE_FETCH_BASE_BACKOFF_SECONDS", "2"))
