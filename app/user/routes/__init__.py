"""
User module routes aggregator.

Exports:
  - auth_router: Authentication endpoints (/api/v1/auth/*)
  - user_router: User self-service endpoints (/api/v1/users/me/*)
  - user_management_router: Admin user management (/api/v1/admin/users/*)
"""

from fastapi import APIRouter

from app.user.auth_management.routes import router as _auth_routes
from app.user.routes.admin_routes import router as _admin_routes
from app.user.routes.user_routes import router as _user_routes

# Auth routes: /api/v1/auth/*
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
auth_router.include_router(_auth_routes)

# User self-service routes: /api/v1/users/me/*
user_router = _user_routes

# Admin routes: /api/v1/admin/users/* (prefix set in admin_routes.py)
user_management_router = _admin_routes
