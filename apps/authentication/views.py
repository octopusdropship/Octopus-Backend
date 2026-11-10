"""
Authentication views.

Rate-limited strictly — login/password endpoints are the #1 target for bots.

There is deliberately no public registration endpoint: store owners are
provisioned by the subscription flow and team members by invite, both through
the internal API (see internal_views.py).
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .permissions import has_valid_internal_key
from .serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    UserProfileSerializer,
)
from .services import dispatch_task, get_user_for_token, issue_account_token
from apps.authentication.tasks import send_password_changed_email, send_password_reset_email

User = get_user_model()


class AuthRateThrottle(AnonRateThrottle):
    """
    10/min per client. Requests relayed by the Next.js server all share its IP,
    so for those the end user's IP comes from X-Client-IP — trusted only when
    the request also carries the internal API key.
    """
    rate = "10/min"

    def get_ident(self, request):
        client_ip = request.META.get("HTTP_X_CLIENT_IP", "").strip()
        if client_ip and has_valid_internal_key(request):
            return client_ip
        return super().get_ident(request)


def validation_error_response(errors):
    """
    Flatten DRF/Django validation errors into the `{"error": "..."}` shape
    the Next.js routes show to users, keeping the full detail under `errors`.
    """
    if isinstance(errors, dict):
        first = next(iter(errors.values()), ["Invalid request."])
    else:
        first = errors
    message = first[0] if isinstance(first, (list, tuple)) and first else first
    return Response(
        {"error": str(message), "errors": errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


class LoginView(APIView):
    """
    POST /api/v1/auth/login/
    Returns access + refresh JWT tokens and the user's profile with their store.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        email = str(request.data.get("email", "")).lower().strip()
        password = str(request.data.get("password", ""))

        if not email or not password:
            return Response(
                {"error": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.select_related("merchant").filter(
            email=email, is_active=True
        ).first()

        if user is None:
            # Hash anyway so a missing email takes as long as a wrong password
            User().set_password(password)
        # Same message for wrong email or wrong password — prevents user enumeration
        if user is None or not user.check_password(password):
            return Response(
                {"error": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserProfileSerializer(user).data,
            }
        )


class MeView(APIView):
    """GET /api/v1/auth/me/ — current user profile."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)


class ChangePasswordView(APIView):
    """POST /api/v1/auth/change-password/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return validation_error_response(serializer.errors)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        dispatch_task(send_password_changed_email, str(request.user.id))
        return Response({"detail": "Password changed successfully."})


class ForgotPasswordView(APIView):
    """
    POST /api/v1/auth/forgot-password/
    Always returns 200 even if email not found — prevents user enumeration.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return validation_error_response(serializer.errors)

        email = serializer.validated_data["email"].lower()
        user = User.objects.filter(email=email, is_active=True).first()
        if user:
            token = issue_account_token(user, settings.PASSWORD_RESET_TOKEN_LIFETIME)
            dispatch_task(send_password_reset_email, str(user.id), token)

        return Response(
            {"detail": "If that email exists, a reset link has been sent."}
        )


class ResetPasswordView(APIView):
    """
    POST /api/v1/auth/reset-password/
    Consumes a token from a reset or invite email and sets the password.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return validation_error_response(serializer.errors)

        user = get_user_for_token(serializer.validated_data["token"])
        if user is None:
            return Response(
                {"error": "This link is invalid or has expired. Request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_password = serializer.validated_data["new_password"]
        try:
            validate_password(new_password, user)
        except DjangoValidationError as exc:
            return validation_error_response(exc.messages)

        user.set_password(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        user.save()
        dispatch_task(send_password_changed_email, str(user.id))
        return Response({"detail": "Password reset successfully."})
