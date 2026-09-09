"""
Core platform permissions and roles.
"""

PLATFORM_ROLES = [
    {
        "name": "super_admin",
        "description": "Full system access. Bypasses all permission checks.",
        "is_system": True,
    },
    {
        "name": "admin",
        "description": "Administrative access: manage users, view reports, update settings.",
        "is_system": True,
    },
    {
        "name": "member",
        "description": "Standard authenticated user with basic access.",
        "is_system": True,
    },
]

PLATFORM_PERMISSIONS: list[tuple[str, str, str]] = [
    # ── Users ──
    ("users", "create",        "Create new user accounts"),
    ("users", "read",          "View user profiles"),
    ("users", "read_all",      "View all users in the system"),
    ("users", "update",        "Edit user accounts"),
    ("users", "delete",        "Delete user accounts"),
    ("users", "manage_roles",  "Assign/remove roles from users"),
    ("users", "reset_password","Reset user passwords"),
    ("users", "deactivate",    "Deactivate user accounts"),

    # ── Activity ──
    ("activity", "read",       "View activity logs"),
    ("activity", "read_all",   "View all activity logs"),
    ("activity", "read_own",   "View own activity"),

    # ── System ──
    ("system", "settings_read",    "View system settings"),
    ("system", "settings_update",  "Modify system settings"),
    ("system", "permissions_read", "View permissions matrix"),
    ("system", "permissions_update","Modify role permissions"),

    # ── Reports ──
    ("reports", "read",     "View reports and analytics"),
    ("reports", "read_own", "View own performance reports"),
    ("reports", "export",   "Export reports"),
]

PLATFORM_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "super_admin": [f"{r}:{a}" for r, a, _ in PLATFORM_PERMISSIONS],
    "admin": [
        "users:create",
        "users:read",
        "users:read_all",
        "users:update",
        "users:delete",
        "users:manage_roles",
        "users:reset_password",
        "users:deactivate",
        "activity:read",
        "activity:read_all",
        "system:settings_read",
        "system:permissions_read",
        "reports:read",
        "reports:export",
    ],
    "member": [
        "users:read",
        "activity:read_own",
        "reports:read_own",
    ],
}
