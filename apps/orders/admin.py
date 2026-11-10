from django.contrib import admin

from .models import Order, OrderItem, PaymentTransaction


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("id", "product", "variant", "sku", "quantity",
                       "customer_unit_price", "supplier_unit_price",
                       "customer_line_total", "supplier_line_total", "created_at")
    can_delete = False


class PaymentTransactionInline(admin.TabularInline):
    model = PaymentTransaction
    extra = 0
    readonly_fields = ("id", "type", "amount", "currency", "status",
                       "gateway", "gateway_txn_id", "created_at")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "merchant_shopify_order_number", "merchant_shop_domain", "merchant",
        "customer_payment_status", "customer_fulfillment_status",
        "customer_total_amount", "currency", "created_at",
    )
    list_filter = (
        "customer_payment_status", "customer_fulfillment_status",
        "supplier_payment_status", "source",
    )
    search_fields = (
        "merchant_shop_domain", "merchant_shopify_order_id",
        "shopify_customer_email", "shopify_customer_name",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)
    raw_id_fields = ("merchant",)
    inlines = [OrderItemInline, PaymentTransactionInline]

    fieldsets = (
        ("Order IDs", {
            "fields": (
                "id", "merchant", "merchant_shop_domain",
                "merchant_shopify_order_id", "merchant_shopify_order_number",
                "supplier_shopify_order_id", "supplier_shopify_order_number",
            )
        }),
        ("Financials", {
            "fields": ("currency", "customer_total_amount", "supplier_payable_amount")
        }),
        ("Status", {
            "fields": (
                "customer_payment_status", "customer_fulfillment_status",
                "supplier_payment_status", "supplier_fulfillment_status", "source",
            )
        }),
        ("Customer", {
            "fields": (
                "shopify_customer_id", "shopify_customer_name",
                "shopify_customer_email", "shopify_customer_phone",
            )
        }),
        ("Shipping Address", {
            "fields": (
                "shipping_address1", "shipping_address2", "shipping_city",
                "shipping_province", "shipping_province_code",
                "shipping_country", "shipping_country_code", "shipping_zip",
            )
        }),
        ("Refund", {
            "fields": ("supplier_refund_amount", "supplier_refund_transaction_id"),
            "classes": ("collapse",),
        }),
        ("Timestamps", {"fields": ("shopify_created_at", "shopify_updated_at", "created_at", "updated_at")}),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "title", "sku", "quantity",
                    "customer_unit_price", "supplier_unit_price", "created_at")
    search_fields = ("title", "sku", "order__merchant_shop_domain")
    readonly_fields = ("id", "created_at")
    raw_id_fields = ("order", "product", "variant")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("order", "merchant", "type", "amount", "currency",
                    "status", "gateway", "gateway_txn_id", "created_at")
    list_filter = ("type", "status", "gateway")
    search_fields = ("gateway_txn_id", "merchant__shop_domain")
    readonly_fields = ("id", "created_at")
    raw_id_fields = ("order", "merchant")
