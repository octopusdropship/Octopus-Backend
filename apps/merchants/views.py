"""Merchant views — settings, billing, dashboard."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.authentication.permissions import IsMerchantAuthenticated, IsOwner
from .models import Merchant
from .serializers import MerchantSettingsSerializer, MerchantBillingSerializer


class MerchantSettingsView(APIView):
    """GET/PATCH /api/v1/merchants/settings/"""
    permission_classes = [IsMerchantAuthenticated]

    def get(self, request):
        serializer = MerchantSettingsSerializer(request.user.merchant)
        return Response(serializer.data)

    def patch(self, request):
        serializer = MerchantSettingsSerializer(
            request.user.merchant,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)


class MerchantBillingView(APIView):
    """GET /api/v1/merchants/billing/"""
    permission_classes = [IsMerchantAuthenticated]

    def get(self, request):
        serializer = MerchantBillingSerializer(request.user.merchant)
        return Response(serializer.data)


class MerchantDashboardView(APIView):
    """GET /api/v1/merchants/dashboard/ — summary stats."""
    permission_classes = [IsMerchantAuthenticated]

    def get(self, request):
        merchant = request.user.merchant
        from apps.orders.models import Order
        from apps.products.models import MerchantProduct

        order_qs = Order.objects.filter(merchant=merchant)
        return Response(
            {
                "total_orders": order_qs.count(),
                "total_pushed_products": MerchantProduct.objects.filter(
                    merchant=merchant
                ).count(),
                "billing_status": merchant.billing_status,
                "billing_plan": merchant.billing_plan,
            }
        )
