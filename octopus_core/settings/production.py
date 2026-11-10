"""Production settings — strict security, no debug."""
import os

from .base import *  # noqa: F401, F403

DEBUG = False

# Security headers.
# When the backend runs on a private Docker network (only the Next.js server
# reaches it, over plain http://backend:8000), set BEHIND_HTTPS=False: an HTTPS
# redirect would break those internal calls. Keep True if it ever gets a public
# HTTPS domain.
BEHIND_HTTPS = os.getenv("BEHIND_HTTPS", "True") == "True"
SECURE_SSL_REDIRECT = BEHIND_HTTPS
SECURE_HSTS_SECONDS = 31536000 if BEHIND_HTTPS else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = BEHIND_HTTPS
SECURE_HSTS_PRELOAD = BEHIND_HTTPS
SESSION_COOKIE_SECURE = BEHIND_HTTPS
CSRF_COOKIE_SECURE = BEHIND_HTTPS
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
