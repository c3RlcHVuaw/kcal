#!/usr/bin/env python3
"""Guard the Mini App against module-level bindings used before they exist.

app.js runs top-level statements — `tg.ready()`, the first render, `loadAll()` —
while it is still being evaluated. Function declarations hoist, so a helper
called from there can run before a `const` further down the file has been
initialised. That throws a ReferenceError, kills the whole module, and the app
silently renders nothing: it happened on 2026-08-20 with the calorie ring
constant, and `node --check` cannot see it because the syntax is valid.

The rule this enforces is simply "declare module-level bindings above the first
top-level call", which is where they belong anyway.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

WEBAPP_DIR = Path(__file__).resolve().parent.parent / "src" / "kcal_tracker" / "webapp_static"
SCRIPTS = ("app.js", "app_core.js", "ios26.js")

# A statement at column zero that invokes something: `loadAll();`, `tg?.ready();`
TOP_LEVEL_CALL = re.compile(r"^[A-Za-z_$][\w$.?]*\s*\(")
DECLARATION = re.compile(r"^(?:const|let)\s+([\w$]+)")
KEYWORDS = ("function", "if", "for", "while", "switch", "catch", "return", "new")


def first_top_level_call(lines: list[str]) -> int | None:
    for number, line in enumerate(lines, start=1):
        if line.startswith(KEYWORDS):
            continue
        if TOP_LEVEL_CALL.match(line):
            return number
    return None


def late_declarations(lines: list[str], boundary: int) -> list[tuple[int, str]]:
    found = []
    for number, line in enumerate(lines, start=1):
        if number <= boundary:
            continue
        match = DECLARATION.match(line)
        if match:
            found.append((number, match.group(1)))
    return found


def main() -> int:
    problems = []
    for name in SCRIPTS:
        path = WEBAPP_DIR / name
        if not path.exists():
            continue
        lines = path.read_text().splitlines()
        boundary = first_top_level_call(lines)
        if boundary is None:
            continue
        for number, identifier in late_declarations(lines, boundary):
            problems.append(
                f"{name}:{number}: module-level '{identifier}' is declared after the "
                f"first top-level call on line {boundary}; a function running during "
                f"module evaluation would hit its temporal dead zone. Move it up."
            )

    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
