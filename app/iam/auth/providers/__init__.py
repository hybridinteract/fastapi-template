"""Auth provider registration.

Each provider is a ``Provider`` dataclass exported as ``provider`` from a module
under this package. To add one:

1. Drop a new file in ``auth/providers/`` that exports
   ``provider = Provider(name=..., router=..., permissions=[...], role_permissions={...})``
2. Add a ``_register(...)`` line below, gated on a config flag if optional.

No Protocol, no registry class — just a flat list.
"""

from dataclasses import dataclass, field
from importlib import import_module

from fastapi import APIRouter

from app.iam.config import auth_config


@dataclass(frozen=True)
class Provider:
    name: str
    router: APIRouter
    permissions: list[tuple[str, str, str]] = field(default_factory=list)
    role_permissions: dict[str, list[str]] = field(default_factory=dict)


PROVIDERS: list[Provider] = []


def _register(module_name: str) -> None:
    """Import a provider module and append its ``provider`` to PROVIDERS."""
    mod = import_module(f"app.iam.auth.providers.{module_name}")
    PROVIDERS.append(mod.provider)


_register("email_password")  # always-on default

if auth_config.AUTH_GOOGLE_OAUTH_ENABLED:
    _register("google_oauth")

if auth_config.AUTH_PHONE_OTP_ENABLED:
    _register("phone_otp")
