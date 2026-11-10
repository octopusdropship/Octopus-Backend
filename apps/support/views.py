import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from rest_framework import status

from apps.authentication.permissions import IsMerchantAuthenticated
from .models import SupportTicket, SupportCallRequest
from .serializers import SupportTicketSerializer, SupportCallRequestSerializer


class SupportTicketListView(APIView):
    permission_classes = [IsMerchantAuthenticated]

    def get(self, request):
        tickets = SupportTicket.objects.filter(
            vendor=request.user.merchant
        ).order_by("-created_at")
        return Response(SupportTicketSerializer(tickets, many=True).data)

    def post(self, request):
        serializer = SupportTicketSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        ticket_number = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        serializer.save(vendor=request.user.merchant, ticket_number=ticket_number)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SupportTicketDetailView(APIView):
    permission_classes = [IsMerchantAuthenticated]

    def get(self, request, pk):
        ticket = get_object_or_404(SupportTicket, pk=pk, vendor=request.user.merchant)
        return Response(SupportTicketSerializer(ticket).data)


class SupportCallRequestView(APIView):
    permission_classes = [IsMerchantAuthenticated]

    def post(self, request):
        serializer = SupportCallRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        call_number = f"CALL-{uuid.uuid4().hex[:8].upper()}"
        serializer.save(vendor=request.user.merchant, call_number=call_number)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
