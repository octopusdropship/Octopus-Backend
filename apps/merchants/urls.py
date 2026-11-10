from django.urls import path
from .views import MerchantSettingsView, MerchantBillingView, MerchantDashboardView

urlpatterns = [
    path("settings/", MerchantSettingsView.as_view(), name="merchant_settings"),
    path("billing/", MerchantBillingView.as_view(), name="merchant_billing"),
    path("dashboard/", MerchantDashboardView.as_view(), name="merchant_dashboard"),
]
