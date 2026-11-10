"""
Authentication serializers.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.authentication.services import TEAM_ROLES

User = get_user_model()


class MerchantSummarySerializer(serializers.Serializer):
    """The store fields the Next.js app needs at login and for billing checks."""
    id = serializers.UUIDField()
    shop_domain = serializers.CharField()
    is_supplier = serializers.BooleanField()
    category = serializers.CharField(allow_null=True)
    brand_name = serializers.CharField(allow_null=True)
    brand_image = serializers.CharField(allow_null=True)
    billing_status = serializers.CharField()
    billing_source = serializers.CharField()
    billing_plan = serializers.CharField(allow_null=True)
    is_approved = serializers.BooleanField()
    has_active_subscription = serializers.BooleanField()


class UserProfileSerializer(serializers.ModelSerializer):
    merchant_id = serializers.UUIDField(source="merchant.id", read_only=True, default=None)
    merchant_shop = serializers.CharField(
        source="merchant.shop_domain", read_only=True, default=None
    )
    merchant = MerchantSummarySerializer(read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "name",
            "role",
            "user_type",
            "merchant_id",
            "merchant_shop",
            "merchant",
            "created_at",
        )
        read_only_fields = ("id", "email", "role", "user_type", "created_at")


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate(self, attrs):
        validate_password(attrs["new_password"], self.context["request"].user)
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)


# ── Internal API (Next.js server → Django) ────────────────────────────────────

class ProvisionStoreOwnerSerializer(serializers.Serializer):
    email = serializers.EmailField()
    shop_domain = serializers.CharField()
    password = serializers.CharField(required=False, allow_blank=False, min_length=8)
    name = serializers.CharField(required=False, allow_blank=True, default="")
    billing_status = serializers.CharField(required=False, default="active")
    billing_plan = serializers.CharField(required=False, allow_blank=True, default="pro")
    billing_source = serializers.ChoiceField(
        choices=["octopus", "shopify", "razorpay", "none"], required=False, default="octopus"
    )
    is_approved = serializers.BooleanField(required=False, default=True)
    send_invite = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if not attrs.get("password") and not attrs["send_invite"]:
            raise serializers.ValidationError("Password is required when send_invite is false.")
        return attrs


class InviteTeamMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    shop_domain = serializers.CharField()
    name = serializers.CharField(required=False, allow_blank=True, default="")
    role = serializers.ChoiceField(choices=[r.value for r in TEAM_ROLES])


class UpdateTeamMemberSerializer(serializers.Serializer):
    shop_domain = serializers.CharField()
    role = serializers.ChoiceField(choices=[r.value for r in TEAM_ROLES])


class MerchantBillingUpdateSerializer(serializers.Serializer):
    shop_domain = serializers.CharField()
    billing_status = serializers.CharField()
    billing_plan = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    billing_source = serializers.ChoiceField(
        choices=["octopus", "shopify", "razorpay", "none"], required=False
    )
    # Only apply the change when the stored source matches — lets a Shopify
    # cancellation lapse Shopify billing without touching a manual Octopus plan.
    only_if_source = serializers.CharField(required=False)



# ── Website accounts (Octopus website server → Django) ───────────────────────

PLAN_CHOICES = ["basic", "pro", "premium"]
BILLING_STATUS_CHOICES = ["inactive", "active", "cancelled", "past_due"]


class RegisterAccountSerializer(serializers.Serializer):
    """Website signup: a store picks basic/pro, a manufacturer (supplier) premium."""
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8)
    name = serializers.CharField(max_length=255)
    user_type = serializers.ChoiceField(choices=["store", "manufacturer"])
    shop_domain = serializers.CharField()
    category = serializers.CharField(max_length=100)
    billing_plan = serializers.ChoiceField(choices=PLAN_CHOICES)

    def validate(self, attrs):
        allowed = ["premium"] if attrs["user_type"] == "manufacturer" else ["basic", "pro"]
        if attrs["billing_plan"] not in allowed:
            raise serializers.ValidationError("That plan is not available for this account type.")
        return attrs


class UpdateAccountSerializer(serializers.Serializer):
    """Staff edits from the website admin panel; every field is optional."""
    name = serializers.CharField(max_length=255, required=False)
    email = serializers.EmailField(required=False)
    shop_domain = serializers.CharField(required=False)
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)
    user_type = serializers.ChoiceField(choices=["store", "manufacturer", "admin"], required=False)
    billing_plan = serializers.ChoiceField(choices=PLAN_CHOICES, required=False)
    billing_status = serializers.ChoiceField(choices=BILLING_STATUS_CHOICES, required=False)
    is_approved = serializers.BooleanField(required=False)


class AccountApprovalSerializer(serializers.Serializer):
    approved = serializers.BooleanField()


class AccountSerializer(serializers.ModelSerializer):
    """An account as the website admin panel shows it: the login plus its store."""
    shop_domain = serializers.CharField(source="merchant.shop_domain", default=None, read_only=True)
    category = serializers.CharField(source="merchant.category", default=None, read_only=True)
    billing_plan = serializers.CharField(source="merchant.billing_plan", default=None, read_only=True)
    billing_status = serializers.CharField(source="merchant.billing_status", default=None, read_only=True)
    # Staff accounts have no store and need no approval.
    is_approved = serializers.BooleanField(source="merchant.is_approved", default=True, read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "name",
            "user_type",
            "shop_domain",
            "category",
            "billing_plan",
            "billing_status",
            "is_approved",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
