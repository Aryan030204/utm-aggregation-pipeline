import os
import unittest
from unittest.mock import patch

from app.services.brand_fetcher import BrandFetcher


class MockResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class BrandFetcherTests(unittest.TestCase):
    def setUp(self):
        BrandFetcher.invalidate_cache()

    def test_get_brands_from_api_only_includes_literal_true_is_active(self):
        brands_map = {
            "1": "Active Brand",
            "2": "Inactive Brand",
            "3": "Missing Flag Brand",
            "4": "String Flag Brand",
        }
        detail_payloads = {
            "1": {
                "brand_name": "Active Brand",
                "db_host": "host-1",
                "db_user": "user-1",
                "db_password": "pw-1",
                "db_database": "db-1",
                "port": 3307,
                "is_active": True,
            },
            "2": {
                "brand_name": "Inactive Brand",
                "db_host": "host-2",
                "db_user": "user-2",
                "db_password": "pw-2",
                "db_database": "db-2",
                "port": 3308,
                "is_active": False,
            },
            "3": {
                "brand_name": "Missing Flag Brand",
                "db_host": "host-3",
                "db_user": "user-3",
                "db_password": "pw-3",
                "db_database": "db-3",
                "port": 3309,
            },
            "4": {
                "brand_name": "String Flag Brand",
                "db_host": "host-4",
                "db_user": "user-4",
                "db_password": "pw-4",
                "db_database": "db-4",
                "port": 3310,
                "is_active": "true",
            },
        }

        def fake_get(url, headers=None, timeout=None):
            if url == "https://brands.example/api":
                return MockResponse(brands_map)

            brand_id = url.rsplit("/", 1)[-1]
            return MockResponse(detail_payloads[brand_id])

        with patch("app.services.brand_fetcher.Config.GET_BRANDS_API", "https://brands.example/api"), \
             patch("app.services.brand_fetcher.Config.PIPELINE_AUTH_HEADER", "secret"), \
             patch("app.services.brand_fetcher.requests.get", side_effect=fake_get):
            brands = BrandFetcher._get_brands_from_api()

        self.assertEqual(
            brands,
            [
                {
                    "brand_id": "1",
                    "brand_name": "Active Brand",
                    "host": "host-1",
                    "user": "user-1",
                    "password": "pw-1",
                    "database": "db-1",
                    "port": 3307,
                    "access_token": "",
                    "shop_name": "",
                    "api_version": "2025-10",
                    "store_timezone": "UTC",
                }
            ],
        )

    def test_get_all_brands_applies_active_filter_before_backfill_filter(self):
        api_brands = [
            {"brand_id": "1", "brand_name": "Active A"},
            {"brand_id": "2", "brand_name": "Active B"},
        ]

        with patch("app.services.brand_fetcher.Config.TEST_MODE", False), \
             patch("app.services.brand_fetcher.Config.BACKFILL_MODE", True), \
             patch("app.services.brand_fetcher.Config.BACKFILL_BRAND_INDICES", "2,3"), \
             patch.object(BrandFetcher, "_get_brands_from_api", return_value=api_brands):
            brands = BrandFetcher.get_all_brands()

        self.assertEqual(brands, [{"brand_id": "2", "brand_name": "Active B"}])

    def test_get_brands_from_env_is_unchanged_in_test_mode(self):
        env = {
            "ACTIVE_BRAND_IDS": "10,11",
            "BRAND_ID_0": "10",
            "BRAND_NAME_0": "Env Brand A",
            "DB_HOST_0": "env-host-a",
            "DB_USER_0": "env-user-a",
            "DB_PASSWORD_0": "env-pw-a",
            "DB_DATABASE_0": "env-db-a",
            "DB_PORT_0": "3311",
            "BRAND_ID_1": "11",
            "BRAND_NAME_1": "Env Brand B",
            "DB_HOST_1": "env-host-b",
            "DB_USER_1": "env-user-b",
            "DB_PASSWORD_1": "env-pw-b",
            "DB_DATABASE_1": "env-db-b",
            "DB_PORT_1": "3312",
        }

        with patch("app.services.brand_fetcher.Config.TEST_MODE", True), \
             patch("app.services.brand_fetcher.Config.ACTIVE_BRAND_IDS", "10,11"), \
             patch("app.services.brand_fetcher.Config.BACKFILL_MODE", False), \
             patch("os.getenv", side_effect=lambda key, default=None: env.get(key, default)):
            brands = BrandFetcher.get_all_brands()

        self.assertEqual(
            brands,
            [
                {
                    "brand_id": "10",
                    "brand_name": "Env Brand A",
                    "host": "env-host-a",
                    "user": "env-user-a",
                    "password": "env-pw-a",
                    "database": "env-db-a",
                    "port": 3311,
                    "access_token": "",
                    "shop_name": "",
                    "api_version": "2025-10",
                    "store_timezone": "UTC",
                },
                {
                    "brand_id": "11",
                    "brand_name": "Env Brand B",
                    "host": "env-host-b",
                    "user": "env-user-b",
                    "password": "env-pw-b",
                    "database": "env-db-b",
                    "port": 3312,
                    "access_token": "",
                    "shop_name": "",
                    "api_version": "2025-10",
                    "store_timezone": "UTC",
                },
            ],
        )

    def test_get_brands_from_api_returns_empty_when_all_brands_are_inactive(self):
        brands_map = {"1": "Inactive A", "2": "Inactive B"}
        detail_payloads = {
            "1": {"brand_name": "Inactive A", "is_active": False},
            "2": {"brand_name": "Inactive B", "is_active": False},
        }

        def fake_get(url, headers=None, timeout=None):
            if url == "https://brands.example/api":
                return MockResponse(brands_map)

            brand_id = url.rsplit("/", 1)[-1]
            return MockResponse(detail_payloads[brand_id])

        with patch("app.services.brand_fetcher.Config.GET_BRANDS_API", "https://brands.example/api"), \
             patch("app.services.brand_fetcher.Config.PIPELINE_AUTH_HEADER", "secret"), \
             patch("app.services.brand_fetcher.requests.get", side_effect=fake_get):
            brands = BrandFetcher._get_brands_from_api()

        self.assertEqual(brands, [])


if __name__ == "__main__":
    unittest.main()
