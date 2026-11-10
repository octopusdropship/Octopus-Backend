"""Celery tasks for authentication — email dispatch."""
import logging
from html import escape
from urllib.parse import urlencode

import requests

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


def _account_link(token: str, link_type: str) -> str:
    query = urlencode({"token": token, "type": link_type})
    return f"{settings.FRONTEND_URL}/auth/reset-password?{query}"


def _send_email(to: str, subject: str, html: str):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"from": settings.FROM_EMAIL, "to": [to], "subject": subject, "html": html},
        timeout=10,
    )
    response.raise_for_status()


def _button(url: str, label: str) -> str:
    return (
        f'<p><a href="{escape(url)}" style="background-color:#3B76D1;color:white;'
        f'padding:10px 20px;text-decoration:none;border-radius:6px;display:inline-block;">'
        f"{label}</a></p>"
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_password_reset_email(self, user_id: str, token: str):
    try:
        user = User.objects.get(id=user_id)
        _send_email(
            user.email,
            "Reset your Octopus Dropship password",
            f"""
            <div style="font-family:sans-serif;padding:20px;">
              <h2>Password Reset Request</h2>
              <p>Click the button below to reset your password. This link expires in 1 hour.</p>
              {_button(_account_link(token, "recovery"), "Reset Password")}
              <p>If you didn't request this, you can safely ignore this email.</p>
            </div>
            """,
        )
        logger.info(f"Password reset email sent to {user.email}")
    except User.DoesNotExist:
        logger.warning(f"send_password_reset_email: user {user_id} not found")
    except Exception as exc:
        logger.error(f"send_password_reset_email failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_invite_email(self, user_id: str, token: str, shop_domain: str):
    try:
        user = User.objects.get(id=user_id)
        _send_email(
            user.email,
            "You've been invited to Octopus Dropship",
            f"""
            <div style="font-family:sans-serif;padding:20px;">
              <h2>You're invited</h2>
              <p>You have been added to the team for <strong>{escape(shop_domain)}</strong>
                 on Octopus Dropship.</p>
              <p>Set a password to activate your account. This link expires in 7 days.</p>
              {_button(_account_link(token, "invite"), "Set Password")}
            </div>
            """,
        )
        logger.info(f"Invite email sent to {user.email}")
    except User.DoesNotExist:
        logger.warning(f"send_invite_email: user {user_id} not found")
    except Exception as exc:
        logger.error(f"send_invite_email failed: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_password_changed_email(self, user_id: str):
    try:
        user = User.objects.get(id=user_id)
        _send_email(
            user.email,
            "Your Octopus Dropship password has been changed",
            """
            <div style="font-family:sans-serif;padding:20px;">
              <h2 style="color:#0f1654;">Password Updated Successfully</h2>
              <p>Your password for <strong>Octopus Dropship</strong> was successfully changed.</p>
              <p>If you did not perform this change, please contact our support team immediately.</p>
            </div>
            """,
        )
    except User.DoesNotExist:
        logger.warning(f"send_password_changed_email: user {user_id} not found")
    except Exception as exc:
        logger.error(f"send_password_changed_email failed: {exc}")
        raise self.retry(exc=exc)
