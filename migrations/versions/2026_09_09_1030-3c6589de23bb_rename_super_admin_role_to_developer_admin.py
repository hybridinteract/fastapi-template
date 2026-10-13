"""rename super_admin role to developer_admin

Data-only migration. The `app/user` → `app/iam` module rename changed no
schema, but it did rename the bypass role from `super_admin` to
`developer_admin`. `seed.py` is additive — it creates roles it does not find
and never renames — so without this migration an upgraded project would end up
with a fresh `developer_admin` row beside the old `super_admin` one while
existing admins stayed on `super_admin`, silently losing their bypass.

Revision ID: 3c6589de23bb
Revises: 18da0849f81f
Create Date: 2026-09-09 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c6589de23bb'
down_revision: Union[str, None] = '18da0849f81f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Case A — only the old role exists: rename it in place, keeping its id, so
    # every user_roles / role_permissions row follows it untouched.
    op.execute(
        """
        UPDATE roles SET name = 'developer_admin'
        WHERE name = 'super_admin'
          AND NOT EXISTS (SELECT 1 FROM roles WHERE name = 'developer_admin')
        """
    )

    # Case B — both exist, because seed.py already ran against the new code.
    # Move the old role's holders onto the new role, then drop the old one
    # (role_id is ON DELETE CASCADE, so its join rows go with it).
    op.execute(
        """
        INSERT INTO user_roles (user_id, role_id, assigned_at)
        SELECT ur.user_id, dev.id, ur.assigned_at
        FROM user_roles ur
        JOIN roles old ON old.id = ur.role_id AND old.name = 'super_admin'
        JOIN roles dev ON dev.name = 'developer_admin'
        ON CONFLICT (user_id, role_id) DO NOTHING
        """
    )
    op.execute("DELETE FROM roles WHERE name = 'super_admin'")

    # Case C — neither exists (fresh database, seed not yet run): every
    # statement above is a no-op and seed.py creates developer_admin directly.


def downgrade() -> None:
    # Reverses the rename. A role dropped by Case B cannot be resurrected —
    # its holders were merged into developer_admin and that merge is not
    # separable after the fact.
    op.execute(
        """
        UPDATE roles SET name = 'super_admin'
        WHERE name = 'developer_admin'
          AND NOT EXISTS (SELECT 1 FROM roles WHERE name = 'super_admin')
        """
    )
