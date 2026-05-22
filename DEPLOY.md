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
OPENAI_API_KEY=
DATABASE_URL=
REDIS_URL=
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
