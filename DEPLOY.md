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
2. Run validation in the target Python/Docker environment:

```bash
python -m compileall src tests migrations
ruff check src migrations tests
pytest -q
docker compose config
```

3. Upload the repository to the server while excluding local secrets and caches.
4. Rebuild and restart the server compose stack.
5. Verify the health endpoint and container status.

Expected health response:

```json
{"ok": true}
```
