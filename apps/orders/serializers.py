from rest_framework import serializers
from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "id", "title", "sku", "quantity",
            "customer_unit_price", "supplier_unit_price",
            "customer_line_total", "supplier_line_total",
        )


class OrderListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = (
            "id",
            "merchant_shopify_order_number",
            "shopify_customer_name",
            "shopify_customer_email",
            "customer_total_amount",
            "customer_payment_status",
            "customer_fulfillment_status",
            "created_at",
        )


class OrderDetailSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = "__all__"
