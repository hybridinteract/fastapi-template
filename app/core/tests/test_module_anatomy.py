"""Every business module matches the contract for its shape.

``CLAUDE.md`` §1 · ``docs/MODULE_CONVENTIONS.md`` §6.

A module missing one of these does not fail loudly — it quietly diverges, and the next
person copies the divergence. ``dependencies.py`` is the one that matters most: without it,
cross-module imports leak into services and the wiring stops being findable.

The required set depends on the shape, because two of the four shapes genuinely differ:
a **shared kernel** wires nothing, so it has no ``dependencies.py``; a **composite** module
carries its error vocabulary per sub-module rather than at the root. The shape is read from
the layout (``conventions.module_shape``) rather than declared, so a module cannot claim a
shape it does not have.
"""

from __future__ import annotations

from pathlib import Path

from app.core.tests.conventions import business_modules, module_shape, rel, sub_modules

#: What each shape must have at the module root.
REQUIRED_BY_SHAPE: dict[str, tuple[str, ...]] = {
    "flat": ("__init__.py", "dependencies.py", "exceptions.py"),
    "layered": ("__init__.py", "dependencies.py", "exceptions.py"),
    # A composite has ONE dependencies.py for every sub-module; its exceptions may live
    # at the root or per sub-module, and `_has_exceptions` below accepts either.
    "composite": ("__init__.py", "dependencies.py"),
    # A shared kernel wires nothing and exposes no HTTP: no dependencies.py, and its
    # exceptions are ValueError subclasses rather than HTTPException.
    "kernel": ("__init__.py", "exceptions.py"),
}


def _has_exceptions(module: Path) -> bool:
    """Root ``exceptions.py``, or one in every sub-module."""
    if (module / "exceptions.py").exists():
        return True
    subs = sub_modules(module)
    return bool(subs) and all((sub / "exceptions.py").exists() for sub in subs)


def test_there_are_business_modules() -> None:
    assert business_modules(), "found no business modules under app/ — the discovery is wrong"


def test_every_module_has_a_recognised_shape() -> None:
    """A shape the filesystem does not match is a module nobody can review against a contract."""
    unknown = [
        f"{rel(m)}  -> {module_shape(m)}"
        for m in business_modules()
        if module_shape(m) not in REQUIRED_BY_SHAPE
    ]
    assert not unknown, (
        "module_shape() returned something REQUIRED_BY_SHAPE has no entry for:\n  "
        + "\n  ".join(unknown)
    )


def test_every_module_has_the_required_files() -> None:
    missing: list[str] = []

    for module in business_modules():
        shape = module_shape(module)
        for filename in REQUIRED_BY_SHAPE[shape]:
            if not (module / filename).exists():
                missing.append(f"{rel(module)}/{filename}   ({shape} module)")
        if shape != "kernel" and not _has_exceptions(module):
            missing.append(
                f"{rel(module)}/exceptions.py   ({shape} module — "
                "at the root, or one in every sub-module)"
            )

    assert not missing, (
        "Every business module owns these — see docs/MODULE_CONVENTIONS.md §6.\n"
        "  dependencies.py is the only file that may import across modules.\n"
        "  exceptions.py is what services and routes raise instead of a raw HTTPException.\n  "
        + "\n  ".join(missing)
    )


def test_every_module_documents_itself() -> None:
    """Docs travel with the module, in app/<module>/<module>_doc/how-it-works.md."""
    missing: list[str] = []
    stray: list[str] = []

    for module in business_modules():
        note = module / f"{module.name}_doc" / "how-it-works.md"
        if not note.exists():
            missing.append(rel(note))
        # A loose .md beside the .py files means the module's docs have two homes.
        stray += [rel(p) for p in module.glob("*.md")]

    assert not missing, (
        "Write the module's developer note — one page: what it is for, its shape and the\n"
        "step that chose it, its tables, how a request flows through it, and the rules that\n"
        "are easy to trip over. app/iam/iam_doc/how-it-works.md is the reference.\n  "
        + "\n  ".join(missing)
    )
    assert not stray, (
        "Move these into the module's <module>_doc/ folder — no loose .md beside the code:\n  "
        + "\n  ".join(stray)
    )


def test_a_composite_module_keeps_one_of_each_shared_file() -> None:
    """A composite has ONE dependencies.py, tests/ and <module>_doc/ — at the root.

    A second `dependencies.py` inside a sub-module is how a composite stops being one
    module: each half grows its own cross-module imports and they quietly become two
    modules that need each other.
    """
    offences: list[str] = []

    for module in business_modules():
        if module_shape(module) != "composite":
            continue
        for sub in sub_modules(module):
            for filename in ("dependencies.py", "seed.py"):
                if (sub / filename).exists():
                    offences.append(f"{rel(sub)}/{filename}  belongs at {rel(module)}/{filename}")
            for folder in ("tests", f"{sub.name}_doc"):
                if (sub / folder).is_dir():
                    offences.append(f"{rel(sub)}/{folder}/  belongs at the module root")

    assert not offences, (
        "A composite module keeps one dependencies.py, one tests/ and one <module>_doc/ "
        "at its root:\n  " + "\n  ".join(offences)
    )
