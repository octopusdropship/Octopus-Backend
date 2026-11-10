from django.contrib import admin

from .models import (
    Collection,
    MerchantProduct,
    MerchantVariant,
    Product,
    ProductCollection,
    ProductOption,
    ProductVariant,
    VariantOptionValue,
)


class ProductOptionInline(admin.TabularInline):
    model = ProductOption
    extra = 0
    readonly_fields = ("id",)


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    readonly_fields = ("id", "created_at", "updated_at")
    fields = ("id", "sku", "supplier_price", "compare_at_price",
              "inventory_quantity", "is_active", "created_at")


class MerchantVariantInline(admin.TabularInline):
    model = MerchantVariant
    extra = 0
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("title", "supplier_shopify_id", "handle")
    search_fields = ("title", "supplier_shopify_id", "handle")
    readonly_fields = ("id",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "title", "merchant", "category", "base_price",
        "total_inventory", "is_active", "is_trending", "updated_at",
    )
    list_filter = ("is_active", "is_trending", "category")
    search_fields = ("title", "id", "merchant__shop_domain", "handle")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-updated_at",)
    raw_id_fields = ("merchant",)
    inlines = [ProductOptionInline, ProductVariantInline]

    fieldsets = (
        ("Identity", {"fields": ("id", "merchant", "title", "handle", "description")}),
        ("Categorisation", {"fields": ("category",)}),
        ("Pricing & Inventory", {"fields": ("base_price", "total_inventory")}),
        ("Flags", {"fields": ("is_active", "is_trending")}),
        ("Media", {"fields": ("images",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )



@admin.register(ProductCollection)
class ProductCollectionAdmin(admin.ModelAdmin):
    list_display = ("product", "collection")
    raw_id_fields = ("product", "collection")
    search_fields = ("product__title", "collection__title")


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = (
        "id", "product", "sku", "supplier_price",
        "inventory_quantity", "is_active", "updated_at",
    )
    list_filter = ("is_active",)
    search_fields = ("id", "sku", "product__title")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("product",)


@admin.register(ProductOption)
class ProductOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "position")
    search_fields = ("name", "product__title")
    raw_id_fields = ("product",)
    readonly_fields = ("id",)


@admin.register(VariantOptionValue)
class VariantOptionValueAdmin(admin.ModelAdmin):
    list_display = ("variant", "option", "value", "created_at")
    search_fields = ("value", "variant__id", "option__name")
    raw_id_fields = ("variant", "option")
    readonly_fields = ("id", "created_at")


@admin.register(MerchantProduct)
class MerchantProductAdmin(admin.ModelAdmin):
    list_display = ("product", "merchant", "shopify_product_id", "pushed_at", "created_at")
    search_fields = ("product__title", "merchant__shop_domain", "shopify_product_id")
    readonly_fields = ("id", "created_at")
    raw_id_fields = ("merchant", "product")
    ordering = ("-created_at",)
    inlines = [MerchantVariantInline]


@admin.register(MerchantVariant)
class MerchantVariantAdmin(admin.ModelAdmin):
    list_display = (
        "merchant_product", "supplier_variant",
        "shopify_variant_id", "margin_percent", "created_at",
    )
    search_fields = ("shopify_variant_id", "merchant_product__merchant__shop_domain")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("merchant_product", "supplier_variant")
