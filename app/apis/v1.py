"""
API Version 1 Router.

Aggregates all module routers for API v1.
Register new module routers here following the existing pattern.
"""

from fastapi import APIRouter

from app.activity.routes import router as activity_router
from app.iam import admin_router, auth_router, rbac_router, user_router
from app.release_notes.routes import router as release_notes_router

# ──── Add new module routers below ────
# from app.<module>.routes import <module>_router

# Version 1 API Router
router = APIRouter()

# Core user / auth routers.
#
# ORDER IS LOAD-BEARING — do not sort these alphabetically or by module.
# FastAPI matches in registration order and stops at the first hit, and a path parameter
# matches any single segment. All three of these routers live under /users:
#
#     user_router   /users/me      (literal)
#     rbac_router   /users/meta    (literal)
#     admin_router  /users         (has /{user_id} routes)
#
# The literal prefixes MUST come first. With admin_router ahead of rbac_router,
# `POST /users/meta/roles` is matched by `POST /users/{user_id}/roles` with
# user_id="meta", and the caller gets a UUID parse error about a field they never sent.
# app/apis/tests/test_route_registration.py fails if anyone reorders them.
router.include_router(auth_router)
router.include_router(user_router)
router.include_router(rbac_router)
router.include_router(admin_router)

# Utility routers (always included)
router.include_router(activity_router)
router.include_router(release_notes_router)

# ──── Include new module routers below ────
# router.include_router(<module>_router)
