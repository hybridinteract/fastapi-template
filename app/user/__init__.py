"""
User module for authentication and user management.

This module provides:
- User model and schemas
- Authentication (login, register, token refresh)
- User self-service operations
- User CRUD operations (admin)
"""

from .models import User
from .routes import auth_router, user_router, user_management_router

__all__ = [
    "User",
    "auth_router",
    "user_router",
    "user_management_router",
]
