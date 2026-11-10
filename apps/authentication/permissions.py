"""
Global RBAC permission classes.

Every DRF view should declare permission_classes explicitly.
Never rely on the global default alone for sensitive operations.
"""
import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission
from apps.authentication.models import UserRole


class IsMerchantAuthenticated(BasePermission):
    """
    User must be authenticated AND belong to a merchant.
    Prevents orphaned users (no merchant) from accessing any data.
    """
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.merchant_id is not None
        )


class IsOwner(BasePermission):
    """Only the OWNER role can perform this action (e.g. delete merchant, manage billing)."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.OWNER
        )


class IsAdminOrOwner(BasePermission):
    """ADMIN or OWNER can perform this action (e.g. manage team, push products)."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_admin_or_above
        )


class IsSupplier(BasePermission):
    """Request user's merchant must be flagged as a supplier."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.merchant is not None
            and request.user.merchant.is_supplier
        )


class IsSameMerchant(BasePermission):
    """
    Object-level permission: user can only access objects belonging
    to their own merchant. Use with has_object_permission().
    """
    def has_object_permission(self, request, view, obj):
        # obj must have a `merchant_id` attribute
        return str(getattr(obj, "merchant_id", None)) == str(
            request.user.merchant_id
        )


def has_valid_internal_key(request) -> bool:
    """True when the request carries the shared server-to-server secret."""
    expected = settings.INTERNAL_API_KEY
    received = request.META.get("HTTP_X_INTERNAL_API_KEY", "")
    return bool(expected) and hmac.compare_digest(received.encode(), expected.encode())


class HasInternalApiKey(BasePermission):
    """
    Only the Next.js server may call /api/v1/internal/. It authenticates with
    the X-Internal-Api-Key header; browsers never see that key.
    """
    def has_permission(self, request, view):
        return has_valid_internal_key(request)
