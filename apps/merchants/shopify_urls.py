"""
Shopify OAuth URLs — outside API versioning because Shopify controls redirect URLs.
These are the install/callback endpoints for the Shopify App OAuth flow.
"""
from django.urls import path
from .shopify_views import ShopifyInstallView, ShopifyCallbackView

urlpatterns = [
    path("install/", ShopifyInstallView.as_view(), name="shopify_install"),
    path("callback/", ShopifyCallbackView.as_view(), name="shopify_callback"),
]
