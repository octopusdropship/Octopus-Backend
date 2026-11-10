import uuid
from django.db import models


class TicketStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    RESOLVED = "RESOLVED", "Resolved"
    CLOSED = "CLOSED", "Closed"


class TicketPriority(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    URGENT = "URGENT", "Urgent"


class SupportTicket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(max_length=50, unique=True, db_index=True)
    vendor = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        related_name="support_tickets",
    )
    contact_number = models.CharField(max_length=20, null=True, blank=True)
    category = models.CharField(max_length=100, db_index=True)
    priority = models.CharField(
        max_length=20, choices=TicketPriority.choices, default=TicketPriority.MEDIUM
    )
    subject = models.CharField(max_length=500)
    description = models.TextField()
    reference_number = models.CharField(max_length=255, null=True, blank=True)
    attachment_name = models.CharField(max_length=255, null=True, blank=True)
    attachment_type = models.CharField(max_length=100, null=True, blank=True)
    attachment_data = models.TextField(null=True, blank=True)  # base64
    status = models.CharField(
        max_length=20, choices=TicketStatus.choices, default=TicketStatus.OPEN, db_index=True
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "support_tickets"
        indexes = [
            models.Index(fields=["vendor", "status", "created_at"]),
            models.Index(fields=["vendor", "category"]),
        ]

    def __str__(self):
        return f"[{self.ticket_number}] {self.subject}"


class SupportTicketReply(models.Model):
    class AuthorRole(models.TextChoices):
        VENDOR = "vendor", "Vendor"
        SUPPORT = "support", "Support"
        ADMIN = "admin", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        SupportTicket, on_delete=models.CASCADE, related_name="replies"
    )
    author_id = models.CharField(max_length=255)
    author_role = models.CharField(
        max_length=20, choices=AuthorRole.choices, db_index=True
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "support_ticket_replies"


class SupportCallRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    call_number = models.CharField(max_length=50, unique=True, db_index=True)
    vendor = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        related_name="support_call_requests",
    )
    contact_number = models.CharField(max_length=20, null=True, blank=True)
    category = models.CharField(max_length=100)
    description = models.TextField()
    status = models.CharField(max_length=20, default="OPEN", db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "support_call_requests"
