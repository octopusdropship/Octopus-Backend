"""Order views — merchant-scoped, no cross-tenant data leaks."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404

from apps.authentication.permissions import IsMerchantAuthenticated
from .models import Order
from .serializers import OrderListSerializer, OrderDetailSerializer


class OrderListView(APIView):
    """GET /api/v1/orders/ — only returns orders for the requesting merchant."""
    permission_classes = [IsMerchantAuthenticated]

    def get(self, request):
        # CRITICAL: always filter by merchant — never return all orders
        orders = Order.objects.filter(
            merchant=request.user.merchant
        ).order_by("-created_at")
        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data)


class OrderDetailView(APIView):
    """GET /api/v1/orders/<uuid>/"""
    permission_classes = [IsMerchantAuthenticated]

    def get(self, request, pk):
        # get_object_or_404 with merchant filter prevents IDOR attacks
        order = get_object_or_404(Order, pk=pk, merchant=request.user.merchant)
        serializer = OrderDetailSerializer(order)
        return Response(serializer.data)
