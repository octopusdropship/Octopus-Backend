"""
Authentication tests — login, rate limiting, user enumeration prevention.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.merchants.models import Merchant
from apps.authentication.models import StoreUser


class AuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.merchant = Merchant.objects.create(shop_domain="testshop.myshopify.com")
        self.user = StoreUser.objects.create_user(
            email="owner@test.com",
            password="securepass123",
            merchant=self.merchant,
            role="OWNER",
        )

    def test_login_returns_jwt(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "owner@test.com", "password": "securepass123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_wrong_password_returns_401(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "owner@test.com", "password": "wrongpass"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_wrong_email_returns_same_message_as_wrong_password(self):
        """Prevents user enumeration — both wrong email and wrong password look identical."""
        r1 = self.client.post(
            "/api/v1/auth/login/",
            {"email": "notexist@test.com", "password": "anything"},
            format="json",
        )
        r2 = self.client.post(
            "/api/v1/auth/login/",
            {"email": "owner@test.com", "password": "wrongpass"},
            format="json",
        )
        self.assertEqual(r1.status_code, 401)
        self.assertEqual(r2.status_code, 401)
        self.assertEqual(r1.data["error"], r2.data["error"])

    def test_me_requires_auth(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_me_returns_profile(self):
        login = self.client.post(
            "/api/v1/auth/login/",
            {"email": "owner@test.com", "password": "securepass123"},
            format="json",
        )
        token = login.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "owner@test.com")

    def test_forgot_password_always_returns_200(self):
        """Even for nonexistent email — prevents enumeration."""
        response = self.client.post(
            "/api/v1/auth/forgot-password/",
            {"email": "doesnotexist@test.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
