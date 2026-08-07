from __future__ import annotations

from typing import Any, Dict

from app.product_utm.models import BrandContext


def build_brand_context(brand_info: Dict[str, Any]) -> BrandContext:
    """Builds a BrandContext (used by GraphQLRequestManager) from the brand dict
    returned by BrandFetcher. Fails loudly if Shopify credentials are missing so a
    misconfigured brand surfaces as a brand-level failure rather than silently
    skipping order data."""
    access_token = brand_info.get("access_token")
    shop_name = brand_info.get("shop_name")
    if not access_token or not shop_name:
        raise ValueError(
            f"Brand '{brand_info.get('brand_name', 'unknown')}' is missing Shopify "
            "access_token/shop_name required for the GraphQL orders fetch."
        )

    return BrandContext(
        brand_id=str(brand_info.get("brand_id", "")),
        brand_name=brand_info["brand_name"],
        host=brand_info["host"],
        user=brand_info["user"],
        password=brand_info["password"],
        database=brand_info["database"],
        port=brand_info.get("port", 3306),
        access_token=access_token,
        shop_name=shop_name,
        api_version=brand_info.get("api_version") or "2025-10",
        store_timezone=brand_info.get("store_timezone") or "UTC",
    )
