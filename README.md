# Telegram AI Calorie Tracker Bot

MVP backend for a Telegram calorie diary with AI photo recognition, natural language meal parsing, barcode lookup via Open Food Facts, PostgreSQL storage, and Redis FSM.

## Stack

- Python 3.12
- FastAPI
- aiogram 3.x
- PostgreSQL
- SQLAlchemy async
- Redis
- OpenAI Chat Completions with vision input
- Open Food Facts API

## Local start

```bash
cp .env.example .env
# fill TELEGRAM_BOT_TOKEN and OPENAI_API_KEY
docker compose up -d --build
curl http://127.0.0.1:3100/health
```

API health should return:

```json
{"ok": true}
```

## MVP flow

- `/start` creates a user by Telegram ID.
- Main menu exposes scan, manual add, day summary, calories, weekly analytics,
  frequent foods, yesterday repeat, and settings.
- Food photo is sent to OpenAI and shown for confirmation before saving.
- Barcode photo is decoded locally and resolved through Open Food Facts with DB cache.
- Manual meal text is parsed by OpenAI and shown for confirmation before saving.
- Diary shows calories, macros, and today's entries.
- Users can edit grams before saving an AI/barcode/manual estimate.
- Users can edit/delete saved entries from the day summary.
- Users can track water, weight, favorite foods, and macro targets.
- Optional reminders can nudge dinner logging and morning weigh-ins.
- Multi-product AI results can be saved one by one or all at once.
- Users without a subscription get 3 free AI requests before the paywall.
- Barcode videos are scanned across several frames, not just one still frame.

## AI reliability rules

- AI results are always approximate.
- The bot never saves AI results automatically.
- `confidence` is capped below `1.0`.
- Low confidence or unusable images return a short retry message.

## Migrations

```bash
alembic upgrade head
```

## Validation before deploy

Before every deploy:

```bash
python -m compileall src tests migrations
ruff check src migrations tests
docker compose config
```

Mandatory rule: if local validation passes, upload the full project to the server
immediately and restart the compose stack. Keep `CHANGELOG.md` updated before upload.

## Git auto-push

This repository is configured to push commits automatically after every local commit.

First connect the GitHub repository once:

```bash
git remote add origin git@github.com:OWNER/kcal-tracker.git
git config core.hooksPath .githooks
```

Then commit and push every current change with one command:

```bash
./scripts/git-autopush.sh "Describe the change"
```

The tracked `post-commit` hook also pushes automatically after normal `git commit`.
