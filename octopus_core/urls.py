"""
Root URL configuration.
All API endpoints are versioned under /api/v1/.
Shopify OAuth endpoints are at /shopify/ (no version — Shopify controls the contract).
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # Versioned REST API
    path("api/v1/", include("octopus_core.api_router")),

    # Shopify OAuth (not versioned — Shopify dictates the redirect URLs)
    path("shopify/", include("apps.merchants.shopify_urls")),

    # Shopify Webhooks (separate — no auth, HMAC verified internally)
    path("webhooks/", include("apps.webhooks.urls")),
]
