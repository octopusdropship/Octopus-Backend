"""
Account services shared by the public auth views and the internal API.

ARCHITECT NOTE:
These replace the Supabase admin calls the Next.js app used to make
(provisioning store owners, inviting team members, password recovery).
Views stay thin; every rule about who may own or join a store lives here.
"""
import hashlib
import logging
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.authentication.models import UserRole, UserType
from apps.merchants.models import BillingSource, BillingStatus, Merchant

logger = logging.getLogger(__name__)
User = get_user_model()

TEAM_ROLES = (UserRole.ADMIN, UserRole.VIEWER)

# Values the old Supabase `users.payment_status` column used for lapsed access.
# Any other non-empty value counted as paid, so imports and the subscription
# webhook keep that rule.
_LAPSED_PAYMENT_STATUSES = {
    # The Octopus website creates every signup as "pending" until it is paid.
    "pending": BillingStatus.INACTIVE,
    "expired": BillingStatus.INACTIVE,
    "inactive": BillingStatus.INACTIVE,
    "failed": BillingStatus.INACTIVE,
    "unpaid": BillingStatus.INACTIVE,
    "cancelled": BillingStatus.CANCELLED,
    "canceled": BillingStatus.CANCELLED,
    "past_due": BillingStatus.PAST_DUE,
}


class AccountConflict(Exception):
    """The requested account change clashes with an existing account."""


class AccountNotFound(Exception):
    pass


def normalize_billing_status(value) -> str:
    status = str(value or "").strip().lower()
    if not status:
        return BillingStatus.INACTIVE
    return _LAPSED_PAYMENT_STATUSES.get(status, BillingStatus.ACTIVE)


def normalize_shop_domain(value) -> str | None:
    """Accepts 'https://x.myshopify.com/', 'x.myshopify.com' or a bare handle 'x'."""
    shop = str(value or "").strip().lower()
    shop = shop.removeprefix("https://").removeprefix("http://").split("/")[0]
    if shop and "." not in shop:
        shop = f"{shop}.myshopify.com"
    if not shop.endswith(".myshopify.com"):
        return None
    handle = shop.removesuffix(".myshopify.com")
    if not handle or not all(c.isalnum() or c == "-" for c in handle) or handle.startswith("-"):
        return None
    return shop


# ── Emailed tokens ────────────────────────────────────────────────────────────

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_account_token(user, lifetime) -> str:
    """Stores the hash of a fresh token on the user and returns the raw token to email."""
    token = secrets.token_urlsafe(32)
    user.reset_token = hash_token(token)
    user.reset_token_expires = timezone.now() + lifetime
    user.save(update_fields=["reset_token", "reset_token_expires"])
    return token


def get_user_for_token(token: str):
    return User.objects.filter(
        reset_token=hash_token(token),
        reset_token_expires__gt=timezone.now(),
        is_active=True,
    ).first()


def dispatch_task(task, *args):
    """
    Queue a Celery task once the surrounding transaction commits. If the
    broker is unreachable the task runs inline, so a missing Redis in dev
    never turns into a 500 for the user.
    """
    def _send():
        try:
            task.delay(*args)
        except Exception as exc:  # kombu raises several connection error types
            logger.warning(f"Broker unavailable for {task.name}, running inline: {exc}")
            task.apply(args=args)

    transaction.on_commit(_send)


def send_invite(user, shop_domain: str):
    from apps.authentication.tasks import send_invite_email

    token = issue_account_token(user, settings.INVITE_TOKEN_LIFETIME)
    dispatch_task(send_invite_email, str(user.id), token, shop_domain)


# ── Merchant billing ──────────────────────────────────────────────────────────

def apply_merchant_billing(
    merchant,
    *,
    billing_status=None,
    billing_plan=None,
    billing_source=None,
    is_approved=None,
):
    fields = []
    if billing_status is not None:
        status = normalize_billing_status(billing_status)
        if status == BillingStatus.ACTIVE and not merchant.billing_activated_at:
            merchant.billing_activated_at = timezone.now()
            fields.append("billing_activated_at")
        merchant.billing_status = status
        fields.append("billing_status")
    if billing_plan is not None:
        merchant.billing_plan = billing_plan or None
        fields.append("billing_plan")
    if billing_source is not None:
        merchant.billing_source = billing_source
        fields.append("billing_source")
    if is_approved is not None:
        merchant.is_approved = bool(is_approved)
        fields.append("is_approved")
    if fields:
        merchant.save(update_fields=[*fields, "updated_at"])
    return merchant


# ── Store owners ──────────────────────────────────────────────────────────────

@transaction.atomic
def provision_store_owner(
    *,
    email: str,
    shop_domain: str,
    password: str | None = None,
    name: str = "",
    billing_status="active",
    billing_plan="pro",
    billing_source=BillingSource.OCTOPUS,
    is_approved=True,
    send_invite_email: bool = False,
):
    """
    Create (or update) the owner login for a store and record its billing.
    Replaces `provisionSupabaseStoreUser`. An existing user keeps their
    password; an invite is only sent to accounts that have no password yet.
    """
    email = User.objects.normalize_email(email).lower()
    merchant, _ = Merchant.objects.select_for_update().get_or_create(shop_domain=shop_domain)
    apply_merchant_billing(
        merchant,
        billing_status=billing_status,
        billing_plan=billing_plan,
        billing_source=billing_source,
        is_approved=is_approved,
    )

    user = User.objects.select_for_update().filter(email=email).first()
    created = user is None
    if created:
        user = User.objects.create_user(
            email=email,
            password=password,  # None → unusable password
            name=name or email.split("@")[0],
            role=UserRole.OWNER,
            user_type=UserType.STORE,
            merchant=merchant,
        )
    else:
        if user.user_type != UserType.STORE:
            raise AccountConflict("This email belongs to a non-store account.")
        if user.merchant_id and user.merchant_id != merchant.id:
            raise AccountConflict("This email already has an Octopus account for another store.")
        if user.merchant_id and user.role != UserRole.OWNER:
            raise AccountConflict("This email is a team member of this store, not its owner.")
        user.merchant = merchant
        user.role = UserRole.OWNER
        user.is_active = True
        if name and not user.name:
            user.name = name
        user.save(update_fields=["merchant", "role", "is_active", "name", "updated_at"])

    invited = False
    if send_invite_email and not password and not user.has_usable_password():
        send_invite(user, merchant.shop_domain)
        invited = True

    return user, created, invited


# ── Team members ──────────────────────────────────────────────────────────────

@transaction.atomic
def invite_team_member(*, email: str, shop_domain: str, role: str, name: str = ""):
    """
    Create the login for a store's team member and email them a link to set
    their password. Replaces `inviteTeamMember` from supabase-admin.
    """
    if role not in TEAM_ROLES:
        raise ValueError("Role must be ADMIN or VIEWER.")

    email = User.objects.normalize_email(email).lower()
    merchant, _ = Merchant.objects.get_or_create(shop_domain=shop_domain)

    user = User.objects.select_for_update().filter(email=email).first()
    created = user is None
    if created:
        user = User.objects.create_user(
            email=email,
            password=None,
            name=name,
            role=role,
            user_type=UserType.STORE,
            merchant=merchant,
        )
    else:
        if user.user_type != UserType.STORE or user.merchant_id != merchant.id:
            raise AccountConflict("This email already has an Octopus account for another store.")
        if user.role == UserRole.OWNER:
            raise AccountConflict(
                "This email is the store owner's account and can't be invited as a team member."
            )
        user.role = role
        user.is_active = True
        if name:
            user.name = name
        user.save(update_fields=["role", "is_active", "name", "updated_at"])

    invited = False
    if not user.has_usable_password():
        send_invite(user, merchant.shop_domain)
        invited = True

    return user, created, invited


def _get_team_member(user_id, shop_domain: str):
    user = User.objects.filter(
        id=user_id, merchant__shop_domain=shop_domain, role__in=TEAM_ROLES
    ).first()
    if not user:
        raise AccountNotFound("Team member not found.")
    return user


def update_team_member(*, user_id, shop_domain: str, role: str):
    if role not in TEAM_ROLES:
        raise ValueError("Role must be ADMIN or VIEWER.")
    user = _get_team_member(user_id, shop_domain)
    user.role = role
    user.save(update_fields=["role", "updated_at"])
    return user


def remove_team_member(*, user_id, shop_domain: str):
    _get_team_member(user_id, shop_domain).delete()


# ── Accounts managed from the Octopus website ─────────────────────────────────
# The website (octopusdropship.com) is where stores and suppliers sign up and
# where Octopus staff approve them. An "account" is a store's or supplier's
# owner login (team members are managed inside the app), or a staff admin.

SIGNUP_USER_TYPES = (UserType.STORE, UserType.MANUFACTURER)
SUPPLIER_USER_TYPES = (UserType.SUPPLIER, UserType.MANUFACTURER)


@transaction.atomic
def register_account(
    *,
    email: str,
    password: str,
    name: str,
    user_type: str,
    shop_domain: str,
    category: str,
    billing_plan: str,
):
    """
    Website signup. The account starts unapproved and unpaid, so it cannot use
    the app until Octopus staff approve it.
    """
    if user_type not in SIGNUP_USER_TYPES:
        raise ValueError("Signup is only for stores and manufacturers.")

    email = User.objects.normalize_email(email).lower()
    if User.objects.filter(email=email).exists():
        raise AccountConflict("An account with this email already exists.")

    merchant, created = Merchant.objects.select_for_update().get_or_create(
        shop_domain=shop_domain,
        defaults={
            "is_approved": False,
            "billing_status": BillingStatus.INACTIVE,
            "billing_source": BillingSource.OCTOPUS,
        },
    )
    if not created and merchant.store_users.filter(role=UserRole.OWNER).exists():
        raise AccountConflict("This Shopify store is already connected to another account.")

    merchant.is_supplier = user_type in SUPPLIER_USER_TYPES
    merchant.category = category or merchant.category
    merchant.billing_plan = billing_plan or merchant.billing_plan
    merchant.save(update_fields=["is_supplier", "category", "billing_plan", "updated_at"])

    return User.objects.create_user(
        email=email,
        password=password,
        name=name or email.split("@")[0],
        role=UserRole.OWNER,
        user_type=user_type,
        merchant=merchant,
    )


def list_accounts(*, user_type: str = "all", approval: str = "all", search: str = ""):
    """Owner and staff accounts, newest first, for the website's admin panel."""
    accounts = (
        User.objects.select_related("merchant")
        .filter(role=UserRole.OWNER)
        .order_by("-created_at")
    )
    if user_type == UserType.STORE:
        accounts = accounts.filter(user_type=UserType.STORE)
    elif user_type in SUPPLIER_USER_TYPES:
        accounts = accounts.filter(user_type__in=SUPPLIER_USER_TYPES)
    elif user_type == UserType.ADMIN:
        accounts = accounts.filter(user_type=UserType.ADMIN)

    if approval == "approved":
        accounts = accounts.filter(merchant__is_approved=True)
    elif approval == "pending":
        accounts = accounts.filter(merchant__is_approved=False)

    search = (search or "").strip()
    if search:
        accounts = accounts.filter(
            Q(name__icontains=search)
            | Q(email__icontains=search)
            | Q(merchant__shop_domain__icontains=search)
        )
    return accounts


def _get_account(user_id):
    user = User.objects.select_related("merchant").filter(id=user_id, role=UserRole.OWNER).first()
    if not user:
        raise AccountNotFound("Account not found.")
    return user


@transaction.atomic
def update_account(user_id, **changes):
    """
    Staff edits from the website's admin panel. Only the keys present in
    `changes` are updated: name, email, shop_domain, category, user_type,
    billing_plan, billing_status, is_approved.
    """
    user = _get_account(user_id)
    merchant = user.merchant
    user_fields = []

    if "name" in changes:
        user.name = changes["name"]
        user_fields.append("name")

    if "email" in changes:
        email = User.objects.normalize_email(changes["email"]).lower()
        if email != user.email:
            if User.objects.filter(email=email).exclude(id=user.id).exists():
                raise AccountConflict("An account with this email already exists.")
            user.email = email
            user_fields.append("email")

    if "user_type" in changes:
        user.user_type = changes["user_type"]
        user_fields.append("user_type")

    if user_fields:
        user.save(update_fields=[*user_fields, "updated_at"])

    if merchant is None:
        return user

    merchant_fields = []
    if "shop_domain" in changes and changes["shop_domain"] != merchant.shop_domain:
        if Merchant.objects.filter(shop_domain=changes["shop_domain"]).exists():
            raise AccountConflict("This Shopify store is already connected to another account.")
        merchant.shop_domain = changes["shop_domain"]
        merchant_fields.append("shop_domain")
    if "category" in changes:
        merchant.category = changes["category"] or None
        merchant_fields.append("category")
    if "user_type" in changes:
        merchant.is_supplier = changes["user_type"] in SUPPLIER_USER_TYPES
        merchant_fields.append("is_supplier")
    if merchant_fields:
        merchant.save(update_fields=[*merchant_fields, "updated_at"])

    apply_merchant_billing(
        merchant,
        billing_status=changes.get("billing_status"),
        billing_plan=changes.get("billing_plan"),
        is_approved=changes.get("is_approved"),
    )
    return user


def set_account_approval(user_id, approved: bool):
    """
    Approve or revoke a store/supplier. Approving also activates its plan,
    because plans are paid outside the app for now; revoking leaves the plan
    as it is, so re-approving restores the same access.
    """
    user = _get_account(user_id)
    if user.merchant is None:
        raise AccountConflict("Staff accounts don't need approval.")
    apply_merchant_billing(
        user.merchant,
        is_approved=approved,
        billing_status=BillingStatus.ACTIVE if approved else None,
    )
    return user


@transaction.atomic
def delete_account(user_id):
    """Deletes the account; for a store or supplier, its store record and team logins too."""
    user = _get_account(user_id)
    if user.merchant is not None:
        user.merchant.delete()  # cascades to every login of that store
    else:
        user.delete()
