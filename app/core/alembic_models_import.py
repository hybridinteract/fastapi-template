"""
Alembic Models Import

This file imports all models so Alembic autogenerate can detect schema changes.
Add an import line here for every new module's models.

Convention:
    # <Module name> module models
    from app.<module>.models import <Model1>, <Model2>
"""

# Import Base for metadata
from app.core.models import Base

# User module models (auth + RBAC)
from app.user.models import User, Role, Permission, RefreshToken, UserRole, RolePermission

# Activity module models (append-only audit log)
from app.activity.models import ActivityLog

# Release notes module models (What's New system)
from app.release_notes.models import ReleaseNote

# ──── Add new module models below ────
# from app.<module>.models import <Model>
