"""Test settings — in-memory SQLite, inline Celery, no external services."""
from .development import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CELERY_TASK_ALWAYS_EAGER = True
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",  # fast hashing for tests only
    *PASSWORD_HASHERS,  # noqa: F405
]
LOGGING = {"version": 1, "disable_existing_loggers": False}

# Throttle counters live in the cache; a dummy cache keeps tests independent.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
