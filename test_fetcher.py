from app.services.brand_fetcher import BrandFetcher

print("Fetching brands...")
brands = BrandFetcher.get_all_brands()
for b in brands:
    print(f"Brand: {b.get('brand_name')} -> DB: {b.get('database')} connecting to {b.get('host')}:{b.get('port')}")
