from rest_framework import serializers
from .models import Merchant


class MerchantSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Merchant
        fields = (
            "id",
            "shop_domain",
            "category",
            "brand_name",
            "brand_image",
            "is_supplier",
            "product_sync",
        )
        read_only_fields = ("id", "shop_domain", "is_supplier")


class MerchantBillingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Merchant
        fields = (
            "billing_status",
            "billing_plan",
            "billing_source",
            "billing_activated_at",
            "shopify_subscription_id",
        )
        read_only_fields = fields
