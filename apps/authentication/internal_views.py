"""
Internal account API — called only by the Next.js server (X-Internal-Api-Key).

These endpoints replace the Supabase admin API the Next.js app used:
provisioning store owners, inviting/managing team members and reading a
user's profile by id.
"""
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import HasInternalApiKey
from .serializers import (
    AccountApprovalSerializer,
    AccountSerializer,
    InviteTeamMemberSerializer,
    ProvisionStoreOwnerSerializer,
    RegisterAccountSerializer,
    UpdateAccountSerializer,
    UpdateTeamMemberSerializer,
    UserProfileSerializer,
)
from .services import (
    AccountConflict,
    AccountNotFound,
    delete_account,
    invite_team_member,
    list_accounts,
    normalize_shop_domain,
    provision_store_owner,
    register_account,
    remove_team_member,
    set_account_approval,
    update_account,
    update_team_member,
)
from .views import validation_error_response

User = get_user_model()


class InternalAPIView(APIView):
    authentication_classes = []
    permission_classes = [HasInternalApiKey]
    throttle_classes = []  # server-to-server; the Next.js app throttles end users


def shop_or_error(value):
    shop = normalize_shop_domain(value)
    if not shop:
        return None, Response(
            {"error": "A valid Shopify shop domain is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return shop, None


class ProvisionStoreOwnerView(InternalAPIView):
    """POST /api/v1/internal/users/provision/"""

    def post(self, request):
        serializer = ProvisionStoreOwnerSerializer(data=request.data)
        if not serializer.is_valid():
            return validation_error_response(serializer.errors)
        data = serializer.validated_data
        shop, error = shop_or_error(data["shop_domain"])
        if error:
            return error

        try:
            user, created, invited = provision_store_owner(
                email=data["email"],
                shop_domain=shop,
                password=data.get("password"),
                name=data["name"],
                billing_status=data["billing_status"],
                billing_plan=data["billing_plan"],
                billing_source=data["billing_source"],
                is_approved=data["is_approved"],
                send_invite_email=data["send_invite"],
            )
        except AccountConflict as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(
            {"user": UserProfileSerializer(user).data, "created": created, "invited": invited},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class UserDetailView(InternalAPIView):
    """GET /api/v1/internal/users/<uuid>/"""

    def get(self, request, pk):
        user = get_object_or_404(User.objects.select_related("merchant"), pk=pk)
        return Response(UserProfileSerializer(user).data)


class InviteTeamMemberView(InternalAPIView):
    """POST /api/v1/internal/team/invite/"""

    def post(self, request):
        serializer = InviteTeamMemberSerializer(data=request.data)
        if not serializer.is_valid():
            return validation_error_response(serializer.errors)
        data = serializer.validated_data
        shop, error = shop_or_error(data["shop_domain"])
        if error:
            return error

        try:
            user, created, invited = invite_team_member(
                email=data["email"], shop_domain=shop, role=data["role"], name=data["name"]
            )
        except AccountConflict as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(
            {"user": UserProfileSerializer(user).data, "created": created, "invited": invited},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class TeamMemberDetailView(InternalAPIView):
    """
    PATCH  /api/v1/internal/team/<uuid>/   {shop_domain, role}
    DELETE /api/v1/internal/team/<uuid>/?shop_domain=...
    Both are scoped to the shop so one store can never touch another's users.
    """

    def patch(self, request, pk):
        serializer = UpdateTeamMemberSerializer(data=request.data)
        if not serializer.is_valid():
            return validation_error_response(serializer.errors)
        shop, error = shop_or_error(serializer.validated_data["shop_domain"])
        if error:
            return error
        try:
            user = update_team_member(
                user_id=pk, shop_domain=shop, role=serializer.validated_data["role"]
            )
        except AccountNotFound as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserProfileSerializer(user).data)

    def delete(self, request, pk):
        shop, error = shop_or_error(request.query_params.get("shop_domain"))
        if error:
            return error
        try:
            remove_team_member(user_id=pk, shop_domain=shop)
        except AccountNotFound as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Website accounts ──────────────────────────────────────────────────────────

class AccountListView(InternalAPIView):
    """
    GET  /api/v1/internal/accounts/?user_type=&approval=&search=
    POST /api/v1/internal/accounts/   website signup (starts unapproved)
    """

    def get(self, request):
        accounts = list_accounts(
            user_type=request.query_params.get("user_type", "all"),
            approval=request.query_params.get("approval", "all"),
            search=request.query_params.get("search", ""),
        )
        return Response({"accounts": AccountSerializer(accounts, many=True).data})

    def post(self, request):
        serializer = RegisterAccountSerializer(data=request.data)
        if not serializer.is_valid():
            return validation_error_response(serializer.errors)
        data = serializer.validated_data
        shop, error = shop_or_error(data["shop_domain"])
        if error:
            return error
        try:
            user = register_account(**{**data, "shop_domain": shop})
        except AccountConflict as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({"account": AccountSerializer(user).data}, status=status.HTTP_201_CREATED)


class AccountDetailView(InternalAPIView):
    """
    PATCH  /api/v1/internal/accounts/<uuid>/   staff edits
    DELETE /api/v1/internal/accounts/<uuid>/   removes the account and its store
    """

    def patch(self, request, pk):
        serializer = UpdateAccountSerializer(data=request.data)
        if not serializer.is_valid():
            return validation_error_response(serializer.errors)
        changes = dict(serializer.validated_data)
        if "shop_domain" in changes:
            shop, error = shop_or_error(changes["shop_domain"])
            if error:
                return error
            changes["shop_domain"] = shop
        try:
            user = update_account(pk, **changes)
        except AccountNotFound as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except AccountConflict as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({"account": AccountSerializer(user).data})

    def delete(self, request, pk):
        try:
            delete_account(pk)
        except AccountNotFound as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccountApprovalView(InternalAPIView):
    """POST /api/v1/internal/accounts/<uuid>/approval/  {approved: bool}"""

    def post(self, request, pk):
        serializer = AccountApprovalSerializer(data=request.data)
        if not serializer.is_valid():
            return validation_error_response(serializer.errors)
        try:
            user = set_account_approval(pk, serializer.validated_data["approved"])
        except AccountNotFound as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except AccountConflict as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({"account": AccountSerializer(user).data})
