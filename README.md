# Kcal Tracker

[![CI](https://github.com/c3RlcHVuaw/kcal/actions/workflows/ci.yml/badge.svg)](https://github.com/c3RlcHVuaw/kcal/actions/workflows/ci.yml)

Telegram-бот для дневника питания с AI-распознаванием еды, подсчетом калорий,
водой, весом, активностью, подписками и прогресс-карточками.

Language: [Русский](#русский) | [English](#english)

---

## Русский

### Что умеет

Kcal Tracker помогает вести дневник питания прямо в Telegram: пользователь
присылает фото еды, голос, текст или штрихкод, а бот предлагает оценку калорий и
БЖУ перед сохранением. AI-оценки никогда не сохраняются автоматически.

Основные возможности:

- Распознавание еды по фото через OpenAI vision.
- Разбор еды из текста и голосовых сообщений.
- Поиск продуктов по штрихкоду через Open Food Facts с локальным кешем.
- Подтверждение AI-оценки перед сохранением.
- Редактирование граммовки, удаление записей и AI-уточнение сохраненной еды.
- Дневник за сегодня и просмотр вчерашнего дня.
- Карточка итогов вчерашнего дня с калориями, БЖУ, водой и активностью.
- Вода, вес, активность и цели по макронутриентам.
- Избранные блюда и быстрые шаблоны без AI.
- Недельная и месячная аналитика.
- Недельные миссии, реферальные награды и share-карточки прогресса.
- Apple Health webhook для iOS Shortcuts.
- Подписки через Telegram Stars и YooKassa.
- Health/readiness endpoints, smoke checks, backup/restore scripts и GitHub CI.

### Стек

- Python 3.12
- FastAPI
- aiogram 3.x
- PostgreSQL
- SQLAlchemy async
- Redis
- Alembic
- OpenAI API
- Open Food Facts
- Docker Compose

### Локальный запуск

```bash
cp .env.example .env
# заполните TELEGRAM_BOT_TOKEN и OPENAI_API_KEY
docker compose up -d --build
curl http://127.0.0.1:3100/health
curl http://127.0.0.1:3100/health/ready
```

Ожидаемый `/health`:

```json
{"ok": true}
```

`/health/ready` дополнительно проверяет PostgreSQL и Redis.

### Миграции

В Docker миграции запускает API-контейнер при старте. Вручную:

```bash
alembic upgrade head
```

### Проверки

Полная локальная проверка:

```bash
./scripts/validate.sh
```

Если на хосте нет Python 3.12 и dev-инструментов, можно проверить внутри Docker:

```bash
./scripts/validate-docker.sh
```

После деплоя:

```bash
./scripts/smoke.sh https://your-api.example.com
```

На сервере helper пересобирает контейнеры, перезапускает стек, проверяет health
и показывает хвост логов:

```bash
./scripts/post-deploy.sh https://your-api.example.com
```

### Бэкап и восстановление

```bash
./scripts/backup-db.sh
```

Восстановление намеренно требует явного подтверждения:

```bash
RESTORE_CONFIRM=yes ./scripts/restore-db.sh backups/kcal-YYYYMMDDTHHMMSSZ.sql.gz
```

### Правила надежности AI

- AI-оценки приблизительные.
- Бот всегда просит подтверждение перед сохранением AI-результата.
- `confidence` не должен быть равен `1.0`.
- Плохие или неуверенные фото возвращают короткий retry-сценарий.

### Git и деплой

Репозиторий настроен на автоматический push после локального коммита.

```bash
./scripts/git-autopush.sh "Describe the change"
```

Секреты не хранятся в git. Используйте `.env`, `DEPLOY.local.md` или password
manager для production-данных.

---

## English

### Overview

Kcal Tracker is a Telegram calorie diary bot with AI food recognition, barcode
lookup, macro tracking, water, weight, activity, subscriptions, referrals, and
shareable progress cards.

Users can send a food photo, text, voice message, or barcode. The bot estimates
calories and macros, then asks for confirmation before saving anything.

### Features

- Food recognition from photos via OpenAI vision.
- Natural-language and voice meal parsing.
- Barcode lookup via Open Food Facts with a local database cache.
- Confirmation flow before saving AI estimates.
- Portion editing, entry deletion, and AI refinements for saved food entries.
- Today diary plus yesterday view.
- Generated daily summary card for yesterday.
- Water, weight, activity, and macro targets.
- Favorite foods and quick templates without AI.
- Weekly and monthly analytics.
- Weekly missions, referral rewards, and progress share cards.
- Apple Health webhook for iOS Shortcuts.
- Telegram Stars and YooKassa subscriptions.
- Health/readiness endpoints, smoke checks, backup/restore scripts, and GitHub CI.

### Tech Stack

- Python 3.12
- FastAPI
- aiogram 3.x
- PostgreSQL
- SQLAlchemy async
- Redis
- Alembic
- OpenAI API
- Open Food Facts
- Docker Compose

### Local Setup

```bash
cp .env.example .env
# fill TELEGRAM_BOT_TOKEN and OPENAI_API_KEY
docker compose up -d --build
curl http://127.0.0.1:3100/health
curl http://127.0.0.1:3100/health/ready
```

Expected `/health` response:

```json
{"ok": true}
```

`/health/ready` checks PostgreSQL and Redis.

### Migrations

The API container runs migrations on startup. To run them manually:

```bash
alembic upgrade head
```

### Validation

Run the full validation suite:

```bash
./scripts/validate.sh
```

If Python 3.12 and dev tools are not installed on the host, run validation in
Docker:

```bash
./scripts/validate-docker.sh
```

Post-deploy smoke check:

```bash
./scripts/smoke.sh https://your-api.example.com
```

Server deploy helper:

```bash
./scripts/post-deploy.sh https://your-api.example.com
```

### Backup and Restore

```bash
./scripts/backup-db.sh
```

Restore is destructive and requires an explicit confirmation:

```bash
RESTORE_CONFIRM=yes ./scripts/restore-db.sh backups/kcal-YYYYMMDDTHHMMSSZ.sql.gz
```

### AI Reliability Rules

- AI estimates are approximate.
- AI results are never saved automatically.
- `confidence` must stay below `1.0`.
- Low-confidence or unusable images return a short retry message.

### Git and Secrets

Commit and push current changes:

```bash
./scripts/git-autopush.sh "Describe the change"
```

Do not commit secrets. Keep `.env`, production notes, credentials, local caches,
logs, and backups out of git.
