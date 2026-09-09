"""Extension points for downstream projects."""


class ExtraUserFieldsMixin:
    """
    Mixin to add extra fields to the User model from downstream projects.

    Example:
        # In downstream project's models.py:
        from sqlalchemy.orm import Mapped, mapped_column
        from sqlalchemy import String
        from app.user.user.models import User

        class ProjectUser(User):
            __tablename__ = "users"
            __table_args__ = {"extend_existing": True}
            organization_id: Mapped[str] = mapped_column(String(50), nullable=True)
    """
    pass


def extra_permissions() -> list[tuple[str, str, str]]:
    """Return additional (resource, action, description) tuples."""
    return []


def extra_roles() -> list[dict]:
    """Return additional role dicts: {"name": str, "description": str, "is_system": bool}."""
    return []


def extra_role_permissions() -> dict[str, list[str]]:
    """Return additional role->permission mappings: {"role_name": ["resource:action", ...]}."""
    return {}
