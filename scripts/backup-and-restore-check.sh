#!/usr/bin/env sh
set -eu

backup_dir="${BACKUP_DIR:-backups}"

./scripts/backup-db.sh

latest="$(
  find "$backup_dir" -maxdepth 1 -type f -name "*.sql.gz" -printf "%T@ %p\n" \
    | sort -nr \
    | head -1 \
    | cut -d" " -f2-
)"

if [ -z "$latest" ]; then
  echo "No backup file found in $backup_dir" >&2
  exit 1
fi

./scripts/restore-check-db.sh "$latest"
