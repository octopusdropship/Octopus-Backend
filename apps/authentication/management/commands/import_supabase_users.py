"""
One-off import of accounts from Supabase into Django.

1. In the Supabase SQL editor, export users with their password hashes as JSON:

    select coalesce(json_agg(t), '[]') from (
      select u.id, u.email, u.name, u.user_type, u.shop_url, u.payment_status,
             u.is_approved, u.subscription_plan, u.category,
             to_jsonb(u) ->> 'brand_image' as brand_image,
             a.encrypted_password
      from public.users u
      join auth.users a on a.id = u.id
    ) t;

   Save the result as supabase_users.json.

2. Team members' roles live in the Next.js (Prisma) database, not Supabase.
   Export them so they are not imported as store owners:

    psql "$DATABASE_URL" -At -c \
      "select coalesce(json_agg(json_build_object('email', email, 'role', role)), '[]') from \"StoreUser\";" \
      > team_roles.json

3. Run:  python manage.py import_supabase_users supabase_users.json --team-file team_roles.json

Users keep their Supabase UUID (so existing `octopus_app_user` cookies and
Prisma `StoreUser.supabaseId` links still resolve) and their bcrypt password
hash, which Django verifies and upgrades to PBKDF2 on their next login.
Re-running is safe: existing users are updated, and a password already set
in Django is never overwritten.
"""
import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.authentication.models import UserRole, UserType
from apps.authentication.services import apply_merchant_billing, normalize_shop_domain
from apps.merchants.models import BillingSource, Merchant

User = get_user_model()


class Command(BaseCommand):
    help = "Import users exported from Supabase (see module docstring)."

    def add_arguments(self, parser):
        parser.add_argument("users_file", help="JSON array exported from Supabase")
        parser.add_argument("--team-file", help="JSON array of {email, role} from Prisma StoreUser")
        parser.add_argument("--dry-run", action="store_true", help="Validate without saving")

    def handle(self, *args, **options):
        rows = self._load(options["users_file"])
        team_roles = {
            str(r["email"]).strip().lower(): r["role"]
            for r in (self._load(options["team_file"]) if options["team_file"] else [])
        }

        counts = {"created": 0, "updated": 0, "skipped": 0}
        with transaction.atomic():
            for row in rows:
                result = self._import_row(row, team_roles)
                counts[result] += 1
            if options["dry_run"]:
                transaction.set_rollback(True)

        prefix = "[dry run] " if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}created {counts['created']}, updated {counts['updated']}, "
            f"skipped {counts['skipped']}"
        ))

    def _load(self, path):
        try:
            with open(path) as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read {path}: {exc}")
        if not isinstance(data, list):
            raise CommandError(f"{path} must contain a JSON array")
        return data

    def _skip(self, row, reason):
        self.stdout.write(self.style.WARNING(f"skip {row.get('email') or row.get('id')}: {reason}"))
        return "skipped"

    def _import_row(self, row, team_roles):
        email = str(row.get("email") or "").strip().lower()
        if not email:
            return self._skip(row, "no email")

        user_type = str(row.get("user_type") or "").strip().lower()
        if user_type not in UserType.values:
            return self._skip(row, f"unknown user_type {user_type!r}")

        shop = normalize_shop_domain(row.get("shop_url"))
        if user_type == UserType.STORE and not shop:
            return self._skip(row, f"store user without a valid shop_url ({row.get('shop_url')!r})")

        role = team_roles.get(email, UserRole.OWNER)
        if role not in UserRole.values:
            return self._skip(row, f"unknown role {role!r}")

        merchant = None
        if shop and user_type != UserType.ADMIN:
            merchant, _ = Merchant.objects.get_or_create(shop_domain=shop)
            if user_type in (UserType.SUPPLIER, UserType.MANUFACTURER):
                merchant.is_supplier = True
            if row.get("category"):
                merchant.category = row["category"]
            if row.get("brand_image"):
                merchant.brand_image = row["brand_image"]
            merchant.save()
            # Billing belongs to the owner's profile; team profiles were created unpaid.
            if user_type == UserType.STORE and role == UserRole.OWNER:
                apply_merchant_billing(
                    merchant,
                    billing_status=row.get("payment_status"),
                    billing_plan=row.get("subscription_plan") or "",
                    billing_source=BillingSource.OCTOPUS,
                    is_approved=row.get("is_approved", True),
                )

        user = User.objects.filter(email=email).first()
        created = user is None
        if created:
            user = User(id=row["id"], email=email) if row.get("id") else User(email=email)

        user.name = row.get("name") or user.name or email.split("@")[0]
        user.user_type = user_type
        user.role = role if user_type == UserType.STORE else UserRole.OWNER
        user.merchant = merchant
        user.is_active = True

        if created or not user.has_usable_password():
            password_hash = str(row.get("encrypted_password") or "")
            if password_hash.startswith("$2"):
                user.password = f"bcrypt${password_hash}"
            else:
                user.set_unusable_password()

        user.save()
        return "created" if created else "updated"
