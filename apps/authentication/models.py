"""
Authentication models.

ARCHITECT NOTE:
Custom User model (StoreUser) MUST be defined before the first migration.
Django cannot change AUTH_USER_MODEL after migrations have been applied.
We use email as the login identifier, not username.
"""
import uuid
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models


class UserRole(models.TextChoices):
    OWNER = "OWNER", "Owner"
    ADMIN = "ADMIN", "Admin"
    VIEWER = "VIEWER", "Viewer"


class UserType(models.TextChoices):
    """
    Account kind, carried over from the old Supabase `users.user_type` column.
    STORE users run a retailer store; SUPPLIER/MANUFACTURER users own the
    catalog; ADMIN users are Octopus staff who use the support panel.
    """
    STORE = "store", "Store"
    SUPPLIER = "supplier", "Supplier"
    MANUFACTURER = "manufacturer", "Manufacturer"
    ADMIN = "admin", "Admin"


class StoreUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", UserRole.OWNER)
        return self.create_user(email, password, **extra_fields)


class StoreUser(AbstractBaseUser, PermissionsMixin):
    """
    One user belongs to exactly one Merchant (multi-tenant isolation).
    A merchant can have multiple StoreUsers with different roles.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    name = models.CharField(max_length=255, blank=True)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.VIEWER,
        db_index=True,
    )
    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.STORE,
        db_index=True,
    )

    # FK to Merchant — circular import handled via string reference
    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        related_name="store_users",
        null=True,
        blank=True,
    )

    # Password reset / invite. Only the SHA-256 of the emailed token is stored.
    reset_token = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    reset_token_expires = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Django admin access

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = StoreUserManager()

    class Meta:
        db_table = "store_users"
        indexes = [
            models.Index(fields=["merchant", "role"]),
            models.Index(fields=["email", "is_active"]),
        ]

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property
    def is_supplier_account(self):
        return self.user_type in (UserType.SUPPLIER, UserType.MANUFACTURER)

    @property
    def is_owner(self):
        return self.role == UserRole.OWNER

    @property
    def is_admin_or_above(self):
        return self.role in (UserRole.OWNER, UserRole.ADMIN)
