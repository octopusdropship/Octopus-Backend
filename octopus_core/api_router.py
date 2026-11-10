"""
Central API v1 router.
One place to see every endpoint in the system.
"""
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────
    path("auth/", include("apps.authentication.urls")),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # ── Merchants ─────────────────────────────────────────────────────────
    path("merchants/", include("apps.merchants.urls")),

    # ── Products / Catalog ────────────────────────────────────────────────
    # path("products/", include("apps.products.urls")),

    # ── Orders ────────────────────────────────────────────────────────────
    path("orders/", include("apps.orders.urls")),

    # ── Support ───────────────────────────────────────────────────────────
    path("support/", include("apps.support.urls")),

    # ── Notifications ─────────────────────────────────────────────────────
    path("notifications/", include("apps.notifications.urls")),

    # ── Internal (Next.js server only, X-Internal-Api-Key) ────────────────
    path("internal/", include("apps.authentication.internal_urls")),
]
