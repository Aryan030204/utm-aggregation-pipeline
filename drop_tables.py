from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.local")

from app.services.brand_fetcher import BrandFetcher
from app.services.db_manager import DBManager
from app.sql.setup import DAILY_TABLES, HOURLY_TABLES

def main():
    brands = BrandFetcher.get_all_brands()
    for b in brands:
        db = DBManager(
            brand_name=b.get("brand_name", "Unknown"),
            host=b.get("host", "localhost"),
            user=b.get("user", "root"),
            password=b.get("password", ""),
            database=b.get("database", ""),
            port=b.get("port", 3306)
        )
        try:
            db.connect()
            tables = DAILY_TABLES + HOURLY_TABLES
            print(f"\nConnected to {b.get('brand_name', 'Unknown')}. Dropping tables...")
            for t in tables:
                db.execute_query(f"DROP TABLE IF EXISTS {t};", commit=True)
                print(f" - Dropped {t}")
        except Exception as e:
            print(f"Error for {b.get('brand_name', 'Unknown')}: {e}")
        finally:
            db.close()

if __name__ == "__main__":
    main()
