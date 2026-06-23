#!/usr/bin/env sh
set -eu

target="${1:-${DEPLOY_TARGET:-}}"
source_dir="${DEPLOY_SOURCE_DIR:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"
ssh_command="${DEPLOY_SSH_COMMAND:-}"
dry_run="${DEPLOY_UPLOAD_DRY_RUN:-false}"

if [ -z "$target" ]; then
  echo "Usage: $0 user@server:/opt/kcal-tracker/" >&2
  echo "Or set DEPLOY_TARGET." >&2
  echo "Set DEPLOY_SSH_COMMAND='ssh -i ~/.ssh/key' when a custom SSH command is needed." >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required for deploy upload." >&2
  exit 1
fi

case "$target" in
  "/"|"")
    echo "Refusing to sync to an empty target or filesystem root." >&2
    exit 1
    ;;
esac

set -- -az --delete \
  --exclude .git \
  --exclude .env \
  --exclude .venv \
  --exclude DEPLOY.local.md \
  --exclude backups/ \
  --exclude __pycache__ \
  --exclude .pytest_cache \
  --exclude .ruff_cache \
  --exclude '*.log' \
  --exclude build \
  --exclude dist

case "$dry_run" in
  1|true|yes)
    set -- --dry-run "$@"
    ;;
esac

if [ -n "$ssh_command" ]; then
  set -- "$@" -e "$ssh_command"
fi

set -- "$@" "$source_dir/" "$target"

echo "Uploading $source_dir/ to $target"
rsync "$@"
