"""
Merchant models.

ARCHITECT NOTE:
Merchant is the root multi-tenant entity. Every other model in the system
traces back to a Merchant via foreign key. This is your data isolation boundary.
NEVER return data from one merchant in another merchant's API response.
"""
import uuid
from django.db import models


class BillingStatus(models.TextChoices):
    INACTIVE = "inactive", "Inactive"
    ACTIVE = "active", "Active"
    CANCELLED = "cancelled", "Cancelled"
    PAST_DUE = "past_due", "Past Due"


class BillingSource(models.TextChoices):
    SHOPIFY = "shopify", "Shopify"
    OCTOPUS = "octopus", "Octopus"
    RAZORPAY = "razorpay", "Razorpay"
    NONE = "none", "None"


class Merchant(models.Model):
    """
    One Merchant = one Shopify store.
    shop_domain is the unique identifier — e.g. 'mystore.myshopify.com'.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop_domain = models.CharField(max_length=255, unique=True, db_index=True)
    access_token = models.CharField(max_length=512, null=True, blank=True)
    is_supplier = models.BooleanField(default=False, db_index=True)
    product_sync = models.BooleanField(default=False)

    # Categorisation
    category = models.CharField(max_length=100, null=True, blank=True, db_index=True)

    # Brand Identity
    brand_name = models.CharField(max_length=255, null=True, blank=True)
    brand_image = models.URLField(max_length=1000, null=True, blank=True)

    # Billing
    billing_source = models.CharField(
        max_length=20,
        choices=BillingSource.choices,
        default=BillingSource.NONE,
    )
    billing_status = models.CharField(
        max_length=20,
        choices=BillingStatus.choices,
        default=BillingStatus.INACTIVE,
        db_index=True,
    )
    billing_plan = models.CharField(max_length=100, null=True, blank=True)
    shopify_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    billing_activated_at = models.DateTimeField(null=True, blank=True)
    # Octopus staff can withhold access even while billing is active.
    is_approved = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "merchants"
        indexes = [
            models.Index(fields=["is_supplier", "category"]),
            models.Index(fields=["billing_status", "category"]),
        ]

    def __str__(self):
        return self.shop_domain

    @property
    def is_billing_active(self):
        return self.billing_status == BillingStatus.ACTIVE

    @property
    def has_active_subscription(self):
        return self.is_approved and self.is_billing_active


class ShopifySession(models.Model):
    """
    Stores Shopify OAuth access tokens per shop.
    Replaces the Prisma 'Session' model.
    """
    id = models.CharField(max_length=255, primary_key=True)  # Shopify session ID
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="sessions",
        to_field="shop_domain",
    )
    state = models.CharField(max_length=255)
    is_online = models.BooleanField(default=False)
    scope = models.TextField(null=True, blank=True)
    expires = models.DateTimeField(null=True, blank=True)
    access_token = models.CharField(max_length=512)

    class Meta:
        db_table = "shopify_sessions"
