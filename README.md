# Octopus Backend — Django REST API

## Quick Start

```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Copy env file and fill in values
cp .env.example .env

# 4. Run migrations
make migrate

# 5. Create superuser for Django Admin
make superuser

# 6. Start dev server
make dev
# → http://localhost:8000

# 7. Run tests
make test

# 8. Start Celery worker (in separate terminal)
make celery
```

## Project Structure

```
apps/
├── authentication/   # StoreUser model, JWT login, password reset, RBAC permissions
├── merchants/        # Merchant profiles, billing, Shopify OAuth
├── products/         # Catalog, variants, push to merchant store
├── orders/           # Order management, idempotent webhook processing
├── support/          # Support tickets and call requests
├── notifications/    # In-app notifications
└── webhooks/         # Shopify webhook receiver (HMAC verified → Celery)

octopus_core/
├── settings/
│   ├── base.py       # Shared settings
│   ├── development.py
│   └── production.py
├── urls.py           # Root URL config
├── api_router.py     # All /api/v1/ routes in one place
└── celery.py         # Background task queue
```

## API Endpoints (v1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/login/ | Login — returns JWT |
| GET | /api/v1/auth/me/ | Current user profile |
| POST | /api/v1/auth/forgot-password/ | Send reset email |
| POST | /api/v1/auth/reset-password/ | Set password from reset/invite token |
| POST | /api/v1/auth/change-password/ | Change password (JWT) |
| GET | /api/v1/merchants/settings/ | Get merchant settings |
| PATCH | /api/v1/merchants/settings/ | Update settings |
| GET | /api/v1/merchants/billing/ | Billing status |
| GET | /api/v1/merchants/dashboard/ | Dashboard stats |
| GET | /api/v1/products/ | Product catalog |
| GET | /api/v1/orders/ | Order list |
| GET | /api/v1/orders/{id}/ | Order detail |
| GET | /api/v1/support/tickets/ | List tickets |
| POST | /api/v1/support/tickets/ | Create ticket |
| POST | /api/v1/support/call-requests/ | Request callback |
| GET | /api/v1/notifications/ | Notifications list |
| PATCH | /api/v1/notifications/{id}/read/ | Mark as read |
| POST | /api/v1/internal/users/provision/ | Create/update store owner + billing (internal) |
| GET | /api/v1/internal/users/{id}/ | User profile by id (internal) |
| POST | /api/v1/internal/team/invite/ | Invite team member, emails set-password link (internal) |
| PATCH/DELETE | /api/v1/internal/team/{id}/ | Change role / remove team member (internal) |
| GET | /api/v1/internal/merchants/lookup/?shop= | Store category, billing, owner (internal) |
| POST | /api/v1/internal/merchants/billing/ | Update store billing status (internal) |
| GET | /shopify/install/ | Shopify OAuth install |
| GET | /shopify/callback/ | Shopify OAuth callback |
| POST | /webhooks/shopify/{topic}/ | Shopify webhook receiver |

## Internal API & the Next.js app

The Next.js app calls this backend **server-to-server only**. Every request it
sends carries `X-Internal-Api-Key` (= `INTERNAL_API_KEY` here,
`OCTOPUS_BACKEND_INTERNAL_KEY` in the frontend) and the end user's IP as
`X-Client-IP`, so login rate limits apply per user, not per Next.js server.
`/api/v1/internal/*` rejects every request when `INTERNAL_API_KEY` is unset.

There is no public registration: store owners are provisioned by the
subscription flow, team members by invite.

## Migrating users from Supabase

`python manage.py import_supabase_users supabase_users.json --team-file team_roles.json`

See the docstring in `apps/authentication/management/commands/import_supabase_users.py`
for the two export queries. Users keep their Supabase ids and passwords.
# Octopus-Backend
