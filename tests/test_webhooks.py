"""
Webhook idempotency tests.
These tests prove that Shopify's at-least-once delivery cannot duplicate orders.
"""
import json
import hmac
import hashlib
import base64

from django.conf import settings
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.merchants.models import Merchant
from apps.orders.models import Order


def _make_signature(body: bytes) -> str:
    digest = hmac.new(
        settings.SHOPIFY_API_SECRET.encode("utf-8"),
        body,
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode()


ORDER_PAYLOAD = {
    "id": 9999000001,
    "order_number": 1001,
    "created_at": "2026-08-18T10:00:00Z",
    "updated_at": "2026-08-18T10:00:00Z",
    "currency": "INR",
    "total_price": "1500.00",
    "financial_status": "paid",
    "fulfillment_status": None,
    "email": "customer@example.com",
    "customer": {"id": 111, "first_name": "Test", "last_name": "User"},
    "line_items": [],
    "shipping_address": {
        "address1": "123 Test St",
        "city": "Mumbai",
        "country": "India",
        "country_code": "IN",
        "zip": "400001",
    },
}


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class WebhookIdempotencyTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.merchant = Merchant.objects.create(shop_domain="testshop.myshopify.com")
        self.body = json.dumps(ORDER_PAYLOAD).encode("utf-8")
        self.signature = _make_signature(self.body)

    def _post_webhook(self):
        return self.client.post(
            "/webhooks/shopify/orders/create/",
            data=self.body,
            content_type="application/json",
            HTTP_X_SHOPIFY_HMAC_SHA256=self.signature,
            HTTP_X_SHOPIFY_SHOP_DOMAIN="testshop.myshopify.com",
        )

    def test_webhook_creates_order(self):
        response = self._post_webhook()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 1)

    def test_duplicate_webhook_does_not_create_duplicate_order(self):
        """Shopify sends the same webhook twice — we must only create one order."""
        self._post_webhook()
        self._post_webhook()  # Send again
        self.assertEqual(Order.objects.count(), 1, "Duplicate webhook created a duplicate order!")

    def test_invalid_hmac_returns_401(self):
        response = self.client.post(
            "/webhooks/shopify/orders/create/",
            data=self.body,
            content_type="application/json",
            HTTP_X_SHOPIFY_HMAC_SHA256="invalidsignature",
            HTTP_X_SHOPIFY_SHOP_DOMAIN="testshop.myshopify.com",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(Order.objects.count(), 0)

    def test_missing_hmac_returns_401(self):
        response = self.client.post(
            "/webhooks/shopify/orders/create/",
            data=self.body,
            content_type="application/json",
            HTTP_X_SHOPIFY_SHOP_DOMAIN="testshop.myshopify.com",
        )
        self.assertEqual(response.status_code, 401)
