"""
Shopify OAuth views.

Flow:
1. Merchant visits /shopify/install/?shop=mystore.myshopify.com
2. We verify the request, generate state, redirect to Shopify authorize URL
3. Shopify redirects back to /shopify/callback/?code=...&shop=...&hmac=...&state=...
4. We verify HMAC and state, exchange code for access token
5. We save/update Merchant record with access token
6. Redirect merchant to Next.js app
"""
import hashlib
import hmac
import secrets
import urllib.parse

import requests
from django.conf import settings
from django.shortcuts import redirect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.services import normalize_shop_domain
from apps.merchants.models import Merchant, ShopifySession


def _verify_shopify_request(params: dict) -> bool:
    """Verify HMAC from Shopify OAuth redirect params."""
    received_hmac = params.pop("hmac", "")
    sorted_params = "&".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )
    computed = hmac.new(
        settings.SHOPIFY_API_SECRET.encode("utf-8"),
        sorted_params.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, received_hmac)


class ShopifyInstallView(APIView):
    """GET /shopify/install/?shop=mystore.myshopify.com"""
    permission_classes = [AllowAny]

    def get(self, request):
        shop = request.query_params.get("shop", "").strip().lower()
        # Only *.myshopify.com hosts — otherwise we'd redirect to any domain
        if not shop or normalize_shop_domain(shop) != shop:
            return Response({"error": "Invalid shop parameter"}, status=400)

        state = secrets.token_hex(16)
        request.session["shopify_oauth_state"] = state

        scopes = ",".join(settings.SHOPIFY_SCOPES)
        redirect_uri = f"{settings.SHOPIFY_APP_URL}/shopify/callback/"
        install_url = (
            f"https://{shop}/admin/oauth/authorize"
            f"?client_id={settings.SHOPIFY_API_KEY}"
            f"&scope={scopes}"
            f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
            f"&state={state}"
        )
        return redirect(install_url)


class ShopifyCallbackView(APIView):
    """GET /shopify/callback/?code=...&shop=...&hmac=...&state=..."""
    permission_classes = [AllowAny]

    def get(self, request):
        params = dict(request.query_params)
        params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}

        # ── Verify HMAC ───────────────────────────────────────────────────
        if not _verify_shopify_request(dict(params)):
            return Response({"error": "HMAC verification failed"}, status=401)

        # ── Verify state (CSRF protection) ────────────────────────────────
        state = params.get("state", "")
        stored_state = request.session.pop("shopify_oauth_state", None)
        if not stored_state or not hmac.compare_digest(state, stored_state):
            return Response({"error": "State mismatch"}, status=401)

        shop = params.get("shop", "")
        code = params.get("code", "")
        # The token request below goes to this host, so it must be a Shopify store
        if normalize_shop_domain(shop) != shop:
            return Response({"error": "Invalid shop parameter"}, status=400)

        # ── Exchange code for access token ────────────────────────────────
        token_response = requests.post(
            f"https://{shop}/admin/oauth/access_token",
            json={
                "client_id": settings.SHOPIFY_API_KEY,
                "client_secret": settings.SHOPIFY_API_SECRET,
                "code": code,
            },
            timeout=10,
        )
        if not token_response.ok:
            return Response({"error": "Failed to get access token"}, status=400)

        token_data = token_response.json()
        access_token = token_data.get("access_token")
        scope = token_data.get("scope", "")

        # ── Upsert Merchant ───────────────────────────────────────────────
        merchant, created = Merchant.objects.update_or_create(
            shop_domain=shop,
            defaults={"access_token": access_token},
        )

        # ── Save session ──────────────────────────────────────────────────
        ShopifySession.objects.update_or_create(
            id=f"{shop}_offline",
            defaults={
                "merchant": merchant,
                "state": state,
                "is_online": False,
                "scope": scope,
                "access_token": access_token,
            },
        )

        # ── Redirect to Next.js app ────────────────────────────────────────
        frontend_url = f"{settings.SHOPIFY_APP_URL}?shop={shop}"
        return redirect(frontend_url)
