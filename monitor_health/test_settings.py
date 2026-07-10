from .settings import *

# Use SQLite for tests (no pgvector issues)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable migrations (fixes VectorExtension crash)
MIGRATION_MODULES = {
    "core": None,
}