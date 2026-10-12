#!/usr/bin/env python3
"""Documentation checker — links resolve, stamps stay fresh, rules stay path-scoped.

Four ways this repo's documentation goes wrong on its own, without anybody touching it:

  1. A file moves or is deleted and every link into it dies. Renames are routine here
     (``app/user`` -> ``app/iam`` rewrote 148 references); finding the stale links by
     hand does not scale.
  2. A doc quietly ages past the point where anyone should trust it. Every file under
     ``docs/`` and ``.claude/rules/`` carries ``Last verified against the code: <DD Month
     YYYY>``. An unstamped or silently-stale doc is worse than no doc, because a reader
     cannot tell July-true from today-true.
  3. A file in ``.claude/rules/`` loses its ``paths:`` frontmatter. It then loads into
     **every** session instead of only the ones that touch the code it governs — the exact
     cost the rules directory exists to avoid, and invisible until someone reads
     ``/context``.
  4. ``CLAUDE.md`` grows. It is read in full at the start of every session, so every line
     costs attention on every future task. The budget is a hard gate, not a suggestion.

Module anatomy — whether ``app/<module>/<module>_doc/how-it-works.md`` exists — is checked
by ``app/core/tests/test_module_anatomy.py``, not here. One owner per rule.

Usage
-----
    python3 scripts/check_docs.py                 # everything
    python3 scripts/check_docs.py --links-only
    python3 scripts/check_docs.py --max-age 60
    python3 scripts/check_docs.py --strict        # stale stamps become errors
    python3 scripts/check_docs.py --quiet         # only problems

Standard library only, so it runs anywhere without installing the project. Exit code is 1
if any *error* was found; stale stamps are warnings unless ``--strict``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    ".ruff_cache",
    "site-packages",
    ".mypy_cache",
}

# Subtrees whose every .md must carry a freshness stamp.
STAMP_ROOTS = ("docs", ".claude/rules")

# Files that carry no stamp on purpose: templates, and the guardrail itself (which is
# re-read constantly and would churn the date on every commit).
STAMP_EXEMPT = {
    "docs/planning/_TEMPLATE.md",
    "docs/research/_TEMPLATE.md",
}

CLAUDE_MD = "CLAUDE.md"
CLAUDE_MD_MAX_LINES = 200

RULES_DIR = ".claude/rules"

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+?)(?:\s+\"[^\"]*\")?\)")
STAMP_RE = re.compile(r"Last verified against the code:\s*\**\s*(\d{1,2}\s+\w+\s+\d{4})")
EXTERNAL = ("http://", "https://", "mailto:", "tel:", "#")


def _is_nested_checkout(d: Path) -> bool:
    """A git worktree or clone nested inside the repo (agent scratch copies).

    Scanning one tells you nothing about this tree, and every ``../`` link in it
    resolves outside the checkout and reads as dead.
    """
    return d != REPO and (d / ".git").exists()


def markdown_files() -> list[Path]:
    out: list[Path] = []

    def walk(d: Path) -> None:
        for child in sorted(d.iterdir()):
            if child.is_dir():
                if child.name in SKIP_DIRS or _is_nested_checkout(child):
                    continue
                walk(child)
            elif child.suffix == ".md":
                out.append(child)

    walk(REPO)
    return out


def check_links(files: list[Path]) -> tuple[list[str], int]:
    errors, checked = [], 0
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in LINK_RE.finditer(text):
            target = m.group(1)
            if target.startswith(EXTERNAL):
                continue
            path = target.split("#")[0]
            if not path:
                continue
            checked += 1
            if not (f.parent / path).resolve().exists():
                line = text[: m.start()].count("\n") + 1
                errors.append(f"{f.relative_to(REPO)}:{line}  dead link -> {target}")
    return errors, checked


def check_stamps(files: list[Path], max_age: int) -> tuple[list[str], list[str], int]:
    today = dt.date.today()
    missing, stale, checked = [], [], 0
    for f in files:
        rel = f.relative_to(REPO).as_posix()
        if not rel.startswith(tuple(f"{r}/" for r in STAMP_ROOTS)) or rel in STAMP_EXEMPT:
            continue
        checked += 1
        m = STAMP_RE.search(f.read_text(encoding="utf-8", errors="replace"))
        if not m:
            missing.append(f"{rel}  no 'Last verified against the code' stamp")
            continue
        try:
            stamped = dt.datetime.strptime(m.group(1).strip(), "%d %B %Y").date()
        except ValueError:
            missing.append(f"{rel}  unparseable stamp date: {m.group(1)!r}")
            continue
        age = (today - stamped).days
        if age > max_age:
            stale.append(f"{rel}  stamp is {age} days old ({m.group(1)})")
    return missing, stale, checked


def check_rule_frontmatter() -> tuple[list[str], int]:
    """Every .claude/rules/*.md must declare `paths:` in YAML frontmatter.

    A rule without it is loaded unconditionally at the start of every session.
    """
    errors, checked = [], 0
    rules = REPO / RULES_DIR
    if not rules.is_dir():
        return errors, checked
    for f in sorted(rules.rglob("*.md")):
        checked += 1
        rel = f.relative_to(REPO).as_posix()
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        if not lines or lines[0].strip() != "---":
            errors.append(f"{rel}  no YAML frontmatter — would load on EVERY session")
            continue
        try:
            end = lines.index("---", 1)
        except ValueError:
            errors.append(f"{rel}  frontmatter is never closed with '---'")
            continue
        if not any(ln.startswith("paths:") for ln in lines[1:end]):
            errors.append(f"{rel}  frontmatter has no 'paths:' — would load on EVERY session")
    return errors, checked


def check_claude_md_budget() -> list[str]:
    f = REPO / CLAUDE_MD
    if not f.exists():
        return [f"{CLAUDE_MD}  missing — agents start every session with no guardrail"]
    n = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
    if n > CLAUDE_MD_MAX_LINES:
        return [
            f"{CLAUDE_MD}  {n} lines, budget is {CLAUDE_MD_MAX_LINES}. "
            "Move a rule into .claude/rules/ or docs/ and leave one line pointing at it."
        ]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--max-age", type=int, default=30, help="days before a stamp is called stale (default: 30)"
    )
    ap.add_argument("--links-only", action="store_true", help="skip every other check")
    ap.add_argument("--strict", action="store_true", help="treat stale stamps as errors")
    ap.add_argument("--quiet", action="store_true", help="print only problems")
    args = ap.parse_args()

    files = markdown_files()
    errors: list[str] = []
    say = (lambda *_: None) if args.quiet else print

    link_errors, n_links = check_links(files)
    errors += link_errors
    say(f"links   : {n_links} checked, {len(link_errors)} dead")

    if not args.links_only:
        missing, stale, n_stamped = check_stamps(files, args.max_age)
        errors += missing
        if args.strict:
            errors += stale
        say(
            f"stamps  : {n_stamped} checked, {len(missing)} missing, "
            f"{len(stale)} older than {args.max_age}d"
        )
        for s in stale:
            print(f"  warn  {s}")

        rule_errors, n_rules = check_rule_frontmatter()
        errors += rule_errors
        say(f"rules   : {n_rules} checked, {len(rule_errors)} not path-scoped")

        budget_errors = check_claude_md_budget()
        errors += budget_errors
        n = len((REPO / CLAUDE_MD).read_text().splitlines()) if (REPO / CLAUDE_MD).exists() else 0
        say(f"guardrail: {CLAUDE_MD} is {n}/{CLAUDE_MD_MAX_LINES} lines")

    for e in errors:
        print(f"  ERROR {e}")

    if errors:
        print(f"\n{len(errors)} problem(s). Fix the doc, or the thing it points at.")
        return 1
    say("\nDocs OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
