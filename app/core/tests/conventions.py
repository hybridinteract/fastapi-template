"""Shared helpers for the convention tests.

These tests read the source with ``ast`` instead of importing it, so they keep working
while a module is half-built and they cost nothing to run — no database, no app import,
no event loop.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent.parent
REPO = APP.parent

SKIP_PARTS = {"__pycache__", "tests"}

# Directories under app/ that are not business modules.
NON_MODULE_DIRS = {"core", "apis"}


def python_files(*patterns: str) -> list[Path]:
    """Every file under app/ matching any glob, minus caches and test packages."""
    out: set[Path] = set()
    for pattern in patterns:
        for p in APP.rglob(pattern):
            if p.is_file() and not SKIP_PARTS & set(p.parts):
                out.add(p)
    return sorted(out)


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def business_modules() -> list[Path]:
    """Top-level packages under app/ that are business modules."""
    return sorted(
        d
        for d in APP.iterdir()
        if d.is_dir()
        and not d.name.startswith((".", "_"))
        and d.name not in NON_MODULE_DIRS
        and (d / "__init__.py").exists()
    )


# The layer names, in either form: `models.py` or `models/`.
LAYER_NAMES = ("models", "schemas", "crud", "services", "service", "routes")


def _holds_a_layer(package: Path) -> bool:
    return any(
        (package / f"{name}.py").exists() or (package / name).is_dir() for name in LAYER_NAMES
    )


def sub_modules(module: Path) -> list[Path]:
    """Sub-packages of a module that are themselves modules — they hold layers.

    `app/iam/auth/providers/` is a package but holds no layer, so it is a sibling file
    that happens to be a folder, not a sub-module.
    """
    return sorted(
        child
        for child in module.iterdir()
        if child.is_dir()
        and (child / "__init__.py").exists()
        and child.name != "tests"
        and not child.name.endswith("_doc")
        and _holds_a_layer(child)
    )


def module_shape(module: Path) -> str:
    """Which of the four shapes this module is — see docs/MODULE_CONVENTIONS.md §6.

    Read from the filesystem rather than declared anywhere, so a module cannot claim a
    shape its layout does not match.
    """
    if len(sub_modules(module)) >= 2:
        return "composite"
    if not _holds_a_layer(module):
        return "kernel"
    if any((module / name).is_dir() for name in LAYER_NAMES):
        return "layered"
    return "flat"


def crud_files() -> list[Path]:
    """Files that make up the CRUD layer, flat or as a package."""
    return [p for p in python_files("crud.py", "crud/*.py") if p.name != "__init__.py"]


def service_and_route_files() -> list[Path]:
    return [
        p
        for p in python_files(
            "services.py",
            "service.py",
            "services/*.py",
            "routes.py",
            "routes/*.py",
        )
        if p.name != "__init__.py"
    ]
