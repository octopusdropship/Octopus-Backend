from rest_framework import serializers
from .models import SupportTicket, SupportCallRequest


class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = (
            "id", "ticket_number", "category", "priority",
            "subject", "description", "status", "contact_number",
            "reference_number", "created_at", "updated_at",
        )
        read_only_fields = ("id", "ticket_number", "status", "created_at", "updated_at")


class SupportCallRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportCallRequest
        fields = (
            "id", "call_number", "category", "description",
            "contact_number", "status", "created_at",
        )
        read_only_fields = ("id", "call_number", "status", "created_at")
