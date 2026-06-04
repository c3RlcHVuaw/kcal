# Changelog

## 2026-06-04

- Added iOS-style swipe actions to Mini App diary food cards: swipe right to
  repeat an entry, swipe left to edit or delete it, with a first-run gesture
  guide.

## 2026-05-25

- Simplified the Mini App UX after design review: removed the Lifesum-like
  calorie ring, reduced tab bar weight, flattened nested section cards, and
  separated read-only diary data from editable actions.
- Updated the Mini App glass visual system with a cooler cyan/blue palette,
  SF Pro typography stack, stronger Liquid Glass surfaces, a readable calorie
  ring, and removed the Today undo button.
- Reworked the Mini App visual system away from a literal reference copy:
  shared wellness cards, soft surfaces, consistent forms/lists across tabs, and
  a floating glass-style tab bar.
- Reworked the Telegram Mini App toward an iOS-style tab interface and added
  webapp endpoints for week progress, body summary, frequent foods, templates,
  repeat-yesterday, entry deletion, activity, weight goals, and food export.
- Refined the Mini App UI into a more native diary layout with compact calorie
  progress, macro tiles, quick actions, and a bottom sheet for manual food entry.
- Added the first Telegram Mini App MVP at `/app` with signed Telegram WebApp
  authentication, today's dashboard, manual food entry, water, and weight.
- Added promo codes for subscription payments with admin creation/listing/
  disabling and user entry before choosing a payment method.
- Removed raw Apple Health payload logging and replaced it with a privacy-safe
  field summary.
- Added weight goals with target weight, weekly pace, and forecast text in
  profile settings and API responses.
- Added external-client API routes for profile, weekly analytics, weight goals,
  and CSV exports.
- Expanded the admin funnel to show today, 7-day, and 30-day cohorts through
  onboarding, first food, 3 active days, AI use, and payment.
- Added regression coverage for Apple Health log summaries, weight goal
  forecasts, admin funnel conversion text, and OpenAPI route exposure.

## 2026-05-22

- Added a tracked `.env.example` with local defaults and placeholders for
  required bot, AI, FatSecret, and YooKassa credentials.
- Added a single validation script for compile, lint, test, and compose config
  checks, and updated docs to use it before deploy.
- Added Docker-based validation for machines without local Python 3.12 tooling
  and expanded Docker build ignores for local-only files and caches.
- Added startup validation for required production settings and smoke tests for
  configuration checks and the health endpoint.
- Added a production guard that rejects missing, relative, or local
  `PUBLIC_API_URL` values before startup.
- Added a readiness endpoint for PostgreSQL and Redis checks plus a post-deploy
  smoke script for health checks.
- Simplified readiness checks so the database probe uses a direct engine
  connection instead of a request-scoped API session.
- Added GitHub Actions CI, structured logging, graceful bot shutdown, payment
  charge idempotency indexes, database backup/restore helpers, and a post-deploy
  smoke helper.
- Added yesterday diary navigation from Today plus a generated daily summary
  card for yesterday's food, macros, water, and activity.
- Changed compose startup so only the API runs migrations and the bot waits for
  the API healthcheck, avoiding Alembic races during deploy.
- Changed yesterday view to send the daily card immediately, removed emoji from
  card food names, wrapped long food lists, and added `@trackerkcal_bot`.
- Moved the daily card bot tag into a top-right badge and made the Telegram
  caption more share-friendly.
- Added a Telegram button under daily cards, branded weekly cards, skipped empty
  yesterday cards, and covered card text wrapping with a test.

## 2026-05-21

- Added a referral dashboard with invited friend counts, active-day progress,
  reward status, and the user's invite link.
- Added weekly missions for food, water, weight, and activity with a one-day AI
  bonus after completing two missions in the week.
- Added a generated weekly progress share-card image alongside the existing
  Telegram progress sharing link.

## 2026-05-20

- Changed referrals so the first active friend gives 7 AI days after 5 active
  days out of 7, while later referral bonuses require the friend to pay.
- Added referral links, weekly progress sharing, one-day premium trials, and
  one-time win-back AI day offers for expired subscribers.
- Fixed barcode scans failing completely when the native decoder rejects one
  image candidate, so the bot now keeps trying other frames and variants.
- Added activity management in Today so users can delete incorrect activity
  entries, including Apple Health imports.
- Moved activity management into the existing More -> Activity section so add
  and delete actions live in one place.
- Allowed newline-separated Apple Health sample dumps again, with same-day delta
  sync preventing repeated webhook runs from double-counting the same total.
- Fixed Apple Health activity parsing when Shortcuts sends a list of HealthKit
  samples by summing active calories and steps instead of taking the first sample.
- Changed Apple Health activity imports to use same-day cumulative deltas, so
  hourly Shortcut runs only add newly gained active calories or steps.
- Made the Apple Health Shortcuts webhook tolerant of HealthKit-style payloads
  with numeric strings, nested value objects, and unknown fields.
- Added an Apple Health Shortcuts webhook with per-user tokens for importing
  weight, active calories, and steps from iOS Shortcuts.
- Added soft inactivity reminders that nudge users back after 3+ silent diary days,
  capped to at most once per week.
- Added AI correction for saved AI food entries from the Today entry actions.
- Added photo follow-up prompts for sauces/oil and drinks before saving AI food estimates.
- Added a 30-day monthly report with tracking coverage, calorie patterns,
  protein average, weight trend, and next-month focus.
- Reworked favorites into quick food templates for one-tap repeat meals without AI.
- Added a weight dashboard with recent sparkline, 7-day average, and trend label.
- Added habit streaks and 30-day tracking coverage for food, water, and weight
  to the weekly report.
- Expanded the weekly report with clearer highlights: best target day, average
  protein, and the main calorie trend.
- Made meal reminders behavior-aware so already logged breakfast, lunch, or
  dinner does not trigger a redundant reminder.
- Added quick photo portion controls for AI estimates: quarter, half, normal,
  one-and-a-half, and double portion.
- Added CSV export for food, water, weight, and activity from settings.

## 2026-05-19

- Changed the "Today" view to show all entries immediately under meal sections
  with each meal's calories, and removed the separate signals block.
- Added a meal-grouped "Today" view with entries organized by breakfast, lunch,
  dinner, and snacks.
- Turned weekly analytics into a cleaner report with a weekly score and
  highlighted coaching notes.
- Simplified today's food list into one-line entries and moved per-product
  advice out of the dense entry list.
- Made today's entry action keyboard compact by default, with entry edit,
  delete, and favorite controls hidden behind a "Редактировать" action.
- Improved daily AI advice formatting with clearer spacing and emoji markers
  so Telegram summaries are easier to scan.
- Kept simple end-of-day forecasts free while limiting advanced historical
  nutrition patterns to active AI subscribers.
- Added end-of-day calorie forecasting and automatic nutrition pattern notes
  for skipped breakfasts, sweet drinks, and calorie-heavy evenings.
- Added richer AI-style daily coaching, weekly nutrition analysis, and a
  "what should I eat?" suggestion action based on remaining calories, macros,
  and water.
- Combined the main food/photo actions into one food entry button and made
  today's view include the same remaining-target guidance as the old remainder view.
- Improved video-note barcode scanning by sampling more frames and trying more
  crop/contrast variants.
- Fixed video-note barcode scans appearing unresponsive by replying immediately
  and moving barcode decoding off the bot polling loop with a timeout.
- Fixed diary entry times in Telegram summaries to display in the user's timezone
  instead of raw UTC timestamps.
- Added an AI clarification action before saving AI food estimates so users can
  account for sauces, jam, hidden ingredients, or partial portions.
- Fixed photo meal recognition silently doing nothing on slow AI responses by
  extending OpenAI timeouts and replying with progress or a retry message.

## 2026-05-18

- Added AI food emoji and per-product advice in confirmations, diary entries,
  favorites, frequent foods, and repeated meals.
- Added fallback food insights for barcode and manual favorite entries.
- Expanded reminders with separate food/weight toggles plus smart morning,
  lunch, and evening meal nudges.
- Added an extra confirmation warning before saving another high-calorie item
  when today's diary is already calorie-dense or near the daily target.
- Fixed AI photo recognition with text captions so user hints about grams,
  hidden ingredients, sauces, or partial portions are included in the vision prompt.
- Improved barcode recognition from Telegram video notes by sampling more frames
  and decoding enhanced, cropped, upscaled, thresholded, and rotated image variants.
- Simplified the Telegram reply keyboard to the primary food, diary, water,
  and more actions, moving secondary tools into an inline "More" menu.
- Raised the Telegram Stars AI subscription price from 150 to 199 Stars.
- Improved Telegram bot usability with `/help`, richer food confirmations,
  quick post-save actions, and a smoother multi-item food flow.
- Fixed lint failures found during server-side validation after deploy.
- Tightened Russian food names in AI parsing and Open Food Facts barcode lookup.
- Polished bot calorie labels from `kcal` to `ккал` in user-facing messages.
- Added saved-entry editing/deletion, manual favorites, water and weight tracking.
- Added macro targets with remaining/over target feedback in the daily summary.
- Added configurable dinner and weight reminders, disabled by default.
- Added multi-item AI food confirmation with add-one or add-all actions.
- Granted Telegram user `904738198` a permanent AI subscription on the server.
- Made successful local validation an explicit mandatory trigger for immediate server deploy.
- Added gram editing before saving AI, barcode, and manual food estimates.
- Added frequent foods, quick repeat for yesterday, and weekly nutrition analytics in the bot.
- Added a configurable 3-request AI trial before subscription.
- Improved barcode video scanning by checking several frames per video.
- Fixed the water flow so adding water offers more water instead of switching to food,
  and accepts water amounts with units in text.
- Fixed barcode scanning from Telegram videos and video messages by sampling frames
  across the full clip instead of only the beginning.
- Added activity tracking with manual calorie burn input, AI activity estimates,
  and daily calorie targets extended by today's activity.

## 2026-05-18

- Added onboarding for language, gender, age, height, weight, activity, goal, and daily calories.
- Added profile settings from the main menu with calorie target recalculation.
- Added Telegram Stars AI subscription at 150 Stars for 30 days.
- Added subscription-gated AI photo/manual parsing and voice food input.
- Added barcode scanning from photos, videos, and video notes.

## 2026-05-18

- Added per-user daily AI request tracking and a default 100-request daily limit.
- Added `AI_DAILY_REQUEST_LIMIT`, `ai_usage` migration, and `/users/{telegram_id}/ai-usage/today`.
- Bot now blocks AI photo/manual parsing after the daily limit while keeping barcode scans available.

## 2026-05-17

- Created initial Telegram AI Calorie Tracker backend structure.
- Added FastAPI routes, aiogram bot handlers, async SQLAlchemy models, Alembic migration, Redis FSM, OpenAI service, Open Food Facts service, barcode decoding, Docker Compose, deployment instructions, and environment example.
