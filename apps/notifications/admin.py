from django.contrib import admin

from .models import Notification, NotificationEventLog


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "title", "merchant", "type", "category", "is_read", "created_at",
    )
    list_filter = ("type", "category", "is_read")
    search_fields = ("title", "message", "merchant__shop_domain")
    readonly_fields = ("id", "created_at", "updated_at", "read_at")
    ordering = ("-created_at",)
    raw_id_fields = ("merchant",)

    fieldsets = (
        ("Content", {"fields": ("id", "merchant", "type", "category", "title", "message")}),
        ("Entity Reference", {"fields": ("entity_type", "entity_id", "redirect_url")}),
        ("Status", {"fields": ("is_read", "read_at")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(NotificationEventLog)
class NotificationEventLogAdmin(admin.ModelAdmin):
    list_display = ("event_key", "created_at")
    search_fields = ("event_key",)
    readonly_fields = ("id", "created_at")
    ordering = ("-created_at",)
