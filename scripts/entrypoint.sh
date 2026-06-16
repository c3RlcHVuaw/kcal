#!/usr/bin/env sh
set -eu

case "${1:-api}" in
  api)
    alembic upgrade head
    exec uvicorn kcal_tracker.main:app --host "${API_HOST:-0.0.0.0}" --port 3100 --workers "${API_WORKERS:-2}"
    ;;
  bot)
    exec python -m kcal_tracker.bot.main
    ;;
  admin-bot)
    exec python -m kcal_tracker.admin_bot.main
    ;;
  *)
    exec "$@"
    ;;
esac
