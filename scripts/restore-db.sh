#!/usr/bin/env sh
set -eu

backup="${1:-}"
if [ -z "$backup" ]; then
  echo "Usage: $0 path/to/backup.sql.gz" >&2
  exit 1
fi
if [ ! -f "$backup" ]; then
  echo "Backup file not found: $backup" >&2
  exit 1
fi
if [ "${RESTORE_CONFIRM:-}" != "yes" ]; then
  echo "Refusing to restore without RESTORE_CONFIRM=yes." >&2
  exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for database restore but was not found." >&2
  exit 1
fi

gzip -dc "$backup" | docker compose exec -T postgres psql -U kcal -d kcal
echo "Database restore completed from $backup"
