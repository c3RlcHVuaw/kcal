# Kcal Tracker

[![CI](https://github.com/c3RlcHVuaw/kcal/actions/workflows/ci.yml/badge.svg)](https://github.com/c3RlcHVuaw/kcal/actions/workflows/ci.yml)

Telegram calorie diary with AI food recognition, Telegram Mini App, barcode and
food search, water, weight, activity, subscriptions, referrals, reminders,
exports, admin tooling, and production health checks.

Language: [Русский](#русский) | [English](#english)

---

## Русский

### О проекте

Kcal Tracker помогает вести дневник питания в Telegram и Mini App. Пользователь
может добавить еду по фото, голосу, тексту, штрихкоду, поиску продуктов,
шаблону или точным КБЖУ. AI-оценки показываются на проверку и никогда не
сохраняются автоматически.

### Что умеет

- Распознает еду по фото через OpenAI vision, включая подсказки про вес, соусы,
  напитки, скрытые ингредиенты и неполную порцию.
- Разбирает еду из текста и голосовых сообщений, поддерживает несколько блюд в
  одном вводе и уточнение AI-результата перед сохранением.
- Ищет продукты по названию, бренду или штрихкоду, использует Open Food Facts и
  локальный кеш продуктов.
- Сканирует штрихкоды из фото, видео и video notes; в Mini App можно загрузить
  фото штрихкода или ввести код вручную.
- Позволяет редактировать граммовку, КБЖУ, прием пищи, удалять записи,
  повторять отдельные записи и повторять весь вчерашний дневник.
- Ведет дневник по приемам пищи: завтрак, обед, ужин и перекусы, с целями по
  калориям, белкам, жирам и углеводам.
- Показывает сегодня, вчера, недельную и месячную аналитику, прогноз до конца
  дня, привычки, streaks и 30-дневное покрытие трекинга.
- Считает воду, вес и активность; дневная цель калорий расширяется на расход
  активности.
- Поддерживает цели веса: снижение, поддержание или набор, желаемый вес,
  недельный темп и пересчет дневной калорийности.
- Импортирует вес, активные калории и шаги из Apple Health через iOS Shortcuts
  webhook с защитой от повторного учета дневных totals.
- Делает избранные блюда и быстрые шаблоны без AI, показывает частые продукты и
  недавние записи.
- Дает ежедневные и недельные coaching notes, подсказку "что съесть дальше",
  предупреждения о высококалорийных добавлениях и мягкие inactivity reminders.
- Генерирует share-карточки прогресса за день и неделю.
- Поддерживает реферальные ссылки, активные реферальные награды, недельные
  миссии и бонусные AI-дни.
- Ограничивает AI дневным лимитом, дает trial, win-back AI day и подписки.
- Принимает оплату через Telegram Stars и YooKassa, поддерживает промокоды со
  скидками.
- Имеет админ-бота для funnel-метрик, quality events, алертов, поддержки,
  платежей и промокодов.
- Отдает внешние API endpoints для профиля, дневника, недельной аналитики,
  целей веса, AI usage и CSV export.
- Содержит health/readiness endpoints, smoke checks, backup/restore scripts,
  Docker validation и GitHub CI.

### Telegram Mini App

Mini App доступен по `/app` и проверяет подпись Telegram WebApp init data.

Разделы Mini App:

- **Сегодня**: калории, активность, остаток до цели, БЖУ, оценка питания и
  дневник по приемам пищи.
- **Еда**: поиск продуктов, AI-разбор текста, фото еды, ручной ввод КБЖУ,
  штрихкод, недавние продукты, шаблоны и повтор вчерашнего дня.
- **Прогресс**: недельная динамика, дни в цели, покрытие трекинга и форма цели
  веса.
- **Тело**: быстрый ввод воды, веса и активности, тренд веса и привычки.
- **Ещё**: AI usage, подписка, промокоды, экспорт CSV, поддержка и переход в
  основное меню Telegram-бота.

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

Если Docker не установлен, скрипт выполнит Python-проверки и пропустит
`docker compose config`; в CI эта проверка выполняется с доступным Docker.

Если на хосте нет Python 3.12 и dev-инструментов, можно проверить внутри Docker:

```bash
./scripts/validate-docker.sh
```

После деплоя:

```bash
./scripts/smoke.sh https://your-api.example.com
```

Лёгкий нагрузочный smoke-тест перед запуском трафика:

```bash
LOAD_SMOKE_REQUESTS=200 LOAD_SMOKE_CONCURRENCY=12 ./scripts/load-smoke.sh https://your-api.example.com
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
- Бот и Mini App всегда просят подтверждение перед сохранением AI-результата.
- `confidence` не должен быть равен `1.0`.
- Плохие или неуверенные фото возвращают короткий retry-сценарий.
- AI usage считается по пользователю и источнику запроса.

### Git и деплой

Репозиторий настроен на автоматический push после локального коммита:

```bash
./scripts/git-autopush.sh "Describe the change"
```

Секреты не хранятся в git. Используйте `.env`, `DEPLOY.local.md` или password
manager для production-данных.

---

## English

### Overview

Kcal Tracker is a Telegram calorie diary bot and Telegram Mini App. Users can
log food from photos, voice messages, text, barcode scans, food search,
templates, or exact calories and macros. AI estimates are shown for review and
are never saved automatically.

### Features

- Recognizes food photos through OpenAI vision, including user hints about
  weight, sauces, drinks, hidden ingredients, or partial portions.
- Parses natural-language and voice meal descriptions, supports multi-item
  meals, and can refine AI results before saving.
- Searches foods by product, brand, or barcode using Open Food Facts plus a
  local product cache.
- Scans barcodes from photos, videos, and video notes; the Mini App also
  supports barcode photo upload and manual code entry.
- Lets users edit portion size, calories, macros, meal type, delete entries,
  repeat individual entries, and repeat the full yesterday diary.
- Groups the diary by breakfast, lunch, dinner, and snacks with calorie and
  macro targets.
- Shows today, yesterday, weekly and monthly analytics, end-of-day forecasts,
  habits, streaks, and 30-day tracking coverage.
- Tracks water, weight, and activity; daily calorie targets include today's
  burned activity calories.
- Supports weight goals for loss, maintenance, or gain with target weight,
  weekly pace, forecast text, and recalculated calorie targets.
- Imports weight, active calories, and steps from Apple Health via iOS Shortcuts
  webhook while preventing duplicate same-day totals.
- Provides favorite foods, quick templates without AI, frequent foods, and
  recent entries.
- Generates daily and weekly coaching notes, "what should I eat?" suggestions,
  high-calorie warnings, and soft inactivity reminders.
- Generates daily and weekly progress share cards.
- Supports referral links, active referral rewards, weekly missions, and bonus
  AI days.
- Enforces per-user AI limits with trial usage, win-back AI day offers, and
  subscriptions.
- Accepts Telegram Stars and YooKassa payments with promo-code discounts.
- Includes an admin bot for funnel metrics, quality events, alerts, support,
  payments, and promo-code management.
- Exposes external API endpoints for profile, diary, weekly analytics, weight
  goals, AI usage, and CSV exports.
- Ships health/readiness endpoints, smoke checks, backup/restore scripts, Docker
  validation, and GitHub CI.

### Telegram Mini App

The Mini App is served at `/app` and validates signed Telegram WebApp init data.

Mini App sections:

- **Today**: calories, activity, remaining target, macros, nutrition score, and
  meal-grouped diary.
- **Food**: product search, AI text parsing, food photo parsing, manual macro
  entry, barcode lookup, recent foods, templates, and repeat yesterday.
- **Progress**: weekly trend, days near target, tracking coverage, and weight
  goal editing.
- **Body**: quick water, weight, and activity logging, weight trend, and habits.
- **More**: AI usage, subscription, promo codes, CSV export, support, and a link
  back to the Telegram bot.

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

Lightweight load smoke check before sending traffic:

```bash
LOAD_SMOKE_REQUESTS=200 LOAD_SMOKE_CONCURRENCY=12 ./scripts/load-smoke.sh https://your-api.example.com
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
- AI usage is tracked by user and request source.

### Git and Secrets

Commit and push current changes:

```bash
./scripts/git-autopush.sh "Describe the change"
```

Do not commit secrets. Keep `.env`, production notes, credentials, local caches,
logs, backups, and generated build artifacts out of git.
