"""
API Version 1 Router.

Aggregates all module routers for API v1.
Register new module routers here following the existing pattern.
"""

from fastapi import APIRouter

from app.user import auth_router, user_router, admin_router, rbac_router
from app.activity.routes import router as activity_router
from app.release_notes.routes import router as release_notes_router

# ──── Add new module routers below ────
# from app.<module>.routes import <module>_router

# Version 1 API Router
router = APIRouter()

# Core user / auth routers
router.include_router(auth_router)
router.include_router(user_router)
router.include_router(admin_router)
router.include_router(rbac_router)

# Utility routers (always included)
router.include_router(activity_router)
router.include_router(release_notes_router)

# ──── Include new module routers below ────
# router.include_router(<module>_router)
