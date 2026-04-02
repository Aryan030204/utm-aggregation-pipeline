import logging
import sys
from app.utils.config import Config

def get_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        logger.setLevel(Config.LOG_LEVEL)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(Config.LOG_LEVEL)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
