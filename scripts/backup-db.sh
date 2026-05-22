#!/usr/bin/env sh
set -eu

backup_dir="${BACKUP_DIR:-backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
output="${1:-$backup_dir/kcal-$timestamp.sql.gz}"

mkdir -p "$(dirname "$output")"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for database backups but was not found." >&2
  exit 1
fi

docker compose exec -T postgres pg_dump -U kcal -d kcal --clean --if-exists \
  | gzip -c > "$output"

echo "Database backup written to $output"
