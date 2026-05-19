from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from kcal_tracker.bot.keyboards import (
    after_activity_save_keyboard,
    after_save_keyboard,
    after_water_save_keyboard,
    favorites_keyboard,
    food_entries_keyboard,
    reminders_keyboard,
    water_keyboard,
)
from kcal_tracker.bot.text_parsing import (
    looks_like_activity,
    parse_activity_kcal,
    parse_int_from_text,
)
from kcal_tracker.config import settings
from kcal_tracker.database import SessionLocal
from kcal_tracker.schemas import ActivityEstimate, FoodEntryCreate
from kcal_tracker.services.ai_activity import AIActivityService
from kcal_tracker.services.ai_usage import AILimitReachedError, AIUsageService
from kcal_tracker.services.diary import DiaryService
from kcal_tracker.services.food_insights import food_label
from kcal_tracker.services.nutrition import (
    automatic_pattern_notes,
    daily_focus,
    diet_quality_note,
    end_of_day_forecast,
    meal_suggestion_text,
    remaining_advice,
    smart_day_coach,
    smart_evening_hint,
    weekly_coach_note,
)
from kcal_tracker.services.subscriptions import has_active_subscription
from kcal_tracker.services.users import UserService
from kcal_tracker.services.wellness import WellnessService

router = Router()

ADVANCED_PATTERNS_UPSELL = (
    "Продвинутые паттерны по завтракам, напиткам и вечерам доступны в подписке."
)


class DiaryFlow(StatesGroup):
    editing_saved_weight = State()
    water_custom = State()
    activity_custom = State()
    weight = State()
    favorite_manual = State()
    reminder_time = State()


@router.message(
    lambda message: message.text in {"📊 Сегодня", "📊 Мой день", "🔥 Остаток", "🔥 Калории"}
)
async def show_today(message: Message) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        diary = DiaryService(session)
        summary = await diary.today_summary(user)
        has_subscription = has_active_subscription(user)
        patterns = await diary.nutrition_patterns(user) if has_subscription else None
        water_ml = await WellnessService(session).today_water_ml(user)

    text, reply_markup = _today_view(
        summary,
        water_ml,
        patterns=patterns,
        show_advanced_patterns=has_subscription,
        timezone_name=user.timezone,
        include_advice=True,
    )
    await message.answer(
        text,
        reply_markup=reply_markup,
    )


@router.callback_query(F.data == "nav:today")
async def show_today_inline(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        diary = DiaryService(session)
        summary = await diary.today_summary(user)
        has_subscription = has_active_subscription(user)
        patterns = await diary.nutrition_patterns(user) if has_subscription else None
        water_ml = await WellnessService(session).today_water_ml(user)

    text, reply_markup = _today_view(
        summary,
        water_ml,
        patterns=patterns,
        show_advanced_patterns=has_subscription,
        timezone_name=user.timezone,
        include_advice=True,
    )
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data == "entry:manage")
async def show_entry_management(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        summary = await DiaryService(session).today_summary(user)

    entry_ids = [entry.id for entry in summary.entries]
    if not entry_ids:
        await callback.answer("Сегодня пока нет записей.", show_alert=True)
        return
    await callback.message.edit_reply_markup(
        reply_markup=food_entries_keyboard(entry_ids, expanded=True)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("entry:edit:"))
async def edit_saved_entry(callback: CallbackQuery, state: FSMContext) -> None:
    entry_id = int(callback.data.rsplit(":", 1)[1])
    await state.update_data(entry_id=entry_id)
    await state.set_state(DiaryFlow.editing_saved_weight)
    await callback.message.edit_text("Напиши новую граммовку для этой записи.")
    await callback.answer()


@router.message(DiaryFlow.editing_saved_weight, F.text)
async def save_entry_weight(message: Message, state: FSMContext) -> None:
    grams = _parse_float(message.text or "", 1, 10000)
    if grams is None:
        await message.answer("Напиши граммы числом, например 180.")
        return
    data = await state.get_data()
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        entry = await DiaryService(session).update_entry_weight(user, int(data["entry_id"]), grams)
    await state.clear()
    if entry is None:
        await message.answer("Не нашёл эту запись.")
    else:
        await message.answer(
            f"Обновил: {food_label(entry)} — {entry.weight_g:.0f}г, {entry.kcal:.0f} ккал.",
            reply_markup=after_save_keyboard(),
        )


@router.callback_query(F.data.startswith("entry:delete:"))
async def delete_saved_entry(callback: CallbackQuery) -> None:
    entry_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        deleted = await DiaryService(session).delete_entry(user, entry_id)
    await callback.message.edit_text("Удалил запись." if deleted else "Не нашёл эту запись.")
    await callback.answer()


@router.callback_query(F.data.startswith("entry:fav:"))
async def favorite_saved_entry(callback: CallbackQuery) -> None:
    entry_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        diary = DiaryService(session)
        entry = await diary.get_entry(user, entry_id)
        if entry is None:
            await callback.answer("Не нашёл эту запись.", show_alert=True)
            return
        favorite = await WellnessService(session).add_favorite_from_entry(user, entry)
    await callback.answer(f"В избранном: {food_label(favorite)}", show_alert=True)


@router.message(F.text == "💧 Вода")
async def show_water(message: Message) -> None:
    text, reply_markup = await _water_view(message.from_user.id, message.from_user.username)
    await message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "nav:water")
async def show_water_inline(callback: CallbackQuery) -> None:
    text, reply_markup = await _water_view(callback.from_user.id, callback.from_user.username)
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


@router.message(F.text.in_({"🍽 Что съесть?", "🍽 Что съесть"}))
async def show_meal_suggestion(message: Message) -> None:
    text = await _meal_suggestion_view(message.from_user.id, message.from_user.username)
    await message.answer(text, reply_markup=after_save_keyboard())


@router.callback_query(F.data == "coach:meal")
async def show_meal_suggestion_inline(callback: CallbackQuery) -> None:
    text = await _meal_suggestion_view(callback.from_user.id, callback.from_user.username)
    await callback.message.edit_text(text, reply_markup=after_save_keyboard())
    await callback.answer()


async def _meal_suggestion_view(telegram_id: int, username: str | None) -> str:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id,
            username,
        )
        summary = await DiaryService(session).today_summary(user)
        water_ml = await WellnessService(session).today_water_ml(user)
    return meal_suggestion_text(summary, water_ml)


async def _water_view(telegram_id: int, username: str | None):
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id,
            username,
        )
        total = await WellnessService(session).today_water_ml(user)
    return (
        f"Сегодня воды: {total} мл. Можно быстро добавить ещё:",
        water_keyboard(),
    )


@router.callback_query(F.data.startswith("water:add:"))
async def add_water(callback: CallbackQuery) -> None:
    amount = int(callback.data.rsplit(":", 1)[1])
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        service = WellnessService(session)
        await service.add_water(user, amount)
        total = await service.today_water_ml(user)
    await callback.message.edit_text(
        f"Добавил {amount} мл. За сегодня: {total} мл.",
        reply_markup=after_water_save_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "water:custom")
async def ask_custom_water(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DiaryFlow.water_custom)
    await callback.message.edit_text("Сколько мл воды добавить?")
    await callback.answer()


@router.message(DiaryFlow.water_custom, F.text)
async def save_custom_water(message: Message, state: FSMContext) -> None:
    amount = _parse_int(message.text or "", 1, 5000)
    if amount is None:
        await message.answer("Напиши миллилитры числом.")
        return
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        service = WellnessService(session)
        await service.add_water(user, amount)
        total = await service.today_water_ml(user)
    await state.clear()
    await message.answer(
        f"Добавил {amount} мл. За сегодня: {total} мл.",
        reply_markup=after_water_save_keyboard(),
    )


@router.message(F.text == "🏃 Активность")
async def ask_activity(message: Message, state: FSMContext) -> None:
    await state.set_state(DiaryFlow.activity_custom)
    await message.answer(
        "Напиши активность или расход. Например: «я потратил 100 ккал» или «бег 30 минут»."
    )


@router.callback_query(F.data == "nav:activity")
async def ask_activity_from_more(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DiaryFlow.activity_custom)
    await callback.message.edit_text(
        "Напиши активность или расход. Например: «я потратил 100 ккал» или «бег 30 минут»."
    )
    await callback.answer()


@router.callback_query(F.data == "activity:custom")
async def ask_activity_inline(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DiaryFlow.activity_custom)
    await callback.message.edit_text(
        "Напиши активность или расход. Например: «я потратил 100 ккал» или «бег 30 минут»."
    )
    await callback.answer()


@router.message(DiaryFlow.activity_custom, F.text)
async def save_custom_activity(message: Message, state: FSMContext) -> None:
    added = await _add_activity_from_text(message, use_ai=True, allow_plain_kcal=True)
    if added:
        await state.clear()


@router.message(lambda message: bool(message.text) and looks_like_activity(message.text))
async def save_activity_from_plain_text(message: Message) -> None:
    await _add_activity_from_text(message, use_ai=True)


@router.message(F.text == "⚖️ Вес")
async def ask_weight(message: Message, state: FSMContext) -> None:
    text = await _weight_prompt(message.from_user.id, message.from_user.username)
    await state.set_state(DiaryFlow.weight)
    await message.answer(text)


@router.callback_query(F.data == "nav:weight")
async def ask_weight_from_more(callback: CallbackQuery, state: FSMContext) -> None:
    text = await _weight_prompt(callback.from_user.id, callback.from_user.username)
    await state.set_state(DiaryFlow.weight)
    await callback.message.edit_text(text)
    await callback.answer()


async def _weight_prompt(telegram_id: int, username: str | None) -> str:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id,
            username,
        )
        latest = await WellnessService(session).latest_weight(user)
    current = f"Последний вес: {latest.weight_kg:.1f} кг.\n" if latest else ""
    return f"{current}Напиши текущий вес в кг."


@router.message(DiaryFlow.weight, F.text)
async def save_weight(message: Message, state: FSMContext) -> None:
    weight = _parse_float(message.text or "", 30, 250)
    if weight is None:
        await message.answer("Напиши вес числом, например 74.5.")
        return
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        await WellnessService(session).add_weight(user, weight)
    await state.clear()
    await message.answer(f"Записал вес: {weight:.1f} кг.", reply_markup=after_save_keyboard())


@router.message(F.text.in_({"⭐ Любимое", "⭐ Избранное"}))
async def show_favorites(message: Message) -> None:
    text, reply_markup = await _favorites_view(message.from_user.id, message.from_user.username)
    await message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "nav:favorites")
async def show_favorites_inline(callback: CallbackQuery) -> None:
    text, reply_markup = await _favorites_view(callback.from_user.id, callback.from_user.username)
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


async def _favorites_view(telegram_id: int, username: str | None):
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id,
            username,
        )
        favorites = await WellnessService(session).favorites(user)
    if not favorites:
        return (
            "Любимых продуктов пока нет. Можно добавить вручную или сохранить запись из «Сегодня».",
            favorites_keyboard([]),
        )
    lines = ["Любимое:", ""]
    for index, favorite in enumerate(favorites, start=1):
        weight = f", {favorite.weight_g:.0f}г" if favorite.weight_g else ""
        lines.append(f"#{index} {food_label(favorite)}{weight} — {favorite.kcal:.0f} ккал")
    return (
        "\n".join(lines),
        favorites_keyboard([favorite.id for favorite in favorites]),
    )


@router.callback_query(F.data == "fav:manual")
async def ask_manual_favorite(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DiaryFlow.favorite_manual)
    await callback.message.edit_text(
        "Напиши любимый продукт так: название; граммы; ккал; белки; жиры; углеводы\n"
        "Например: кофе; 250; 80; 3; 2; 10"
    )
    await callback.answer()


@router.message(DiaryFlow.favorite_manual, F.text)
async def save_manual_favorite(message: Message, state: FSMContext) -> None:
    payload = _parse_favorite_payload(message.text or "")
    if payload is None:
        await message.answer("Формат: название; граммы; ккал; белки; жиры; углеводы")
        return
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        favorite = await WellnessService(session).add_favorite(user, payload)
    await state.clear()
    await message.answer(
        f"Добавил в любимое: {food_label(favorite)}.",
        reply_markup=after_save_keyboard(),
    )


@router.callback_query(F.data.startswith("fav:add:"))
async def add_favorite_to_diary(callback: CallbackQuery) -> None:
    favorite_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        wellness = WellnessService(session)
        favorite = await wellness.favorite(user, favorite_id)
        if favorite is None:
            await callback.answer("Не нашёл этот продукт.", show_alert=True)
            return
        entry = await DiaryService(session).add_entry(user, wellness.favorite_payload(favorite))
    await callback.message.edit_text(
        f"Готово: {food_label(entry)} — {entry.kcal:.0f} ккал.",
        reply_markup=after_save_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fav:del:"))
async def delete_favorite(callback: CallbackQuery) -> None:
    favorite_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        deleted = await WellnessService(session).delete_favorite(user, favorite_id)
    await callback.message.edit_text("Удалил из любимого." if deleted else "Не нашёл этот продукт.")
    await callback.answer()


@router.message(F.text.in_({"⏰ Напомнить", "⏰ Напоминания"}))
async def show_reminders(message: Message) -> None:
    text, reply_markup = await _reminders_view(message.from_user.id, message.from_user.username)
    await message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "nav:reminders")
async def show_reminders_inline(callback: CallbackQuery) -> None:
    text, reply_markup = await _reminders_view(callback.from_user.id, callback.from_user.username)
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


async def _reminders_view(telegram_id: int, username: str | None):
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id,
            username,
        )
        text = _reminders_text(user)
        reply_markup = reminders_keyboard(user)
    return text, reply_markup


@router.callback_query(F.data.in_({"reminders:on", "reminders:off"}))
async def toggle_reminders(callback: CallbackQuery) -> None:
    enabled = callback.data.endswith(":on")
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        user.reminders_enabled = enabled
        await session.commit()
        await session.refresh(user)
        text = _reminders_text(user)
        reply_markup = reminders_keyboard(user)
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(
    F.data.in_(
        {
            "reminders:meal:on",
            "reminders:meal:off",
            "reminders:weight-toggle:on",
            "reminders:weight-toggle:off",
        }
    )
)
async def toggle_reminder_kind(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    kind = parts[1]
    enabled = parts[2] == "on"
    field = "meal_reminders_enabled" if kind == "meal" else "weight_reminders_enabled"
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        setattr(user, field, enabled)
        await session.commit()
        await session.refresh(user)
        text = _reminders_text(user)
        reply_markup = reminders_keyboard(user)
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(
    F.data.in_(
        {
            "reminders:breakfast",
            "reminders:lunch",
            "reminders:dinner",
            "reminders:weight",
        }
    )
)
async def ask_reminder_time(callback: CallbackQuery, state: FSMContext) -> None:
    reminder = callback.data.rsplit(":", 1)[1]
    await state.update_data(reminder=reminder)
    await state.set_state(DiaryFlow.reminder_time)
    await callback.message.edit_text("Напиши время в формате HH:MM. Например: 20:30")
    await callback.answer()


@router.message(DiaryFlow.reminder_time, F.text)
async def save_reminder_time(message: Message, state: FSMContext) -> None:
    value = _parse_time(message.text or "")
    if value is None:
        await message.answer("Нужно время в формате HH:MM, например 09:00.")
        return
    data = await state.get_data()
    fields = {
        "breakfast": "breakfast_reminder_time",
        "lunch": "lunch_reminder_time",
        "dinner": "dinner_reminder_time",
        "weight": "weight_reminder_time",
    }
    field = fields[data["reminder"]]
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        setattr(user, field, value)
        await session.commit()
        await session.refresh(user)
        text = _reminders_text(user)
        reply_markup = reminders_keyboard(user)
    await state.clear()
    await message.answer(text, reply_markup=reply_markup)


@router.message(lambda message: message.text in {"📈 7 дней", "📈 Неделя"})
async def show_week(message: Message) -> None:
    await message.answer(await _week_view(message.from_user.id, message.from_user.username))


@router.callback_query(F.data == "nav:week")
async def show_week_inline(callback: CallbackQuery) -> None:
    text = await _week_view(callback.from_user.id, callback.from_user.username)
    await callback.message.edit_text(text)
    await callback.answer()


async def _week_view(telegram_id: int, username: str | None) -> str:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=telegram_id,
            username=username,
        )
        diary = DiaryService(session)
        analytics = await diary.weekly_analytics(user)
        has_subscription = has_active_subscription(user)
        patterns = await diary.nutrition_patterns(user) if has_subscription else None

    lines = [
        "Последние 7 дней:",
        "",
        f"Среднее: {analytics.average_kcal:.0f} / {analytics.target_kcal} ккал",
        f"Дней рядом с целью: {analytics.days_in_target}",
        weekly_coach_note(analytics),
    ]
    if has_subscription:
        lines.extend(automatic_pattern_notes(patterns))
    else:
        lines.append(ADVANCED_PATTERNS_UPSELL)
    lines.append("")
    for day in analytics.days:
        marker = "·" if day.entries_count else " "
        lines.append(
            f"{marker} {day.date_label}: {day.kcal:.0f} ккал, "
            f"Б {day.protein:.0f} / Ж {day.fat:.0f} / У {day.carbs:.0f}"
        )

    return "\n".join(lines)


def _today_view(
    summary,
    water_ml: int,
    *,
    patterns=None,
    show_advanced_patterns: bool = False,
    timezone_name: str = settings.default_timezone,
    include_advice: bool = False,
):
    target_line = f"🔥 {summary.kcal:.0f} / {summary.target_kcal} ккал"
    if summary.activity_kcal:
        target_line += (
            f" (база {summary.base_target_kcal} + активность {summary.activity_kcal:.0f})"
        )

    lines = [
        "Сегодня по дневнику:",
        "",
        target_line,
        "",
        _macro_line("Белки", summary.protein, summary.target_protein),
        _macro_line("Жиры", summary.fat, summary.target_fat),
        _macro_line("Углеводы", summary.carbs, summary.target_carbs),
        f"💧 Вода: {water_ml} мл",
    ]
    entry_ids: list[int] = []
    if summary.entries:
        lines.extend(["", "────────"])
        for index, entry in enumerate(summary.entries, start=1):
            entry_ids.append(entry.id)
            lines.append(_entry_line(index, entry, timezone_name))

    if include_advice:
        forecast = end_of_day_forecast(summary, patterns)
        lines.extend(
            [
                "",
                "✨ AI-совет дня",
                "",
                f"✅ {smart_day_coach(summary, water_ml)}",
                f"🎯 Фокус: {daily_focus(summary, water_ml)}.",
            ]
        )
        if forecast:
            lines.append(f"🔮 {forecast}")
        if show_advanced_patterns:
            lines.extend(f"📌 {note}" for note in automatic_pattern_notes(patterns)[:1])
        else:
            lines.append(f"🔒 {ADVANCED_PATTERNS_UPSELL}")
        lines.extend(
            [
                f"🍽 {remaining_advice(summary)}",
                f"⚖️ {diet_quality_note(summary)}",
                f"🌙 {smart_evening_hint(summary)}",
            ]
        )

    return "\n".join(lines), food_entries_keyboard(entry_ids)


def _entry_line(index: int, entry, timezone_name: str) -> str:
    weight = f", {entry.weight_g:.0f}г" if entry.weight_g else ""
    return (
        f"{index}. {_entry_time_label(entry.created_at, timezone_name)} "
        f"{food_label(entry)}{weight} — {entry.kcal:.0f} ккал"
    )


def _entry_time_label(created_at: datetime, timezone_name: str) -> str:
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo(settings.default_timezone)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return created_at.astimezone(tz).strftime("%H:%M")


def _macro_line(label: str, value: float, target: float) -> str:
    delta = target - value
    if delta >= 0:
        suffix = f"осталось {delta:.0f}г"
    else:
        suffix = f"перебор {abs(delta):.0f}г"
    return f"{label}: {value:.0f} / {target:.0f}г, {suffix}"


def _reminders_text(user) -> str:
    status = "включены" if user.reminders_enabled else "выключены"
    meal_status = "включены" if user.meal_reminders_enabled else "выключены"
    weight_status = "включены" if user.weight_reminders_enabled else "выключены"
    return "\n".join(
        [
            "Напоминания:",
            "",
            f"Общий статус: {status}",
            f"Еда: {meal_status}",
            f"Утро: {user.breakfast_reminder_time or '10:00'}",
            f"Обед: {user.lunch_reminder_time or '14:00'}",
            f"Вечер: {user.dinner_reminder_time or '20:30'}",
            f"Вес: {weight_status}, {user.weight_reminder_time or '09:00'}",
        ]
    )


def _parse_int(text: str, minimum: int, maximum: int) -> int | None:
    return parse_int_from_text(text, minimum, maximum)


async def _add_activity_from_text(
    message: Message,
    use_ai: bool,
    allow_plain_kcal: bool = False,
) -> bool:
    text = message.text or ""
    kcal = parse_activity_kcal(text, allow_plain_kcal=allow_plain_kcal)
    source = "manual"
    estimate: ActivityEstimate | None = None

    if kcal is not None:
        estimate = ActivityEstimate(name="Активность", kcal=kcal, confidence=None)
    elif use_ai:
        if not await _ensure_ai_available(message):
            return False
        estimate = await AIActivityService().parse_text(text)
        await _record_ai_request(message, "activity_text")
        source = "ai_activity"

    if estimate is None:
        await message.answer("Напиши расход в ккал или опиши активность подробнее.")
        return False

    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        service = WellnessService(session)
        activity = await service.add_activity(user, estimate, source)
        total = await service.today_activity_kcal(user)

    await message.answer(
        f"Добавил активность: {activity.activity_name} — {activity.kcal:.0f} ккал. "
        f"За сегодня активность: {total:.0f} ккал.",
        reply_markup=after_activity_save_keyboard(),
    )
    return True


async def _ensure_ai_available(message: Message, request_count: int = 1) -> bool:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        usage_service = AIUsageService(session)
        if not has_active_subscription(user):
            try:
                await usage_service.ensure_trial_allowed(user, request_count=request_count)
            except AILimitReachedError:
                await message.answer(
                    "Бесплатные AI-запросы закончились. "
                    "Можно написать расход вручную: «я потратил 100 ккал»."
                )
                return False
            return True

        try:
            await usage_service.ensure_allowed(user, request_count=request_count)
        except AILimitReachedError:
            await message.answer(
                "Лимит AI на сегодня закончился. "
                "Можно написать расход вручную: «я потратил 100 ккал»."
            )
            return False
    return True


async def _record_ai_request(message: Message, request_type: str) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        await AIUsageService(session).record_request(user, request_type)


def _parse_float(text: str, minimum: float, maximum: float) -> float | None:
    try:
        value = float(text.replace(",", ".").strip())
    except ValueError:
        return None
    return value if minimum <= value <= maximum else None


def _parse_time(text: str) -> str | None:
    parts = text.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def _parse_favorite_payload(text: str) -> FoodEntryCreate | None:
    parts = [part.strip() for part in text.split(";")]
    if len(parts) != 6 or not parts[0]:
        return None
    try:
        weight_g = float(parts[1].replace(",", "."))
        kcal = float(parts[2].replace(",", "."))
        protein = float(parts[3].replace(",", "."))
        fat = float(parts[4].replace(",", "."))
        carbs = float(parts[5].replace(",", "."))
    except ValueError:
        return None
    if weight_g <= 0 or kcal < 0 or min(protein, fat, carbs) < 0:
        return None
    return FoodEntryCreate(
        name=parts[0],
        weight_g=weight_g,
        kcal=kcal,
        protein=protein,
        fat=fat,
        carbs=carbs,
        source="manual",
    )
