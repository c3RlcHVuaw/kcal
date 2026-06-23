#!/usr/bin/env sh
set -eu

backup="${1:-}"
container="${RESTORE_CHECK_CONTAINER:-kcal-restore-check-$$}"
image="${RESTORE_CHECK_IMAGE:-postgres:16-alpine}"
password="${RESTORE_CHECK_PASSWORD:-kcal_restore_check}"

if [ -z "$backup" ]; then
  echo "Usage: $0 path/to/backup.sql.gz" >&2
  exit 1
fi
if [ ! -f "$backup" ]; then
  echo "Backup file not found: $backup" >&2
  exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for database restore checks but was not found." >&2
  exit 1
fi

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

gzip -t "$backup"
docker rm -f "$container" >/dev/null 2>&1 || true
docker run -d --name "$container" \
  -e POSTGRES_USER=kcal \
  -e POSTGRES_PASSWORD="$password" \
  -e POSTGRES_DB=kcal \
  "$image" >/dev/null

until docker exec "$container" pg_isready -U kcal -d kcal >/dev/null 2>&1; do
  sleep 1
done
until docker exec "$container" psql -v ON_ERROR_STOP=1 -U kcal -d kcal -c "SELECT 1" >/dev/null 2>&1; do
  sleep 1
done

gzip -dc "$backup" | docker exec -i "$container" \
  psql -v ON_ERROR_STOP=1 --single-transaction -U kcal -d kcal >/dev/null
docker exec "$container" psql -v ON_ERROR_STOP=1 -U kcal -d kcal -c "SELECT 1" >/dev/null

echo "Restore check passed for $backup"
