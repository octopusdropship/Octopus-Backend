"""
Webhook Celery tasks.

ARCHITECT NOTE on idempotency:
- get_or_create() on the unique constraint (merchant_shop_domain, merchant_shopify_order_id)
  guarantees that even if Shopify sends the same webhook twice (at-least-once delivery),
  we only create the order once.
- If `created` is False, the order already exists — we skip or update carefully.
"""
import logging
from decimal import Decimal

from celery import shared_task
from django.db import IntegrityError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def handle_order_created(self, shop_domain: str, payload: dict):
    """
    Process Shopify orders/create webhook.
    Idempotent: safe to call multiple times with same payload.
    """
    try:
        from apps.merchants.models import Merchant
        from apps.orders.models import Order, OrderItem
        from apps.products.models import Product, ProductVariant

        try:
            merchant = Merchant.objects.get(shop_domain=shop_domain)
        except Merchant.DoesNotExist:
            logger.error(f"handle_order_created: merchant {shop_domain} not found")
            return

        shopify_order_id = str(payload.get("id", ""))

        # ── Idempotency check ─────────────────────────────────────────────
        order, created = Order.objects.get_or_create(
            merchant_shop_domain=shop_domain,
            merchant_shopify_order_id=shopify_order_id,
            defaults={
                "merchant": merchant,
                "merchant_shopify_order_number": payload.get("order_number"),
                "shopify_created_at": payload.get("created_at"),
                "shopify_updated_at": payload.get("updated_at"),
                "currency": payload.get("currency", "INR"),
                "customer_total_amount": Decimal(
                    str(payload.get("total_price", "0"))
                ),
                "supplier_payable_amount": Decimal("0"),  # calculated separately
                "customer_payment_status": payload.get("financial_status", "pending"),
                "customer_fulfillment_status": payload.get(
                    "fulfillment_status", "unfulfilled"
                ) or "unfulfilled",
                "supplier_payment_status": "pending",
                "supplier_fulfillment_status": "unfulfilled",
                "source": "shopify",
                "shopify_customer_id": str(
                    (payload.get("customer") or {}).get("id", "")
                ),
                "shopify_customer_name": (
                    f"{(payload.get('customer') or {}).get('first_name', '')} "
                    f"{(payload.get('customer') or {}).get('last_name', '')}".strip()
                ),
                "shopify_customer_email": payload.get("email", ""),
                "shopify_customer_phone": payload.get("phone", ""),
                **_extract_shipping(payload),
            },
        )

        if not created:
            logger.info(
                f"handle_order_created: order {shopify_order_id} already exists — skipping"
            )
            return

        # ── Create order items ────────────────────────────────────────────
        for line_item in payload.get("line_items", []):
            _create_order_item(order, line_item)

        logger.info(
            f"Order created: #{order.merchant_shopify_order_number} for {shop_domain}"
        )

    except Exception as exc:
        logger.error(f"handle_order_created failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


def _extract_shipping(payload: dict) -> dict:
    addr = payload.get("shipping_address") or {}
    return {
        "shipping_address1": addr.get("address1", ""),
        "shipping_address2": addr.get("address2", "") or "",
        "shipping_city": addr.get("city", ""),
        "shipping_province": addr.get("province", ""),
        "shipping_province_code": addr.get("province_code", ""),
        "shipping_country": addr.get("country", ""),
        "shipping_country_code": addr.get("country_code", ""),
        "shipping_zip": addr.get("zip", ""),
    }


def _create_order_item(order, line_item: dict):
    from apps.orders.models import OrderItem
    from apps.products.models import Product, ProductVariant

    product_id = str(line_item.get("product_id", ""))
    variant_id = str(line_item.get("variant_id", ""))
    price = Decimal(str(line_item.get("price", "0")))
    qty = int(line_item.get("quantity", 1))

    try:
        product = Product.objects.get(id=product_id)
        variant = ProductVariant.objects.get(id=variant_id)
        OrderItem.objects.create(
            order=order,
            product=product,
            variant=variant,
            title=line_item.get("title", ""),
            sku=line_item.get("sku", ""),
            quantity=qty,
            customer_unit_price=price,
            supplier_unit_price=variant.supplier_price,
            customer_line_total=price * qty,
            supplier_line_total=variant.supplier_price * qty,
        )
    except (Product.DoesNotExist, ProductVariant.DoesNotExist):
        logger.warning(
            f"OrderItem skipped: product {product_id} or variant {variant_id} not in DB"
        )


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def handle_order_updated(self, shop_domain: str, payload: dict):
    try:
        from apps.orders.models import Order

        shopify_order_id = str(payload.get("id", ""))
        updated = Order.objects.filter(
            merchant_shop_domain=shop_domain,
            merchant_shopify_order_id=shopify_order_id,
        ).update(
            customer_payment_status=payload.get("financial_status", "pending"),
            customer_fulfillment_status=payload.get("fulfillment_status")
            or "unfulfilled",
            shopify_updated_at=payload.get("updated_at"),
        )
        if not updated:
            logger.warning(
                f"handle_order_updated: order {shopify_order_id} not found in DB"
            )
    except Exception as exc:
        logger.error(f"handle_order_updated failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def handle_order_cancelled(self, shop_domain: str, payload: dict):
    try:
        from apps.orders.models import Order

        shopify_order_id = str(payload.get("id", ""))
        Order.objects.filter(
            merchant_shop_domain=shop_domain,
            merchant_shopify_order_id=shopify_order_id,
        ).update(
            customer_fulfillment_status="cancelled",
            supplier_fulfillment_status="cancelled",
        )
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def handle_product_updated(self, shop_domain: str, payload: dict):
    """Update inventory quantities when supplier updates a product."""
    try:
        from apps.products.models import ProductVariant

        for variant in payload.get("variants", []):
            variant_id = str(variant.get("id", ""))
            inventory_qty = variant.get("inventory_quantity", 0)
            ProductVariant.objects.filter(id=variant_id).update(
                inventory_quantity=inventory_qty
            )
    except Exception as exc:
        raise self.retry(exc=exc)
