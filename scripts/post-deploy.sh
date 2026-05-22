#!/usr/bin/env sh
set -eu

base_url="${1:-${PUBLIC_API_URL:-}}"
if [ -z "$base_url" ]; then
  echo "Usage: $0 https://your-api.example.com" >&2
  echo "Or set PUBLIC_API_URL." >&2
  exit 1
fi

docker compose pull || true
docker compose up -d --build
docker compose ps
./scripts/smoke.sh "$base_url"
docker compose logs --tail=100 api bot
