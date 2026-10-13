"""Auth submodule — assembles the /auth router from shared routes + enabled providers."""

from fastapi import APIRouter

from app.iam.auth.providers import PROVIDERS
from app.iam.auth.routes import router as _core_router


def build_auth_router(prefix: str = "/auth") -> APIRouter:
    """Compose the auth router: shared routes + each enabled provider's sub-router."""
    router = APIRouter(prefix=prefix)
    router.include_router(_core_router)
    for prov in PROVIDERS:
        router.include_router(prov.router)
    return router


auth_router = build_auth_router()


__all__ = ["auth_router", "build_auth_router"]
