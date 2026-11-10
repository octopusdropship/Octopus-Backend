from django.urls import path
from .views import ShopifyWebhookView

urlpatterns = [
    # topic examples: orders/create, orders/updated, products/update
    path("shopify/<path:topic>/", ShopifyWebhookView.as_view(), name="shopify_webhook"),
]
