from django.contrib import admin

from .models import Merchant, ShopifySession


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = (
        "shop_domain", "brand_name", "category", "is_supplier",
        "billing_status", "billing_source", "billing_plan", "created_at",
    )
    list_filter = ("is_supplier", "billing_status", "billing_source", "category")
    search_fields = ("shop_domain", "brand_name", "category")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)

    fieldsets = (
        ("Identity", {"fields": ("id", "shop_domain", "brand_name", "brand_image", "category")}),
        ("Shopify", {"fields": ("access_token", "is_supplier", "product_sync")}),
        ("Billing", {
            "fields": (
                "billing_source", "billing_status", "billing_plan",
                "shopify_subscription_id", "billing_activated_at",
            )
        }),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(ShopifySession)
class ShopifySessionAdmin(admin.ModelAdmin):
    list_display = ("id", "merchant", "is_online", "expires", "scope")
    list_filter = ("is_online",)
    search_fields = ("id", "merchant__shop_domain")
    raw_id_fields = ("merchant",)
