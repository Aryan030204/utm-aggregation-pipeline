import base64
import unittest
from unittest.mock import patch

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from app.product_utm.services.brand_service import BrandService


class MockResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def encrypt_value(key_text: str, plaintext: str) -> str:
    iv = b"1234567890abcdef"
    key = key_text.encode("utf-8").ljust(32, b"\0")
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size))
    return f"{base64.b64encode(iv).decode()}:{base64.b64encode(encrypted).decode()}"


class BrandServiceTests(unittest.TestCase):
    def setUp(self):
        BrandService.invalidate_cache()

    def test_get_active_brands_filters_and_decrypts(self):
        encrypted_password = encrypt_value("awsaesproxykey", "db-secret")
        encrypted_token = encrypt_value("awsaesproxykey", "shopify-token")
        brands_map = {"1": "A", "2": "B"}
        details = {
            "1": {
                "brand_name": "A",
                "db_host": "host",
                "db_user": "user",
                "db_password": encrypted_password,
                "db_database": "database",
                "port": 3306,
                "access_token": encrypted_token,
                "shop_name": "a.myshopify.com",
                "api_version": "2025-10",
                "store_timezone": "Asia/Kolkata",
                "is_active": True,
            },
            "2": {"brand_name": "B", "is_active": False},
        }

        def fake_get(url, headers=None, timeout=None):
            if url == "https://brands.example/api":
                return MockResponse(brands_map)
            return MockResponse(details[url.rsplit("/", 1)[-1]])

        with patch("app.product_utm.services.brand_service.ProductUTMConfig.GET_BRANDS_API", "https://brands.example/api"), \
             patch("app.product_utm.services.brand_service.ProductUTMConfig.PIPELINE_AUTH_HEADER", "secret"), \
             patch("app.product_utm.services.brand_service.ProductUTMConfig.PASSWORD_AES_KEY", "awsaesproxykey"), \
             patch("app.product_utm.services.brand_service.requests.get", side_effect=fake_get):
            brands = BrandService.get_active_brands()

        self.assertEqual(len(brands), 1)
        self.assertEqual(brands[0].password, "db-secret")
        self.assertEqual(brands[0].access_token, "shopify-token")
