#!/usr/bin/env sh
set -eu

image="${VALIDATE_IMAGE:-kcal-tracker-validate}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for Docker validation but was not found." >&2
  exit 1
fi

docker build -t "$image" .
docker run --rm --entrypoint sh "$image" -c '
  python -m compileall src tests migrations &&
  ruff check src migrations tests &&
  pytest -q
'
docker compose config
