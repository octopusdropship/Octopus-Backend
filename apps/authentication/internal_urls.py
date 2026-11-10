"""Internal (server-to-server) routes — see internal_views.py."""
from django.urls import path

from apps.merchants.internal_views import MerchantBillingUpdateView, MerchantLookupView
from .internal_views import (
    AccountApprovalView,
    AccountDetailView,
    AccountListView,
    InviteTeamMemberView,
    ProvisionStoreOwnerView,
    TeamMemberDetailView,
    UserDetailView,
)

urlpatterns = [
    path("users/provision/", ProvisionStoreOwnerView.as_view(), name="internal_provision_owner"),
    path("users/<uuid:pk>/", UserDetailView.as_view(), name="internal_user_detail"),
    path("team/invite/", InviteTeamMemberView.as_view(), name="internal_team_invite"),
    path("team/<uuid:pk>/", TeamMemberDetailView.as_view(), name="internal_team_member"),
    path("accounts/", AccountListView.as_view(), name="internal_accounts"),
    path("accounts/<uuid:pk>/", AccountDetailView.as_view(), name="internal_account_detail"),
    path(
        "accounts/<uuid:pk>/approval/",
        AccountApprovalView.as_view(),
        name="internal_account_approval",
    ),
    path("merchants/lookup/", MerchantLookupView.as_view(), name="internal_merchant_lookup"),
    path("merchants/billing/", MerchantBillingUpdateView.as_view(), name="internal_merchant_billing"),
]
