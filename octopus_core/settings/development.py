"""Development settings — local machine only."""
from .base import *  # noqa: F401, F403

DEBUG = True

# Show all SQL queries in dev console
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
    },
}

# Relaxed CORS in dev
CORS_ALLOW_ALL_ORIGINS = True
