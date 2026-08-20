# Changelog

## 2026-08-19

- Reworked the Mini App interface into an iOS 26 look: system color tokens,
  the native type ramp, opaque grouped content cards, inset row separators and
  Liquid Glass reserved for floating chrome.
- Replaced the bottom navigation with an iOS 26 dock — a glass tab capsule plus
  a separate accessory button — that minimizes while scrolling down.
- Added scroll-aware navigation bars that gain their material and collapse the
  large title into a centered compact one, with a selection haptic on tab taps.
- Removed the older competing style passes that redefined the palette, page
  background and card skins so the theme tokens are authoritative again.
- Gave every raised surface the Liquid Glass build-up — translucent fill, rim
  hairline and top sheen over a softly washed canvas — instead of flat cards.
- Normalized the ad-hoc font weights onto the four SF weights and pulled colour
  out of labels so hue only marks rings, bars and states.
- Fixed the gap left in the tab capsule after the add button moved out of the
  navigation, by laying the tabs out with flex instead of fixed grid columns.
- Redrew the navigation icons in SF Symbols geometry and gave each tab a solid
  variant that replaces the outline once the tab is selected.
- Rebuilt the Today hero around a single calorie ring with the day's secondary
  numbers underneath, replacing the linear progress bar.
- Made sheets draggable: a tall sheet now has a medium detent, resists past its
  top stop, and a flick down dismisses it through the existing close path.
- Asked for continuous (squircle) corners where the engine supports
  `corner-shape`, falling back to the plain radius everywhere else.
- Turned the Today calorie summary into a plain list row that drills into
  Progress, and dropped the stale backdrop filters that were painting a lighter
  band behind rows flattened to a transparent fill.
- Raised form field contrast so inputs read against the glass cards they sit in,
  and matched the id-specificity rules that were overriding the new layer.
- Made tab switches instant, neutralized leftover hover skins, and let the
  compact toolbar appear on Today once its large title scrolls away.
- Replaced the two decorative bar charts on Today with meters over real values:
  the nutrition score out of 100, and the day's actual protein/fat/carb split.
- Parked the premium themes: the picker is hidden and any stored skin resolves
  back to the system theme, because those skins repaint surfaces the iOS 26
  layer owns.
- Reworked the add-food mode screens: the sticky header is a real navigation bar
  with a chevron back button, example chips are neutral capsules, and the mode
  tiles lost their coloured halos and coloured label text.
- Made the search field a single surface again and toned down cards nested
  inside the sheet, which were reading as bright slabs of glass over glass.
- Redrew the selected home glyph with roof eaves so it reads as a house at tab
  bar size, and calmed the bottom background wash the dock floats over.
- Made content surfaces opaque again — cards are a solid systemBackground fill
  on the grouped background, and the colour washes behind them are gone.
  Translucent cards blended into the canvas, which is the opposite of how iOS
  separates content from chrome; blur now applies only to the tab dock,
  navigation bars and sheet headers.
- Rebuilt the navigation bar the way iOS 26 draws one: no slab and no hairline,
  just the title and floating glass action buttons over a blur that fades out
  down the bar.
- Centred the tab glyphs while the bar is minimized. Hiding the label with
  max-height left it holding an implicit grid row plus the row gap, so the icons
  sat high in the capsule.
- Turned the More quick actions from a two-column grid of tinted cards into one
  inset group of rows — coloured glyph, title, chevron — and dropped the static
  descriptions under each title.
- Gave the AI flow three designed states: an idle hero that says what to type,
  a thinking state with a breathing orb, shimmering result lines and a status
  line that narrates each stage, and a result that springs in card by card.
  app.js already toggled a `[data-ai-processing]` element that the markup never
  had, so the state now has something to show.
- Turned row actions into text buttons: "Добавить" in a section header and
  "Изменить / В шаблон / Удалить" on a food card were filled pills, which is
  heavier than any native list row. Delete now carries the system red, and the
  three actions sit on one line instead of being clipped by equal grid columns.
- Painted the calorie figure on food cards in the label colour instead of the
  old palette's blue, which clashed with the green accent.
- Gave the review screen the same navigation bar as the rest of the app: a
  chevron back button in the accent colour instead of a filled pill, a centred
  compact title, and the chrome material with a hairline.
- Centred only the waiting state, not the whole panel. The mode screen is a
  flex column whose first child is its sticky header, so centring the panel
  pushed that header into the middle of the sheet and left a void above it.
- Cleared the form away while the model works: the composer, its example chips
  and the submit button are hidden, so the waiting state has the screen to
  itself and centres in it.
- Rebuilt the add-food tiles: each is tinted by its own mode with a gradient
  glyph tile, replacing three identical grey cards with typographic stand-ins.
- Gave sheet headers an opaque fill. A transparent blurred header leaves a seam
  where its backdrop root ends, which showed as a vertical edge by the back
  button.
- Stripped presentation out of styles.css: every background, box-shadow,
  backdrop-filter and border it declared is gone, except where the paint is the
  data itself (rings, chart bars, thumbnails). The old sheet now carries layout
  only, and the iOS layer owns every surface, so the two can no longer fight
  over specificity. Those surfaces are restated once, on tokens, grouped by the
  role each element plays.
- Stopped the add-food mode screens rendering as a panel inside the panel: the
  rule that flattens cards nested in a sheet was also painting the full-height
  mode screens, so it now skips them.
- Cleaned those screens up — no title repeated under the navigation bar, a
  filled photo drop target instead of a dashed outline, shooting tips as plain
  footnotes, and the paragraph that restated them removed.
- Kept the navigation bar's own height once the refresh button was removed:
  with the compact title positioned absolutely, the bar had no in-flow content
  left and collapsed to its padding, so the blur stopped covering the title.
- Replaced the toolbar refresh buttons with pull to refresh. Telegram's own
  vertical swipe is released so the gesture can work; its header close button
  still dismisses the app.
- Dropped the third line from the add-food mode tiles, the decorative caption
  above the Today title, and the duplicate "Еда" row on More — the dock button
  and the diary's own add action already cover it.
- Unified the More row icons: white glyphs of one geometry on solid system
  colour tiles, replacing a mix of typographic stand-ins ("ml", "kg", "⌗") and
  gradient chips. Adds star, repeat, drop, flame and scale symbols.
- Merged the two Premium blocks into a single card: the AI status line and one
  button, instead of a status card followed by a promo card pointing at the same
  screen.
- Cut interface noise: removed nine section subtitles that only restated their
  heading, the marketing hero on More (its status numbers stay), and the Premium
  badges repeated on every AI entry point.
- Fixed the add-food sheet turning see-through: its panel also carries
  `.component-card`, so the rule that flattens cards nested in a sheet was
  repainting the panel itself. The rule is now scoped to the scroll container.
- Presented sheets as a centred card on wide viewports instead of stretching
  the phone layout across a desktop window, matching how iOS switches
  presentation by width class.
- Sent `Cache-Control: no-cache` with the HTML documents. Static assets were
  already versioned and cached hard, but the document that references them had
  no directive at all, so webviews cached it heuristically and never picked up
  new asset versions.

## 2026-06-23

- Split admin launch readiness checks into a dedicated module with focused
  formatting coverage.
- Switched the production Docker image to a multi-stage wheel build so runtime
  containers no longer install development tools, and made admin launch checks
  read packaged landing assets.
- Made CI install Node explicitly and require Mini App JavaScript syntax plus
  Docker Compose validation in CI runs.

## 2026-06-15

- Added Mini App first-day guidance for empty and nearly empty diaries so new
  users have a clear next food-logging action.
- Added Mini App AI review feedback buttons and a webapp quality-events endpoint
  to capture AI accept/adjust/reject signals, search failures, barcode failures,
  first-food saves, and paywall opens.
- Expanded admin quality, funnel, and alert views to include the new Mini App
  feedback, first-food, paywall, search, barcode, and AI failure signals.
- Turned the Mini App first-day prompt into a smart daily nudge that points to
  food, water, progress, or Premium based on the current day state.
- Made the Mini App AI limit paywall contextual for text parsing, photo
  recognition, AI food search, and food refinement, with a manual-entry fallback.
- Added weekly mission progress to the Mini App Today view so users can see
  retention goals and the +1 day AI bonus without leaving the app.
- Added Mini App claiming for the weekly +1 day AI bonus once enough missions
  are completed.

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
