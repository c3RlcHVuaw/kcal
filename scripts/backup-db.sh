#!/usr/bin/env sh
set -eu

backup_dir="${BACKUP_DIR:-backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
output="${1:-$backup_dir/kcal-$timestamp.sql.gz}"
tmp_output="$output.tmp.$$"

mkdir -p "$(dirname "$output")"
cleanup() {
  rm -f "$tmp_output"
}
trap cleanup EXIT INT TERM

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for database backups but was not found." >&2
  exit 1
fi

docker compose exec -T postgres pg_dump -U kcal -d kcal --clean --if-exists \
  | gzip -c > "$tmp_output"

gzip -t "$tmp_output"
chmod 600 "$tmp_output"
mv "$tmp_output" "$output"
trap - EXIT INT TERM

echo "Database backup written to $output"
