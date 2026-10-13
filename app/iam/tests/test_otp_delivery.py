"""The ``noop`` SMS sender never puts an OTP code in a production log.

``noop`` is the default provider and the only one implemented. It delivers a code by logging
it, which is the point in development and a credential leak in production: anyone who can
read the logs could sign in as any phone user. In production it refuses with a 503 instead.
"""

import pytest

from app.core.settings import settings
from app.iam.auth.exceptions import SmsProviderNotConfiguredError
from app.iam.auth.providers.phone_otp import _send_otp

CODE = "493817"


def test_noop_sender_refuses_in_production(monkeypatch, caplog) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    with caplog.at_level("DEBUG"), pytest.raises(SmsProviderNotConfiguredError) as refused:
        _send_otp("+15550000000", CODE, "noop")

    assert refused.value.status_code == 503
    assert CODE not in caplog.text


def test_noop_sender_delivers_in_development(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    assert _send_otp("+15550000000", CODE, "noop") is None
