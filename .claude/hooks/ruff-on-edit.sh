#!/usr/bin/env bash
# PostToolUse hook: format and autofix a Python file right after an agent edits it.
#
# Keeps NEW code clean without touching the inherited baseline (see the note in
# .github/workflows/ci.yml). Only the edited file is touched.
#
# Always exits 0 — a formatter that can block an edit is worse than an unformatted file.
set -u

payload=$(cat)
file=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))
except Exception:
    print("")
' 2>/dev/null)

[ -z "$file" ] && exit 0
case "$file" in
  *.py) ;;
  *) exit 0 ;;
esac
[ -f "$file" ] || exit 0

# migrations/versions is excluded from ruff on purpose — generated files are not styled.
case "$file" in
  */migrations/versions/*) exit 0 ;;
esac

uv run ruff format -q "$file"          >/dev/null 2>&1
uv run ruff check -q --fix "$file"     >/dev/null 2>&1
exit 0
