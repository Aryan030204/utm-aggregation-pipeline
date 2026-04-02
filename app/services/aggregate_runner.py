from typing import Dict, Any, List
from app.utils.logger import get_logger
from app.utils.retry import retry_db_operation
from app.services.db_manager import DBManager
from app.services.query_builder import build_delete_query, build_insert_query
from app.sql.setup import ensure_tables_exist, DAILY_TABLES, HOURLY_TABLES

logger = get_logger(__name__)

class AggregateRunner:
    def __init__(self, brand_info: Dict[str, Any], target_dates: List[str]):
        self.brand_info = brand_info
        self.target_dates = target_dates
        self.db_manager = DBManager(
            brand_name=brand_info["brand_name"],
            host=brand_info["host"],
            user=brand_info["user"],
            password=brand_info["password"],
            database=brand_info["database"],
            port=brand_info.get("port", 3306)
        )

    @retry_db_operation()
    def initialize(self):
        """Ensures that the aggregate tables exist before we try to populate them."""
        ensure_tables_exist(self.db_manager)

    @retry_db_operation()
    def run_aggregations(self):
        brand_name = self.brand_info["brand_name"]
        all_tables = [(t, False) for t in DAILY_TABLES] + [(t, True) for t in HOURLY_TABLES]
        
        try:
            for metric_date in self.target_dates:
                logger.info(f"Starting aggregations for brand: {brand_name}, date: {metric_date}")
                
                for table_name, is_hourly in all_tables:
                    logger.debug(f"Rebuilding {table_name} for date {metric_date}")
                    
                    # 1. Delete current day's aggregates
                    delete_query = build_delete_query(table_name)
                    self.db_manager.execute_query(delete_query, (metric_date,), commit=True)
                    
                    # 2. Insert new aggregated data for current day
                    insert_query = build_insert_query(table_name, is_hourly)
                    # Note: Using (metric_date, metric_date) because UNION ALL has two %s placeholders
                    self.db_manager.execute_query(insert_query, (metric_date, metric_date), commit=True)
                    
            logger.info(f"Successfully rebuilt all tables for {brand_name} across {len(self.target_dates)} day(s).")
        except Exception as e:
            logger.error(f"Failed to rebuild aggregate tables for {brand_name}: {e}")
            raise e
        finally:
            self.db_manager.close()
