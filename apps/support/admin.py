from django.contrib import admin

from .models import SupportCallRequest, SupportTicket, SupportTicketReply


class SupportTicketReplyInline(admin.TabularInline):
    model = SupportTicketReply
    extra = 0
    readonly_fields = ("id", "author_id", "author_role", "message", "is_read", "created_at")
    can_delete = False


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_number", "vendor", "category", "priority",
        "status", "subject", "created_at",
    )
    list_filter = ("status", "priority", "category")
    search_fields = ("ticket_number", "subject", "vendor__shop_domain", "reference_number")
    readonly_fields = ("id", "created_at", "updated_at", "resolved_at")
    ordering = ("-created_at",)
    raw_id_fields = ("vendor",)
    inlines = [SupportTicketReplyInline]

    fieldsets = (
        ("Ticket Info", {
            "fields": ("id", "ticket_number", "vendor", "contact_number")
        }),
        ("Details", {
            "fields": ("category", "priority", "subject", "description", "reference_number")
        }),
        ("Attachment", {
            "fields": ("attachment_name", "attachment_type", "attachment_data"),
            "classes": ("collapse",),
        }),
        ("Status", {"fields": ("status", "resolved_at")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(SupportTicketReply)
class SupportTicketReplyAdmin(admin.ModelAdmin):
    list_display = ("ticket", "author_role", "author_id", "is_read", "created_at")
    list_filter = ("author_role", "is_read")
    search_fields = ("author_id", "message", "ticket__ticket_number")
    readonly_fields = ("id", "created_at")
    raw_id_fields = ("ticket",)


@admin.register(SupportCallRequest)
class SupportCallRequestAdmin(admin.ModelAdmin):
    list_display = (
        "call_number", "vendor", "category", "status",
        "contact_number", "created_at",
    )
    list_filter = ("status", "category")
    search_fields = ("call_number", "vendor__shop_domain", "contact_number")
    readonly_fields = ("id", "created_at", "updated_at", "resolved_at")
    ordering = ("-created_at",)
    raw_id_fields = ("vendor",)

    fieldsets = (
        ("Call Info", {"fields": ("id", "call_number", "vendor", "contact_number")}),
        ("Details", {"fields": ("category", "description")}),
        ("Status", {"fields": ("status", "resolved_at")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
