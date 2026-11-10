"""
Orders and payment transaction models.

ARCHITECT NOTE:
- Order.id is a UUID — we generate our own IDs.
- merchantShopifyOrderId is Shopify's order ID on the RETAILER's store.
- supplierShopifyOrderId is Shopify's order ID on the SUPPLIER's store (set after forwarding).
- The unique constraint on (merchant_shop_domain, merchant_shopify_order_id)
  is the idempotency key for webhook deduplication.
"""
import uuid
from django.db import models


class Order(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        REFUNDED = "refunded", "Refunded"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially Refunded"

    class FulfillmentStatus(models.TextChoices):
        UNFULFILLED = "unfulfilled", "Unfulfilled"
        FULFILLED = "fulfilled", "Fulfilled"
        PARTIAL = "partial", "Partial"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        related_name="orders",
    )
    merchant_shop_domain = models.CharField(max_length=255, db_index=True)
    merchant_shopify_order_id = models.CharField(max_length=255, db_index=True)
    merchant_shopify_order_number = models.IntegerField(null=True, blank=True)
    shopify_created_at = models.DateTimeField()
    shopify_updated_at = models.DateTimeField()

    # Supplier order (filled after order is forwarded to supplier)
    supplier_shopify_order_id = models.CharField(max_length=255, null=True, blank=True)
    supplier_shopify_order_number = models.IntegerField(null=True, blank=True)

    # Financials
    currency = models.CharField(max_length=10, default="INR")
    customer_total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    supplier_payable_amount = models.DecimalField(max_digits=12, decimal_places=2)

    # Status
    customer_payment_status = models.CharField(
        max_length=30, choices=PaymentStatus.choices, db_index=True
    )
    customer_fulfillment_status = models.CharField(
        max_length=30, choices=FulfillmentStatus.choices, db_index=True
    )
    supplier_payment_status = models.CharField(max_length=30, db_index=True)
    supplier_fulfillment_status = models.CharField(max_length=30, db_index=True)
    source = models.CharField(max_length=50, default="shopify")

    # Customer Details
    shopify_customer_id = models.CharField(max_length=255)
    shopify_customer_name = models.CharField(max_length=255, null=True, blank=True)
    shopify_customer_email = models.CharField(max_length=255)
    shopify_customer_phone = models.CharField(max_length=50, null=True, blank=True)

    # Shipping Address
    shipping_address1 = models.CharField(max_length=500)
    shipping_address2 = models.CharField(max_length=500, blank=True)
    shipping_city = models.CharField(max_length=255)
    shipping_province = models.CharField(max_length=255, null=True, blank=True)
    shipping_province_code = models.CharField(max_length=20, null=True, blank=True)
    shipping_country = models.CharField(max_length=255)
    shipping_country_code = models.CharField(max_length=10)
    shipping_zip = models.CharField(max_length=20)

    # Refund tracking
    supplier_refund_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    supplier_refund_transaction_id = models.CharField(
        max_length=255, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders"
        # This unique constraint IS the idempotency key for webhook dedup
        unique_together = ("merchant_shop_domain", "merchant_shopify_order_id")
        indexes = [
            models.Index(fields=["merchant", "customer_payment_status"]),
            models.Index(fields=["merchant", "created_at"]),
            models.Index(fields=["merchant_shop_domain", "merchant_shopify_order_id"]),
        ]

    def __str__(self):
        return f"Order #{self.merchant_shopify_order_number} — {self.merchant_shop_domain}"


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="order_items"
    )
    variant = models.ForeignKey(
        "products.ProductVariant", on_delete=models.PROTECT, related_name="order_items"
    )
    title = models.CharField(max_length=500)
    sku = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.IntegerField()
    customer_unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    supplier_unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    customer_line_total = models.DecimalField(max_digits=12, decimal_places=2)
    supplier_line_total = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_items"


class PaymentTransaction(models.Model):
    class TransactionType(models.TextChoices):
        CHARGE = "charge", "Charge"
        REFUND = "refund", "Refund"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="payment_transactions"
    )
    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        related_name="payment_transactions",
    )
    type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10)
    status = models.CharField(max_length=50)
    gateway = models.CharField(max_length=50)
    gateway_txn_id = models.CharField(max_length=255, null=True, blank=True)
    gateway_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_transactions"
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["merchant", "created_at"]),
        ]
