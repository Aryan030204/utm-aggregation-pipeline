from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.local")

from app.services.brand_fetcher import BrandFetcher
from app.services.db_manager import DBManager
from app.sql.setup import DAILY_TABLES, HOURLY_TABLES

def main():
    print("Fetching brand credentials...")
    brands = BrandFetcher.get_all_brands()
    if not brands:
        print("No brands found. Please check your .env.local and ACTIVE_BRAND_IDS.")
        return

    # Use the first brand to fetch schema definitions
    b = brands[0]
    print(f"Connecting to database '{b.get('database')}' for brand '{b.get('brand_name')}'...")
    
    db = DBManager(
        brand_name=b.get("brand_name", "Unknown"),
        host=b.get("host", "localhost"),
        user=b.get("user", "root"),
        password=b.get("password", ""),
        database=b.get("database", ""),
        port=b.get("port", 3306)
    )
    
    output_file = "pipeline_schemas.sql"
    all_tables = DAILY_TABLES + HOURLY_TABLES
    
    try:
        db.connect()
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("-- UTM Aggregate Pipeline Table Schemas\n")
            f.write(f"-- Exported from brand: {b.get('brand_name')}\n\n")
            
            for table in all_tables:
                print(f"Fetching schema for: {table}")
                try:
                    result = db.execute_query(f"SHOW CREATE TABLE {table}")
                    if result and len(result) > 0:
                        # SHOW CREATE TABLE returns a list of dicts like [{'Table': '...', 'Create Table': '...'}]
                        create_sql = result[0].get('Create Table', '')
                        f.write(f"-- Schema for {table}\n")
                        f.write(f"DROP TABLE IF EXISTS `{table}`;\n")
                        f.write(create_sql + ";\n\n")
                    else:
                        print(f" ! Table {table} not found in database.")
                except Exception as table_e:
                    print(f" ! Error fetching {table}: {table_e}")
                    
        print(f"\nSuccess! Schemas exported to: {output_file}")
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
