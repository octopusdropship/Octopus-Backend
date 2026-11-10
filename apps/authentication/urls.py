from django.urls import path
from .views import (
    LoginView,
    MeView,
    ChangePasswordView,
    ForgotPasswordView,
    ResetPasswordView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth_login"),
    path("me/", MeView.as_view(), name="auth_me"),
    path("change-password/", ChangePasswordView.as_view(), name="auth_change_password"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="auth_forgot_password"),
    path("reset-password/", ResetPasswordView.as_view(), name="auth_reset_password"),
]
