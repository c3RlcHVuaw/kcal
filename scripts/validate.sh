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
"$python_bin" -m py_compile scripts/*.py
"$python_bin" -m ruff check src migrations tests scripts/*.py
for script in scripts/*.sh; do
  sh -n "$script"
done
"$python_bin" -m pytest -q

require_node="${VALIDATE_REQUIRE_NODE:-${CI:-false}}"
require_docker="${VALIDATE_REQUIRE_DOCKER:-${CI:-false}}"

if command -v node >/dev/null 2>&1; then
  node --check src/kcal_tracker/webapp_static/app_core.js
  node --check src/kcal_tracker/webapp_static/app.js
else
  if [ "$require_node" = "true" ] || [ "$require_node" = "1" ]; then
    echo "node is required for webapp JavaScript syntax checks." >&2
    exit 1
  fi
  echo "node was not found; skipping webapp JavaScript syntax checks." >&2
fi
if command -v docker >/dev/null 2>&1; then
  docker compose config
else
  if [ "$require_docker" = "true" ] || [ "$require_docker" = "1" ]; then
    echo "docker is required for docker compose config validation." >&2
    exit 1
  fi
  echo "docker was not found; skipping docker compose config." >&2
fi
