"""
Shopify webhook receiver.

ARCHITECT NOTE:
1. HMAC verification happens FIRST — before any DB access.
   If signature is wrong, we return 401 immediately.
2. All processing is handed to Celery — the webhook view always returns 200
   within 5 seconds, otherwise Shopify retries and you get duplicate processing.
3. Idempotency is enforced in Celery tasks using get_or_create on the
   unique_together constraint on Order.
"""
import hashlib
import hmac
import base64
import json
import logging

from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .tasks import (
    handle_order_created,
    handle_order_updated,
    handle_order_cancelled,
    handle_product_updated,
)

logger = logging.getLogger(__name__)

WEBHOOK_TOPIC_HANDLERS = {
    "orders/create": handle_order_created,
    "orders/updated": handle_order_updated,
    "orders/cancelled": handle_order_cancelled,
    "products/update": handle_product_updated,
}


def _verify_shopify_hmac(body: bytes, hmac_header: str) -> bool:
    """
    Verify Shopify webhook HMAC-SHA256 signature.
    Returns True if valid, False otherwise.
    """
    if not hmac_header:
        return False
    computed = base64.b64encode(
        hmac.new(
            settings.SHOPIFY_API_SECRET.encode("utf-8"),
            body,
            digestmod=hashlib.sha256,
        ).digest()
    ).decode()
    return hmac.compare_digest(computed, hmac_header)


class ShopifyWebhookView(APIView):
    """
    POST /webhooks/shopify/<topic>/
    topic examples: orders/create, orders/updated, products/update
    """
    permission_classes = [AllowAny]

    def post(self, request, topic: str):
        # ── Step 1: Verify HMAC ───────────────────────────────────────────
        hmac_header = request.META.get("HTTP_X_SHOPIFY_HMAC_SHA256", "")
        if not _verify_shopify_hmac(request.body, hmac_header):
            logger.warning(f"Webhook HMAC verification failed for topic: {topic}")
            return Response({"error": "Unauthorized"}, status=401)

        # ── Step 2: Extract metadata ──────────────────────────────────────
        shop_domain = request.META.get("HTTP_X_SHOPIFY_SHOP_DOMAIN", "")
        if not shop_domain:
            return Response({"error": "Missing shop domain"}, status=400)

        # ── Step 3: Route to Celery task ──────────────────────────────────
        # Parse body once here, pass dict to task (JSON-serializable)
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return Response({"error": "Invalid JSON"}, status=400)

        handler = WEBHOOK_TOPIC_HANDLERS.get(topic)
        if handler:
            handler.delay(shop_domain, payload)
            logger.info(f"Webhook queued: {topic} from {shop_domain}")
        else:
            logger.info(f"Unhandled webhook topic: {topic} from {shop_domain}")

        # ── Step 4: Always return 200 fast ────────────────────────────────
        # Shopify considers anything other than 2xx a failure and will retry
        return Response(status=200)
