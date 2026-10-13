"""The rule that holds this module together, as a test.

A sub-module may import only LOWER ranks. Nothing ever points the other way — not at
module level, not deferred, not inside a function.

It reads source with ``ast`` rather than inspecting imported modules, because a deferred
import inside a function is exactly the form the breach takes, and an import-graph check
cannot see one.
"""

from __future__ import annotations

import ast
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent.parent
MODULE = MODULE_ROOT.name

#: Lowest rank first. A sub-module may import only the ones BEFORE it.
RANK: list[str] = ["<sub_0>", "<sub_1>", "<sub_2>"]

#: Guards the guard: if a rename makes the walk find nothing, these tests would pass
#: forever while checking nothing.
MIN_FILES_PER_SUB = 3


def _py(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _package_parts(path: Path) -> list[str]:
    """app/<module>/<sub>/crud/x.py -> ['app', '<module>', '<sub>', 'crud']"""
    return list(path.relative_to(MODULE_ROOT.parent.parent).parts[:-1])


def _resolve(node: ast.ImportFrom, parts: list[str]) -> str | None:
    """The absolute module an ImportFrom names, relative dots resolved.

    `from ..other import X` inside `<sub>/services/` must resolve the same way it does
    inside `<sub>/` — counting dots, never string-matching, or relative imports slip
    through and the test passes vacuously.
    """
    if node.level == 0:
        return node.module
    base = parts[: len(parts) - (node.level - 1)]
    if node.module:
        base = [*base, *node.module.split(".")]
    return ".".join(base)


def _imports_of(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    parts = _package_parts(path)
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(node.lineno, a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            resolved = _resolve(node, parts)
            if resolved:
                out.append((node.lineno, resolved))
    return out


def _names(sub: str) -> str:
    return f"app.{MODULE}.{sub}"


def test_no_submodule_imports_a_higher_rank() -> None:
    offences: list[str] = []

    for i, sub in enumerate(RANK):
        higher = RANK[i + 1 :]
        root = MODULE_ROOT / sub
        if not root.exists():
            continue
        for path in _py(root):
            for lineno, imported in _imports_of(path):
                for other in higher:
                    target = _names(other)
                    if imported == target or imported.startswith(f"{target}."):
                        rel = path.relative_to(MODULE_ROOT)
                        offences.append(f"{rel}:{lineno}  {sub}/ -> {other}/  ({imported})")

    assert not offences, (
        "A sub-module imported a HIGHER rank, which inverts the dependency:\n  "
        + "\n  ".join(offences)
        + f"\n\nRank (lowest first): {' < '.join(RANK)}."
        "\nServe the data downward from the higher-ranked sub-module instead, or move the"
        "\nshared thing into the lower one. Do not weaken this test."
    )


def test_the_walk_is_actually_finding_files() -> None:
    """A renamed sub-module would make the test above pass while checking nothing."""
    for sub in RANK:
        root = MODULE_ROOT / sub
        if not root.exists():
            continue
        n = len(_py(root))
        assert n >= MIN_FILES_PER_SUB, (
            f"Only {n} files under {root}. The boundary test is walking the wrong "
            "directory and is passing without checking anything."
        )


def test_dependencies_does_not_hand_a_higher_rank_to_a_lower_one() -> None:
    """The one place the boundary can invert with no file under a sub-module importing up.

    ``dependencies.py`` legitimately imports every sub-module, so a factory that passed a
    rank-2 service into a rank-0 constructor would pass every check above — the import
    lives in this file, not in the sub-module.
    """
    source = (MODULE_ROOT / "dependencies.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="dependencies.py")

    origin: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        for i, sub in enumerate(RANK):
            if node.module == _names(sub) or node.module.startswith(f"{_names(sub)}."):
                for alias in node.names:
                    origin[alias.asname or alias.name] = i

    offences: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = getattr(node.func, "id", None)
        if callee not in origin:
            continue
        for arg in node.args:
            named = getattr(arg, "id", None) or getattr(getattr(arg, "func", None), "id", None)
            if named in origin and origin[named] > origin[callee]:
                offences.append(
                    f"line {node.lineno}: {callee} (rank {origin[callee]}) "
                    f"was handed {named} (rank {origin[named]})"
                )

    assert not offences, (
        "dependencies.py inverted the rank through constructor injection:\n  "
        + "\n  ".join(offences)
        + "\n\nNo file under the sub-module imports upward, so the ast check above cannot"
        "\nsee this. It is still the boundary breaking."
    )
