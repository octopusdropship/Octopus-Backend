from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import StoreUser


@admin.register(StoreUser)
class StoreUserAdmin(BaseUserAdmin):
    list_display = ("email", "name", "role", "merchant", "is_active", "is_staff", "created_at")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "name", "merchant__shop_domain")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        ("Personal Info", {"fields": ("name",)}),
        ("Role & Merchant", {"fields": ("role", "merchant")}),
        ("Status", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Password Reset", {"fields": ("reset_token", "reset_token_expires")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "name", "role", "merchant", "password1", "password2"),
        }),
    )
