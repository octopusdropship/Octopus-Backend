"""
Account API tests — the endpoints the Next.js app uses instead of Supabase.
"""
import json
import tempfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth.hashers import check_password
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.authentication.models import StoreUser
from apps.authentication.services import hash_token, issue_account_token, normalize_shop_domain
from apps.merchants.models import Merchant

INTERNAL_KEY = "test-internal-key"


@override_settings(INTERNAL_API_KEY=INTERNAL_KEY, CELERY_TASK_ALWAYS_EAGER=True)
class AccountTestBase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.internal = APIClient()
        self.internal.credentials(HTTP_X_INTERNAL_API_KEY=INTERNAL_KEY)
        patcher = mock.patch("apps.authentication.tasks._send_email")
        self.send_email = patcher.start()
        self.addCleanup(patcher.stop)


class LoginProfileTest(AccountTestBase):
    def test_login_returns_store_and_billing_profile(self):
        merchant = Merchant.objects.create(
            shop_domain="shop.myshopify.com", billing_status="active", category="Jewellery"
        )
        StoreUser.objects.create_user(
            email="Owner@Test.com", password="securepass123", merchant=merchant, role="OWNER"
        )
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "owner@test.com", "password": "securepass123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        user = response.data["user"]
        self.assertEqual(user["user_type"], "store")
        self.assertEqual(user["merchant"]["shop_domain"], "shop.myshopify.com")
        self.assertEqual(user["merchant"]["category"], "Jewellery")
        self.assertTrue(user["merchant"]["has_active_subscription"])

    def test_login_for_user_without_store(self):
        StoreUser.objects.create_user(email="admin@test.com", password="securepass123", user_type="admin")
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "admin@test.com", "password": "securepass123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["user"]["merchant"])

    def test_invited_user_without_password_cannot_log_in(self):
        StoreUser.objects.create_user(email="new@test.com", password=None)
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "new@test.com", "password": ""}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_bcrypt_hash_from_supabase_is_accepted_and_upgraded(self):
        import bcrypt

        user = StoreUser.objects.create(email="legacy@test.com")
        user.password = "bcrypt$" + bcrypt.hashpw(b"oldpassword1", bcrypt.gensalt()).decode()
        user.save()
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "legacy@test.com", "password": "oldpassword1"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.password.startswith("bcrypt$"))  # re-hashed with the preferred hasher

    def test_register_endpoint_is_gone(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {"email": "x@test.com", "password": "securepass123", "role": "OWNER"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)


class PasswordResetTest(AccountTestBase):
    def setUp(self):
        super().setUp()
        self.user = StoreUser.objects.create_user(email="owner@test.com", password="securepass123")

    def test_forgot_password_emails_frontend_link_and_stores_only_hash(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/auth/forgot-password/", {"email": "owner@test.com"}, format="json"
            )
        self.assertEqual(response.status_code, 200)
        self.send_email.assert_called_once()
        html = self.send_email.call_args.args[2]
        self.assertIn("/auth/reset-password?token=", html)
        token = html.split("token=")[1].split("&")[0]
        self.user.refresh_from_db()
        self.assertEqual(self.user.reset_token, hash_token(token))

    def test_reset_password_with_valid_token(self):
        token = issue_account_token(self.user, timedelta(hours=1))
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/auth/reset-password/",
                {"token": token, "new_password": "brand-new-pass-42"},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("brand-new-pass-42"))
        self.assertIsNone(self.user.reset_token)
        self.send_email.assert_called_once()  # "password changed" notice

    def test_reset_password_rejects_unknown_token(self):
        response = self.client.post(
            "/api/v1/auth/reset-password/",
            {"token": "nope", "new_password": "brand-new-pass-42"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)

    def test_reset_password_rejects_weak_password_with_message(self):
        token = issue_account_token(self.user, timedelta(hours=1))
        response = self.client.post(
            "/api/v1/auth/reset-password/", {"token": token, "new_password": "12345678"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIsInstance(response.data["error"], str)


class InternalApiAuthTest(AccountTestBase):
    def test_requires_internal_key(self):
        response = self.client.get("/api/v1/internal/merchants/lookup/?shop=a.myshopify.com")
        self.assertIn(response.status_code, (401, 403))

    def test_wrong_internal_key_rejected(self):
        self.client.credentials(HTTP_X_INTERNAL_API_KEY="wrong")
        response = self.client.get("/api/v1/internal/merchants/lookup/?shop=a.myshopify.com")
        self.assertIn(response.status_code, (401, 403))

    @override_settings(INTERNAL_API_KEY="")
    def test_unset_internal_key_disables_internal_api(self):
        self.client.credentials(HTTP_X_INTERNAL_API_KEY="")
        response = self.client.get("/api/v1/internal/merchants/lookup/?shop=a.myshopify.com")
        self.assertIn(response.status_code, (401, 403))


class ProvisionOwnerTest(AccountTestBase):
    def test_provision_with_password_creates_owner_and_merchant(self):
        response = self.internal.post(
            "/api/v1/internal/users/provision/",
            {
                "email": "owner@test.com",
                "password": "securepass123",
                "shop_domain": "https://my-shop.myshopify.com/",
                "billing_status": "paid",
                "billing_plan": "premium",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        merchant = Merchant.objects.get(shop_domain="my-shop.myshopify.com")
        self.assertEqual(merchant.billing_status, "active")
        self.assertEqual(merchant.billing_plan, "premium")
        user = StoreUser.objects.get(email="owner@test.com")
        self.assertEqual(user.role, "OWNER")
        self.assertTrue(user.check_password("securepass123"))

    def test_provision_with_invite_sends_set_password_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.internal.post(
                "/api/v1/internal/users/provision/",
                {"email": "owner@test.com", "shop_domain": "my-shop", "send_invite": True},
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["invited"])
        self.assertIn("type=invite", self.send_email.call_args.args[2])

    def test_provision_existing_owner_keeps_password(self):
        merchant = Merchant.objects.create(shop_domain="my-shop.myshopify.com")
        StoreUser.objects.create_user(
            email="owner@test.com", password="original-pass-1", merchant=merchant, role="OWNER"
        )
        response = self.internal.post(
            "/api/v1/internal/users/provision/",
            {
                "email": "owner@test.com",
                "password": "other-pass-123",
                "shop_domain": "my-shop.myshopify.com",
                "billing_source": "shopify",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["created"])
        self.assertTrue(StoreUser.objects.get(email="owner@test.com").check_password("original-pass-1"))

    def test_provision_rejects_email_owned_by_another_store(self):
        other = Merchant.objects.create(shop_domain="other.myshopify.com")
        StoreUser.objects.create_user(email="owner@test.com", password="x" * 10, merchant=other, role="OWNER")
        response = self.internal.post(
            "/api/v1/internal/users/provision/",
            {"email": "owner@test.com", "password": "securepass123", "shop_domain": "mine.myshopify.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 409)

    def test_provision_rejects_non_shopify_domain(self):
        response = self.internal.post(
            "/api/v1/internal/users/provision/",
            {"email": "owner@test.com", "password": "securepass123", "shop_domain": "google.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class TeamMemberTest(AccountTestBase):
    def setUp(self):
        super().setUp()
        self.merchant = Merchant.objects.create(shop_domain="store.myshopify.com")
        self.owner = StoreUser.objects.create_user(
            email="owner@test.com", password="securepass123", merchant=self.merchant, role="OWNER"
        )

    def _invite(self, email="staff@test.com", shop="store.myshopify.com", role="VIEWER"):
        with self.captureOnCommitCallbacks(execute=True):
            return self.internal.post(
                "/api/v1/internal/team/invite/",
                {"email": email, "shop_domain": shop, "role": role, "name": "Staff"},
                format="json",
            )

    def test_invite_creates_member_without_password_and_emails_link(self):
        response = self._invite()
        self.assertEqual(response.status_code, 201)
        member = StoreUser.objects.get(email="staff@test.com")
        self.assertEqual(member.role, "VIEWER")
        self.assertFalse(member.has_usable_password())
        self.assertTrue(response.data["invited"])
        self.send_email.assert_called_once()

    def test_cannot_invite_store_owner(self):
        response = self._invite(email="owner@test.com")
        self.assertEqual(response.status_code, 409)

    def test_cannot_invite_user_of_another_store(self):
        response = self._invite(shop="elsewhere.myshopify.com", email="owner@test.com")
        self.assertEqual(response.status_code, 409)

    def test_cannot_invite_as_owner(self):
        response = self._invite(role="OWNER")
        self.assertEqual(response.status_code, 400)

    def test_update_and_remove_are_scoped_to_shop(self):
        member_id = self._invite().data["user"]["id"]
        url = f"/api/v1/internal/team/{member_id}/"

        wrong_shop = self.internal.patch(
            url, {"shop_domain": "elsewhere.myshopify.com", "role": "ADMIN"}, format="json"
        )
        self.assertEqual(wrong_shop.status_code, 404)

        ok = self.internal.patch(url, {"shop_domain": "store.myshopify.com", "role": "ADMIN"}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(StoreUser.objects.get(id=member_id).role, "ADMIN")

        removed = self.internal.delete(f"{url}?shop_domain=store.myshopify.com")
        self.assertEqual(removed.status_code, 204)
        self.assertFalse(StoreUser.objects.filter(id=member_id).exists())

    def test_owner_cannot_be_removed_through_team_api(self):
        response = self.internal.delete(
            f"/api/v1/internal/team/{self.owner.id}/?shop_domain=store.myshopify.com"
        )
        self.assertEqual(response.status_code, 404)


class MerchantInternalTest(AccountTestBase):
    def setUp(self):
        super().setUp()
        self.merchant = Merchant.objects.create(
            shop_domain="store.myshopify.com",
            billing_status="active",
            billing_source="shopify",
            billing_plan="pro",
        )
        StoreUser.objects.create_user(
            email="owner@test.com", password="securepass123", merchant=self.merchant, role="OWNER"
        )

    def test_lookup_returns_billing_and_owner(self):
        response = self.internal.get("/api/v1/internal/merchants/lookup/?shop=store.myshopify.com")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["has_active_subscription"])
        self.assertEqual(response.data["owner"]["email"], "owner@test.com")

    def test_lookup_unknown_shop_is_404(self):
        response = self.internal.get("/api/v1/internal/merchants/lookup/?shop=nobody.myshopify.com")
        self.assertEqual(response.status_code, 404)

    def test_billing_update_respects_only_if_source(self):
        skipped = self.internal.post(
            "/api/v1/internal/merchants/billing/",
            {"shop_domain": "store.myshopify.com", "billing_status": "inactive", "only_if_source": "octopus"},
            format="json",
        )
        self.assertFalse(skipped.data["updated"])
        self.merchant.refresh_from_db()
        self.assertEqual(self.merchant.billing_status, "active")

        applied = self.internal.post(
            "/api/v1/internal/merchants/billing/",
            {"shop_domain": "store.myshopify.com", "billing_status": "cancelled", "only_if_source": "shopify"},
            format="json",
        )
        self.assertTrue(applied.data["updated"])
        self.merchant.refresh_from_db()
        self.assertEqual(self.merchant.billing_status, "cancelled")


class ImportSupabaseUsersTest(TestCase):
    def _run(self, users, team=None):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(users, fh)
        args = [fh.name]
        if team is not None:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
                json.dump(team, tf)
            args += ["--team-file", tf.name]
        call_command("import_supabase_users", *args, stdout=open("/dev/null", "w"))

    def test_imports_owner_team_member_and_admin(self):
        import bcrypt

        pw = bcrypt.hashpw(b"ownerpass1", bcrypt.gensalt()).decode()
        self._run(
            [
                {
                    "id": "5f0c3f5e-1111-4a4a-9a9a-000000000001",
                    "email": "Owner@Shop.com",
                    "user_type": "store",
                    "shop_url": "https://shop.myshopify.com",
                    "payment_status": "paid",
                    "is_approved": True,
                    "subscription_plan": "premium",
                    "category": "Opticals",
                    "encrypted_password": pw,
                },
                {
                    "id": "5f0c3f5e-1111-4a4a-9a9a-000000000002",
                    "email": "staff@shop.com",
                    "user_type": "store",
                    "shop_url": "https://shop.myshopify.com",
                    "payment_status": "inactive",
                    "encrypted_password": None,
                },
                {"id": "5f0c3f5e-1111-4a4a-9a9a-000000000003", "email": "agent@octopus.com",
                 "user_type": "admin", "shop_url": None, "encrypted_password": pw},
                {"id": "5f0c3f5e-1111-4a4a-9a9a-000000000004", "email": "bad@x.com",
                 "user_type": "store", "shop_url": "google.com"},
            ],
            team=[{"email": "staff@shop.com", "role": "VIEWER"}],
        )
        owner = StoreUser.objects.get(email="owner@shop.com")
        self.assertEqual(str(owner.id), "5f0c3f5e-1111-4a4a-9a9a-000000000001")
        self.assertEqual(owner.role, "OWNER")
        self.assertTrue(check_password("ownerpass1", owner.password))

        merchant = Merchant.objects.get(shop_domain="shop.myshopify.com")
        self.assertEqual(merchant.billing_status, "active")  # team member's "inactive" ignored
        self.assertEqual(merchant.billing_plan, "premium")
        self.assertEqual(merchant.category, "Opticals")

        staff = StoreUser.objects.get(email="staff@shop.com")
        self.assertEqual(staff.role, "VIEWER")
        self.assertFalse(staff.has_usable_password())

        self.assertEqual(StoreUser.objects.get(email="agent@octopus.com").user_type, "admin")
        self.assertFalse(StoreUser.objects.filter(email="bad@x.com").exists())


class ShopDomainTest(TestCase):
    def test_normalize_shop_domain(self):
        self.assertEqual(normalize_shop_domain("https://My-Shop.myshopify.com/"), "my-shop.myshopify.com")
        self.assertEqual(normalize_shop_domain("my-shop"), "my-shop.myshopify.com")
        self.assertIsNone(normalize_shop_domain("google.com"))
        self.assertIsNone(normalize_shop_domain("evil.com/x.myshopify.com"))
        self.assertIsNone(normalize_shop_domain(""))
        self.assertIsNone(normalize_shop_domain(None))


class WebsiteAccountTest(AccountTestBase):
    """Signup and staff approval from the Octopus website (replaces Supabase)."""

    def signup(self, **overrides):
        payload = {
            "email": "Owner@Shop.com",
            "password": "securepass123",
            "name": "Asha",
            "user_type": "store",
            "shop_domain": "https://my-shop.myshopify.com/",
            "category": "Jewellery",
            "billing_plan": "pro",
            **overrides,
        }
        return self.internal.post("/api/v1/internal/accounts/", payload, format="json")

    def test_signup_creates_unapproved_unpaid_store(self):
        response = self.signup()
        self.assertEqual(response.status_code, 201)
        account = response.json()["account"]
        self.assertEqual(account["email"], "owner@shop.com")
        self.assertEqual(account["shop_domain"], "my-shop.myshopify.com")
        self.assertFalse(account["is_approved"])
        self.assertEqual(account["billing_status"], "inactive")
        merchant = Merchant.objects.get(shop_domain="my-shop.myshopify.com")
        self.assertFalse(merchant.has_active_subscription)
        self.assertFalse(merchant.is_supplier)
        self.assertEqual(merchant.category, "Jewellery")

    def test_supplier_signup_marks_store_as_supplier(self):
        response = self.signup(user_type="manufacturer", billing_plan="premium")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Merchant.objects.get(shop_domain="my-shop.myshopify.com").is_supplier)

    def test_signup_rejects_plan_for_wrong_account_type(self):
        self.assertEqual(self.signup(billing_plan="premium").status_code, 400)
        self.assertEqual(self.signup(user_type="manufacturer", billing_plan="basic").status_code, 400)

    def test_signup_rejects_duplicate_email_and_shop(self):
        self.assertEqual(self.signup().status_code, 201)
        self.assertEqual(self.signup(shop_domain="other.myshopify.com").status_code, 409)
        self.assertEqual(self.signup(email="second@shop.com").status_code, 409)

    def test_signup_requires_internal_key(self):
        response = self.client.post("/api/v1/internal/accounts/", {}, format="json")
        self.assertIn(response.status_code, (401, 403))

    def test_approval_grants_access_and_revoking_removes_it(self):
        account_id = self.signup().json()["account"]["id"]
        url = f"/api/v1/internal/accounts/{account_id}/approval/"

        approved = self.internal.post(url, {"approved": True}, format="json").json()["account"]
        self.assertTrue(approved["is_approved"])
        self.assertEqual(approved["billing_status"], "active")
        self.assertTrue(Merchant.objects.get(shop_domain="my-shop.myshopify.com").has_active_subscription)

        revoked = self.internal.post(url, {"approved": False}, format="json").json()["account"]
        self.assertFalse(revoked["is_approved"])
        self.assertFalse(Merchant.objects.get(shop_domain="my-shop.myshopify.com").has_active_subscription)

    def test_signup_password_works_for_login(self):
        self.signup()
        response = self.client.post(
            "/api/v1/auth/login/", {"email": "owner@shop.com", "password": "securepass123"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["user"]["merchant"]["is_approved"])

    def test_list_filters_by_approval_and_type(self):
        store_id = self.signup().json()["account"]["id"]
        self.signup(
            email="maker@x.com", shop_domain="maker.myshopify.com", user_type="manufacturer", billing_plan="premium"
        )
        self.internal.post(f"/api/v1/internal/accounts/{store_id}/approval/", {"approved": True}, format="json")

        def emails(query):
            return sorted(a["email"] for a in self.internal.get(f"/api/v1/internal/accounts/{query}").json()["accounts"])

        self.assertEqual(emails(""), ["maker@x.com", "owner@shop.com"])
        self.assertEqual(emails("?approval=pending"), ["maker@x.com"])
        self.assertEqual(emails("?user_type=store"), ["owner@shop.com"])
        self.assertEqual(emails("?search=maker"), ["maker@x.com"])

    def test_staff_edit_updates_store_fields(self):
        account_id = self.signup().json()["account"]["id"]
        response = self.internal.patch(
            f"/api/v1/internal/accounts/{account_id}/",
            {"category": "Opticals", "billing_plan": "basic", "billing_status": "cancelled", "name": "New"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        merchant = Merchant.objects.get(shop_domain="my-shop.myshopify.com")
        self.assertEqual((merchant.category, merchant.billing_plan, merchant.billing_status), ("Opticals", "basic", "cancelled"))
        self.assertEqual(StoreUser.objects.get(id=account_id).name, "New")

    def test_delete_removes_store_and_its_logins(self):
        account_id = self.signup().json()["account"]["id"]
        merchant = Merchant.objects.get(shop_domain="my-shop.myshopify.com")
        StoreUser.objects.create_user(email="team@shop.com", merchant=merchant, role="VIEWER")

        response = self.internal.delete(f"/api/v1/internal/accounts/{account_id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Merchant.objects.filter(shop_domain="my-shop.myshopify.com").exists())
        self.assertFalse(StoreUser.objects.filter(email__in=["owner@shop.com", "team@shop.com"]).exists())
