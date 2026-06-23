#!/usr/bin/env sh
set -eu

services="${COMPOSE_REQUIRED_SERVICES:-api bot admin-bot postgres redis}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for compose service checks but was not found." >&2
  exit 1
fi

failed=0

for service in $services; do
  container_id="$(docker compose ps -q "$service" 2>/dev/null || true)"
  if [ -z "$container_id" ]; then
    echo "Compose service is missing: $service" >&2
    failed=1
    continue
  fi

  running="$(docker inspect -f '{{.State.Running}}' "$container_id")"
  health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")"

  if [ "$running" != "true" ]; then
    echo "Compose service is not running: $service" >&2
    failed=1
    continue
  fi

  if [ "$health" != "none" ] && [ "$health" != "healthy" ]; then
    echo "Compose service is not healthy: $service ($health)" >&2
    failed=1
    continue
  fi

  echo "Compose service ok: $service ($health)"
done

if [ "$failed" -ne 0 ]; then
  exit 1
fi
