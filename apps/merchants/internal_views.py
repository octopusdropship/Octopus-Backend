"""
Internal merchant API — called only by the Next.js server (X-Internal-Api-Key).

Replaces the Next.js app's reads/writes of the Supabase `users` table for a
store's category, approval and Octopus subscription state.
"""
from rest_framework import status
from rest_framework.response import Response

from apps.authentication.internal_views import InternalAPIView, shop_or_error
from apps.authentication.models import UserRole
from apps.authentication.serializers import MerchantBillingUpdateSerializer
from apps.authentication.services import apply_merchant_billing
from apps.authentication.views import validation_error_response
from .models import Merchant


def _merchant_payload(merchant):
    owner = (
        merchant.store_users.filter(role=UserRole.OWNER, is_active=True)
        .order_by("created_at")
        .values("id", "email", "name")
        .first()
    )
    return {
        "id": merchant.id,
        "shop_domain": merchant.shop_domain,
        "is_supplier": merchant.is_supplier,
        "category": merchant.category,
        "brand_name": merchant.brand_name,
        "brand_image": merchant.brand_image,
        "billing_status": merchant.billing_status,
        "billing_source": merchant.billing_source,
        "billing_plan": merchant.billing_plan,
        "is_approved": merchant.is_approved,
        "has_active_subscription": merchant.has_active_subscription,
        "owner": owner,
    }


class MerchantLookupView(InternalAPIView):
    """GET /api/v1/internal/merchants/lookup/?shop=mystore.myshopify.com"""

    def get(self, request):
        shop, error = shop_or_error(request.query_params.get("shop"))
        if error:
            return error
        merchant = Merchant.objects.filter(shop_domain=shop).first()
        if not merchant:
            return Response({"error": "Merchant not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_merchant_payload(merchant))


class MerchantBillingUpdateView(InternalAPIView):
    """
    POST /api/v1/internal/merchants/billing/
    {shop_domain, billing_status, billing_plan?, billing_source?, only_if_source?}
    """

    def post(self, request):
        serializer = MerchantBillingUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return validation_error_response(serializer.errors)
        data = serializer.validated_data
        shop, error = shop_or_error(data["shop_domain"])
        if error:
            return error

        merchant = Merchant.objects.filter(shop_domain=shop).first()
        if not merchant:
            return Response({"error": "Merchant not found."}, status=status.HTTP_404_NOT_FOUND)

        only_if_source = data.get("only_if_source")
        updated = only_if_source is None or merchant.billing_source == only_if_source
        if updated:
            apply_merchant_billing(
                merchant,
                billing_status=data["billing_status"],
                billing_plan=data.get("billing_plan"),
                billing_source=data.get("billing_source"),
            )
        return Response({**_merchant_payload(merchant), "updated": updated})
