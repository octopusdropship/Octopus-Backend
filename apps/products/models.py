"""
Products models.

ARCHITECT NOTE:
- Product.id and ProductVariant.id use Shopify's numeric string IDs (e.g. "9823456789")
  because they come directly from Shopify's API. This prevents ID mismatch bugs.
- All other models use UUIDs.
- MerchantProduct is the "push" record — it means a retailer has pushed a supplier product to their store.
- MerchantVariant holds the per-variant margin and the resulting Shopify variant ID on the retailer's store.
"""
import uuid
from django.db import models


class Collection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier_shopify_id = models.CharField(max_length=255, unique=True, db_index=True)
    title = models.CharField(max_length=500)
    handle = models.CharField(max_length=500, null=True, blank=True)
    image = models.URLField(max_length=1000, null=True, blank=True)

    class Meta:
        db_table = "collections"

    def __str__(self):
        return self.title


class Product(models.Model):
    """Supplier's product. One supplier merchant owns many products."""
    id = models.CharField(max_length=255, primary_key=True)  # Shopify numeric ID
    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        related_name="products",
        db_index=True,
    )
    title = models.CharField(max_length=500)
    description = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    handle = models.CharField(max_length=500, null=True, blank=True)
    is_trending = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_inventory = models.IntegerField(null=True, blank=True)
    images = models.JSONField(default=list)
    collections = models.ManyToManyField(
        Collection,
        through="ProductCollection",
        related_name="products",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"
        unique_together = ("merchant", "id")
        indexes = [
            models.Index(fields=["merchant", "is_active"]),
            models.Index(fields=["category", "is_active", "is_trending"]),
            models.Index(fields=["merchant", "category"]),
        ]

    def __str__(self):
        return self.title


class ProductCollection(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)

    class Meta:
        db_table = "product_collections"
        unique_together = ("product", "collection")


class ProductOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="options")
    name = models.CharField(max_length=255)
    values = models.JSONField(default=list)
    position = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "product_options"
        unique_together = ("product", "name")


class ProductVariant(models.Model):
    """Supplier's variant. Price here is the supplier's cost price."""
    id = models.CharField(max_length=255, primary_key=True)  # Shopify numeric ID
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants"
    )
    sku = models.CharField(max_length=255, null=True, blank=True)
    supplier_price = models.DecimalField(max_digits=12, decimal_places=2)
    compare_at_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    inventory_quantity = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    images = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_variants"
        indexes = [
            models.Index(fields=["product", "is_active"]),
        ]


class VariantOptionValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="option_values",
    )
    option = models.ForeignKey(
        ProductOption,
        on_delete=models.CASCADE,
        related_name="variant_values",
    )
    value = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "variant_option_values"
        unique_together = ("variant", "option")
        indexes = [
            models.Index(fields=["variant"]),
            models.Index(fields=["option"]),
        ]


class MerchantProduct(models.Model):
    """
    A retailer has pushed this supplier product to their Shopify store.
    shopify_product_id is the product ID on the RETAILER's store.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        related_name="merchant_products",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="merchant_products",
    )
    shopify_product_id = models.CharField(max_length=255, null=True, blank=True)
    pushed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "merchant_products"
        unique_together = ("product", "merchant")
        indexes = [
            models.Index(fields=["merchant", "product"]),
        ]


class MerchantVariant(models.Model):
    """
    Per-variant margin set by the retailer.
    shopify_variant_id is the variant ID on the RETAILER's store.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant_product = models.ForeignKey(
        MerchantProduct,
        on_delete=models.CASCADE,
        related_name="merchant_variants",
    )
    supplier_variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="merchant_variants",
    )
    shopify_variant_id = models.CharField(max_length=255)
    margin_percent = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "merchant_variants"
        unique_together = [
            ("merchant_product", "supplier_variant"),
            ("merchant_product", "shopify_variant_id"),
        ]
        indexes = [
            models.Index(fields=["merchant_product"]),
        ]
