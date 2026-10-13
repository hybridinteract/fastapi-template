"""Router registration order in ``app/apis/v1.py`` is load-bearing.

``CLAUDE.md`` §3 · ``.claude/rules/routes-and-di.md`` rule 8 · conventions §11.

FastAPI matches routes in registration order and stops at the first hit. A path parameter
matches any single segment, so a router mounted at ``/users`` with a ``/{user_id}`` route
will swallow ``/users/me`` and ``/users/meta/...`` if it is registered first. The caller
does not get a 404 — they get a UUID parse error about a field they never sent, which is
a genuinely confusing bug to receive.

The check below is deliberately **method-agnostic**. Two routes that collide on path but
differ on verb are safe *today* and become a live bug the moment somebody adds the missing
verb to the wildcard router — which is exactly the change nobody thinks to check.
"""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI

from app.apis.v1 import router

PARAM = re.compile(r"\{[^}]+\}")


def _paths() -> list[str]:
    """Registered paths, in the order the matcher walks them.

    `include_router` is lazy in FastAPI 0.141 — sub-routers stay wrapped in
    `_IncludedRouter` until something forces resolution, so `app.routes` holds no
    `APIRoute` objects to read. Generating the OpenAPI schema resolves them, and its
    `paths` mapping preserves registration order. It is also public API, which a walk
    over the private wrapper would not be.
    """
    app = FastAPI()
    app.include_router(router)
    return list(app.openapi()["paths"])


def _matcher(path: str) -> re.Pattern[str]:
    return re.compile("^" + PARAM.sub(r"[^/]+", re.escape(path).replace(r"\{", "{")) + "$")


def test_routes_are_registered() -> None:
    assert _paths(), "app/apis/v1.py registered no routes — did an include_router go missing?"


def test_no_literal_path_is_shadowed_by_an_earlier_wildcard() -> None:
    paths = _paths()
    shadowed: list[str] = []

    for i, path in enumerate(paths):
        if PARAM.search(path):
            continue  # only literal paths can be shadowed
        for earlier in paths[:i]:
            if PARAM.search(earlier) and _matcher(earlier).match(path):
                shadowed.append(f"{path}  is shadowed by  {earlier}  (registered earlier)")

    assert not shadowed, (
        "Reorder the include_router() calls in app/apis/v1.py: the router with the more\n"
        "specific literal prefix must be registered FIRST.\n  " + "\n  ".join(shadowed)
    )


@pytest.mark.parametrize("literal", ["/users/me", "/users/meta"])
def test_known_literal_prefixes_precede_the_wildcard_user_router(literal: str) -> None:
    """The two prefixes this template ships that live under /users.

    Named explicitly so that deleting the guard is a deliberate act rather than a
    reordering nobody noticed.
    """
    paths = _paths()
    first_literal = next((i for i, p in enumerate(paths) if p.startswith(literal)), None)
    if first_literal is None:
        pytest.skip(f"no routes under {literal}")

    wildcard = next(
        (i for i, p in enumerate(paths) if p.startswith("/users/{")),
        None,
    )
    if wildcard is None:
        pytest.skip("no wildcard /users/{...} routes")

    assert first_literal < wildcard, (
        f"{literal} routes are registered after /users/{{user_id}} routes.\n"
        "Move that include_router() call earlier in app/apis/v1.py."
    )
