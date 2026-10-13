"""Every model must be visible to Alembic autogenerate.

``CLAUDE.md`` §3 · ``.claude/rules/models-and-migrations.md`` · conventions §8.

This is the highest-value test in the repo, because the failure is completely silent: a
model missing from ``app/core/alembic_models_import.py`` is not seen by
``alembic revision --autogenerate``, so no ``CREATE TABLE`` is emitted, the migration
looks fine in review, and the first query against the table fails in whichever environment
runs it first.

Read by AST rather than by importing, so a model in a half-built module still counts.
"""

from __future__ import annotations

import ast

from app.core.tests.conventions import APP, parse, python_files, rel

REGISTRY = APP / "core" / "alembic_models_import.py"


def _declared_models() -> dict[str, str]:
    """Every ``class X(Base)`` under app/, mapped to the file that declares it."""
    found: dict[str, str] = {}
    for path in python_files("models.py", "models/*.py"):
        if path == APP / "core" / "models.py":
            continue  # declares Base itself
        for node in parse(path).body:
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
            if "Base" in bases:
                found[node.name] = rel(path)
    return found


def _registered_names() -> set[str]:
    names: set[str] = set()
    for node in parse(REGISTRY).body:
        if isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def test_registry_file_exists() -> None:
    assert REGISTRY.exists(), f"{rel(REGISTRY)} is the single source of truth for autogenerate"


def test_every_model_is_registered() -> None:
    declared = _declared_models()
    registered = _registered_names()

    assert declared, "found no models at all — the AST walk is probably looking in the wrong place"

    missing = sorted(
        f"{name}  ({source})" for name, source in declared.items() if name not in registered
    )
    assert not missing, (
        f"These models are invisible to `alembic revision --autogenerate`.\n"
        f"Add them to {rel(REGISTRY)} — the imports look unused and are not:\n  "
        + "\n  ".join(missing)
    )


def test_registry_has_no_stale_entries() -> None:
    """An import for a model that no longer exists breaks `alembic` at import time."""
    declared = set(_declared_models())
    registered = _registered_names() - {"Base"}

    stale = sorted(registered - declared)
    assert not stale, (
        f"{rel(REGISTRY)} imports names that no model declares any more:\n  " + "\n  ".join(stale)
    )
