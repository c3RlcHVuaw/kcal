#!/usr/bin/env sh
set -eu

python_bin="${PYTHON:-}"
if [ -z "$python_bin" ]; then
  if [ -x ".venv/bin/python" ]; then
    python_bin=".venv/bin/python"
  fi
fi

if [ -z "$python_bin" ]; then
  for candidate in python3.12 python python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      python_bin="$candidate"
      break
    fi
  done
fi

if [ -z "$python_bin" ]; then
  echo "Python 3.12+ is required but no Python executable was found." >&2
  exit 1
fi

"$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' || {
  echo "Python 3.12+ is required. Set PYTHON=/path/to/python3.12 or install python3.12." >&2
  exit 1
}

"$python_bin" -m compileall src tests migrations
"$python_bin" -m ruff check src migrations tests
"$python_bin" -m pytest -q
if command -v node >/dev/null 2>&1; then
  node --check src/kcal_tracker/webapp_static/app_core.js
  node --check src/kcal_tracker/webapp_static/app.js
else
  echo "node was not found; skipping webapp JavaScript syntax checks." >&2
fi
if command -v docker >/dev/null 2>&1; then
  docker compose config
else
  echo "docker was not found; skipping docker compose config." >&2
fi
