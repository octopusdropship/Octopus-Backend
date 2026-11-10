import uuid
from django.db import models


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
    )
    type = models.CharField(max_length=100)
    category = models.CharField(max_length=100, db_index=True)
    title = models.CharField(max_length=500)
    message = models.TextField()
    entity_type = models.CharField(max_length=100, null=True, blank=True)
    entity_id = models.CharField(max_length=255, null=True, blank=True)
    redirect_url = models.CharField(max_length=1000, null=True, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notifications"
        indexes = [
            models.Index(fields=["merchant", "is_read", "created_at"]),
            models.Index(fields=["merchant", "category", "created_at"]),
        ]

    def __str__(self):
        return f"{self.title} → {self.merchant}"


class NotificationEventLog(models.Model):
    """
    Deduplication log for system-generated notification events.
    Same event_key = same notification was already created.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_key = models.CharField(max_length=500, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notification_event_log"
