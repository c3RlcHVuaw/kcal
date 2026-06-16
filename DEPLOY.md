# Deployment

This repository intentionally does not store production hostnames, IP addresses,
SSH key names, server paths, or secret values.

Keep real deployment details in a local, untracked file such as
`DEPLOY.local.md` or in your password manager.

## Required Environment

Set these values on the server, not in git:

```env
APP_ENV=production
TELEGRAM_BOT_TOKEN=
ADMIN_BOT_TOKEN=
ADMIN_TELEGRAM_IDS=
OPENAI_ADMIN_API_KEY=
OPENAI_MONTHLY_BUDGET_USD=
OPENAI_REMAINING_ALERT_USD=2
OPENAI_API_KEY=
DATABASE_URL=
REDIS_URL=
```

`ADMIN_TELEGRAM_IDS` is a comma-separated allowlist of Telegram numeric user IDs.
Without allowed IDs, the admin bot starts in locked mode and only reports the
requester's Telegram ID.
`OPENAI_ADMIN_API_KEY` is optional; when present, the admin bot uses it for the
OpenAI organization Costs endpoint. Otherwise it falls back to `OPENAI_API_KEY`.
Set `OPENAI_MONTHLY_BUDGET_USD` to enable "remaining budget" alerts. For example,
with `OPENAI_REMAINING_ALERT_USD=2`, admins get a Telegram alert when the current
month's OpenAI spend leaves about $2 or less from that budget.

Optional admin alert tuning:

```env
ADMIN_ALERT_INTERVAL_SECONDS=300
ADMIN_ALERT_COOLDOWN_SECONDS=3600
ADMIN_SERVER_LOAD_PER_CPU_THRESHOLD=2.0
ADMIN_SERVER_MEMORY_PERCENT_THRESHOLD=90
ADMIN_SERVER_DISK_PERCENT_THRESHOLD=85
ADMIN_PENDING_PAYMENTS_ALERT_THRESHOLD=3
ADMIN_FAILED_PAYMENTS_HOUR_THRESHOLD=2
ADMIN_NO_ONBOARDING_ALERT_THRESHOLD=5
ADMIN_BROADCAST_ALL_ENABLED=false
```

Keep `ADMIN_BROADCAST_ALL_ENABLED=false` before launch unless you explicitly
want the admin bot to allow broadcasts to every user in the database.

Optional food-search stability tuning:

```env
FOOD_SEARCH_OPENFOODFACTS_TIMEOUT_SECONDS=3
FOOD_SEARCH_FATSECRET_TIMEOUT_SECONDS=3
```

## Update Checklist

1. Write a short note in `CHANGELOG.md`.
2. Create a database backup on the server:

```bash
./scripts/backup-db.sh
```

3. Run validation in the target Python/Docker environment:

```bash
./scripts/validate.sh
# or, when Python 3.12 is only available through Docker:
./scripts/validate-docker.sh
```

4. Upload the repository to the server while excluding local secrets and caches.
5. Rebuild and restart the server compose stack.
6. Verify health, readiness, and container status.

Run:

```bash
./scripts/post-deploy.sh https://your-api.example.com
```

Before sending real traffic, run a short load smoke check:

```bash
LOAD_SMOKE_REQUESTS=200 LOAD_SMOKE_CONCURRENCY=12 ./scripts/load-smoke.sh https://your-api.example.com
```

Expected health response:

```json
{"ok": true}
```

Readiness should return `ok: true` with `database` and `redis` checks.

## Restore

Restores are destructive. Run only with an explicit confirmation:

```bash
RESTORE_CONFIRM=yes ./scripts/restore-db.sh backups/kcal-YYYYMMDDTHHMMSSZ.sql.gz
```
