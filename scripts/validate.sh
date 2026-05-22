#!/usr/bin/env sh
set -eu

python_bin="${PYTHON:-}"
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

for tool in ruff pytest docker; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "$tool is required for validation but was not found." >&2
    exit 1
  fi
done

"$python_bin" -m compileall src tests migrations
ruff check src migrations tests
pytest -q
docker compose config
