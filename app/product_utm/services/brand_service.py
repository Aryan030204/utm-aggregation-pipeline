from __future__ import annotations

import base64
from typing import Any

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from app.product_utm.config import ProductUTMConfig
from app.product_utm.models import BrandContext
from app.utils.logger import get_logger
from app.utils.ttl_cache import TTLCache

logger = get_logger(__name__)


class BrandService:
    # 1 list call + 1 detail call per brand on every 10-minute cycle is wasteful for
    # data that rarely changes. Only non-empty results are cached.
    _cache = TTLCache(ProductUTMConfig.BRANDS_CACHE_TTL_SECONDS)
    _CACHE_KEY = "active_brands"

    @staticmethod
    def invalidate_cache() -> None:
        """Drop the cached brand list, e.g. after a brand run fails (rotated token/credentials)."""
        BrandService._cache.invalidate()

    @staticmethod
    def get_active_brands() -> list[BrandContext]:
        cached = BrandService._cache.get(BrandService._CACHE_KEY)
        if cached is not None:
            return list(cached)

        brands = BrandService._fetch_active_brands()
        if brands:
            BrandService._cache.set(BrandService._CACHE_KEY, brands)
        return list(brands)

    @staticmethod
    def _fetch_active_brands() -> list[BrandContext]:
        headers = {"x-pipeline-key": ProductUTMConfig.PIPELINE_AUTH_HEADER}
        response = requests.get(ProductUTMConfig.GET_BRANDS_API, headers=headers, timeout=30)
        response.raise_for_status()
        brands_map = response.json()

        active_brands: list[BrandContext] = []
        for brand_id, brand_name in brands_map.items():
            try:
                detail_response = requests.get(
                    f"{ProductUTMConfig.GET_BRANDS_API}/{brand_id}",
                    headers=headers,
                    timeout=30,
                )
                detail_response.raise_for_status()
                detail = detail_response.json()
                if detail.get("is_active") is not True:
                    continue

                active_brands.append(
                    BrandContext(
                        brand_id=str(brand_id),
                        brand_name=detail.get("brand_name", brand_name),
                        host=detail.get("db_host", ""),
                        user=detail.get("db_user", ""),
                        password=BrandService.decrypt_value(detail.get("db_password", "")),
                        database=detail.get("db_database", ""),
                        port=int(detail.get("port", detail.get("db_port", 3306))),
                        access_token=BrandService.decrypt_value(detail.get("access_token", "")),
                        shop_name=detail.get("shop_name", ""),
                        api_version=detail.get("api_version", "2025-10"),
                        store_timezone=detail.get("store_timezone", "UTC"),
                    )
                )
            except Exception as exc:
                logger.error("Failed to load brand %s: %s", brand_id, exc)
        return active_brands

    @staticmethod
    def decrypt_value(encrypted_str: str) -> str:
        if not encrypted_str or ":" not in encrypted_str:
            return encrypted_str

        iv_b64, cipher_b64 = encrypted_str.split(":", 1)
        iv = base64.b64decode(iv_b64)
        cipher = base64.b64decode(cipher_b64)
        key = ProductUTMConfig.PASSWORD_AES_KEY.encode("utf-8").ljust(32, b"\0")
        aes = AES.new(key, AES.MODE_CBC, iv)
        return unpad(aes.decrypt(cipher), AES.block_size).decode("utf-8")
