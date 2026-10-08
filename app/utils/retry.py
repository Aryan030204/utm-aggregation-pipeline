import time
from functools import wraps
from app.utils.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)

# MySQL client/server errors that are worth retrying: lock wait timeout, deadlock,
# can't connect, server gone away, lost connection, lost connection (extended).
TRANSIENT_MYSQL_ERRNOS = {1205, 1213, 2003, 2006, 2013, 2055}
_TRANSIENT_MESSAGE_HINTS = ("connection not available", "lost connection", "server has gone away")


def is_transient_db_error(exc: BaseException) -> bool:
    """True only for failures a retry can plausibly fix. Logic errors (bad SQL, missing
    table, programming errors) are deterministic and must fail fast instead of being
    retried and re-doing all the work."""
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    if getattr(exc, "errno", None) in TRANSIENT_MYSQL_ERRNOS:
        return True
    message = str(exc).lower()
    return any(hint in message for hint in _TRANSIENT_MESSAGE_HINTS)


def retry_db_operation(max_attempts=Config.RETRY_ATTEMPTS, delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if not is_transient_db_error(e):
                        raise
                    attempts += 1
                    logger.warning(f"Attempt {attempts}/{max_attempts} failed for {func.__name__}: {e}")
                    if attempts >= max_attempts:
                        logger.error(f"Function {func.__name__} failed after {max_attempts} attempts.")
                        raise e
                    time.sleep(delay * attempts)  # linear backoff
        return wrapper
    return decorator
