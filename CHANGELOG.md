# Changelog

## 2026-05-20

- Added activity management in Today so users can delete incorrect activity
  entries, including Apple Health imports.
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
