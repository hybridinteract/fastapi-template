"""The layering contract, enforced.

``CLAUDE.md`` §2 and §6 · ``.claude/rules/layering.md`` · conventions §4, §13.

Both rules here fail **silently** in production when broken. A ``commit()`` in CRUD does
not raise — it just moves the transaction boundary, so a later failure in the same service
leaves half the write committed. A raw ``HTTPException`` in a service does not raise
either; it produces an error the frontend cannot distinguish from any other, and it
bypasses the module's own error vocabulary.
"""

from __future__ import annotations

import ast

from app.core.tests.conventions import (
    crud_files,
    parse,
    rel,
    service_and_route_files,
)

# app/core/database.py and app/core/background/internals/ ARE the transaction boundary;
# they are infrastructure, not a CRUD layer, and are not matched by crud_files() anyway.
TRANSACTION_METHODS = {"commit", "rollback"}


def test_crud_never_commits_or_rolls_back() -> None:
    """CRUD flushes; the service owns the transaction. Exactly one commit per mutation."""
    offenders: list[str] = []

    for path in crud_files():
        for node in ast.walk(parse(path)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in TRANSACTION_METHODS:
                offenders.append(f"{rel(path)}:{node.lineno}  .{func.attr}() in the CRUD layer")

    assert not offenders, (
        "CRUD must be flush-only — the service owns the transaction.\n"
        "Move the commit into the service that calls this.\n  " + "\n  ".join(offenders)
    )


def test_services_and_routes_raise_named_exceptions() -> None:
    """Every module owns an exceptions.py; nothing builds a raw HTTPException inline."""
    offenders: list[str] = []

    for path in service_and_route_files():
        for node in ast.walk(parse(path)):
            if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
                continue
            func = node.exc.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name == "HTTPException":
                offenders.append(f"{rel(path)}:{node.lineno}  raw HTTPException(...)")

    assert not offenders, (
        "Define a named exception in the module's exceptions.py and raise that instead.\n"
        "See app/release_notes/exceptions.py for the shape.\n  " + "\n  ".join(offenders)
    )
