"""Repo-wide pytest fixtures and the environment the suite needs to import the app.

``app/core/settings.py`` instantiates ``Settings()`` at module import time, and the
required secrets have no defaults — deliberately, so the app fails fast rather than
booting with a guessable key. The consequence is that *importing* any module under
``app`` needs those variables present.

pytest imports this file before it collects anything, so setting them here is what makes
``uv run pytest`` work on a fresh checkout with no ``.env``. The values are throwaway and
are only ever used by tests that never open a connection. Do not "fix" the settings module
to have defaults instead.
"""

from __future__ import annotations

import os

_TEST_ENV = {
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_DB": "test",
    "SECRET_KEY": "test-secret-key-not-used-for-anything-real",
    "JWT_SECRET_KEY": "test-jwt-secret-key-not-used-for-anything-real",
}

for _key, _value in _TEST_ENV.items():
    os.environ.setdefault(_key, _value)
