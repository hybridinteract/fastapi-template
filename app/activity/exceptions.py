"""Activity-log domain exceptions.

None yet. The routes are a gated list and a bulk delete by ID, and neither has a failure that
needs its own exception. The file exists because every module owns an ``exceptions.py``
(``CLAUDE.md`` §6): when a route first needs to fail, add a named exception here rather than
raising ``HTTPException`` inline.
"""

__all__: list[str] = []
