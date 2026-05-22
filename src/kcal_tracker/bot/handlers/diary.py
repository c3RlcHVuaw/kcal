from __future__ import annotations

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from kcal_tracker.bot.keyboards import (
    activity_logs_keyboard,
    activity_menu_keyboard,
    after_activity_save_keyboard,
    after_save_keyboard,
    after_water_save_keyboard,
    favorites_keyboard,
    food_entries_keyboard,
    progress_share_keyboard,
    reminders_keyboard,
    subscription_cta_keyboard,
    water_keyboard,
    weight_dashboard_keyboard,
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
from kcal_tracker.services.ai_food import AIFoodService
from kcal_tracker.services.ai_usage import AILimitReachedError, AIUsageService
from kcal_tracker.services.diary import DiaryService, estimate_from_entry
from kcal_tracker.services.food_insights import food_label
from kcal_tracker.services.growth import GrowthService, WeeklyMissions, progress_share_url
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
    weekly_score,
)
from kcal_tracker.services.share_cards import daily_progress_card, weekly_progress_card
from kcal_tracker.services.subscriptions import has_active_subscription
from kcal_tracker.services.users import UserService
from kcal_tracker.services.wellness import WellnessService

router = Router()
logger = logging.getLogger(__name__)

ADVANCED_PATTERNS_UPSELL = (
    "Продвинутые паттерны по завтракам, напиткам и вечерам доступны в подписке."
)


class DiaryFlow(StatesGroup):
    editing_saved_weight = State()
    refining_saved_entry = State()
    water_custom = State()
    activity_custom = State()
    weight = State()
    favorite_manual = State()
    reminder_time = State()


@router.message(
    lambda message: message.text in {"📊 Сегодня", "📊 Мой день", "🔥 Остаток", "🔥 Калории"}
)
async def show_today(message: Message) -> None:
    text, reply_markup = await _day_view_for_user(
        message.from_user.id,
        message.from_user.username,
        days_ago=0,
    )
    await message.answer(
        text,
        reply_markup=reply_markup,
    )


@router.callback_query(F.data == "nav:today")
async def show_today_inline(callback: CallbackQuery) -> None:
    text, reply_markup = await _day_view_for_user(
        callback.from_user.id,
        callback.from_user.username,
        days_ago=0,
    )
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data == "diary:yesterday")
async def show_yesterday_inline(callback: CallbackQuery) -> None:
    text, reply_markup = await _day_view_for_user(
        callback.from_user.id,
        callback.from_user.username,
        days_ago=1,
    )
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await _send_yesterday_card(
        callback.message,
        callback.from_user.id,
        callback.from_user.username,
        caption="Карточка вчерашнего дня.",
    )
    await callback.answer()


@router.callback_query(F.data == "nav:today:full")
async def show_today_full_inline(callback: CallbackQuery) -> None:
    text, reply_markup = await _day_view_for_user(
        callback.from_user.id,
        callback.from_user.username,
        days_ago=0,
    )
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data == "day:yesterday-card")
async def send_yesterday_share_card(callback: CallbackQuery) -> None:
    await _send_yesterday_card(
        callback.message,
        callback.from_user.id,
        callback.from_user.username,
        caption="Готово, карточка вчерашнего дня.",
    )
    await callback.answer()


async def _send_yesterday_card(
    message: Message,
    telegram_id: int,
    username: str | None,
    *,
    caption: str,
) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id,
            username,
        )
        diary = DiaryService(session)
        wellness = WellnessService(session)
        summary = await diary.summary_for_day_offset(user, days_ago=1)
        water_ml = await wellness.water_ml_for_day_offset(user, days_ago=1)
        activities = await wellness.activities_for_day_offset(user, days_ago=1)
        date_label = _day_offset_date_label(user.timezone, days_ago=1)

    image_bytes = daily_progress_card(
        summary,
        date_label=date_label,
        water_ml=water_ml,
        activities=activities,
    )
    await message.answer_photo(
        BufferedInputFile(image_bytes, filename="kcal_yesterday.png"),
        caption=caption,
    )


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


@router.callback_query(F.data == "activity:manage")
async def show_activity_management(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        activities = await WellnessService(session).today_activities(user)

    if not activities:
        await callback.answer("Сегодня пока нет активности.", show_alert=True)
        return
    text = _activity_management_text(activities, user.timezone)
    activity_ids = [activity.id for activity in activities]
    await callback.message.edit_text(
        text,
        reply_markup=activity_logs_keyboard(activity_ids, expanded=True),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("activity:delete:"))
async def delete_saved_activity(callback: CallbackQuery) -> None:
    activity_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        service = WellnessService(session)
        deleted = await service.delete_activity(user, activity_id)
        activities = await service.today_activities(user)
        total = await service.today_activity_kcal(user)

    if deleted is None:
        await callback.message.edit_text("Не нашёл эту активность.")
    elif activities:
        activity_ids = [activity.id for activity in activities]
        await callback.message.edit_text(
            f"Удалил активность. За сегодня: {total:.0f} ккал.\n\n"
            + _activity_management_text(activities, user.timezone),
            reply_markup=activity_logs_keyboard(activity_ids, expanded=True),
        )
    else:
        await callback.message.edit_text(
            f"Удалил активность. За сегодня: {total:.0f} ккал.",
            reply_markup=activity_menu_keyboard([]),
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
    await callback.answer(f"В шаблонах: {food_label(favorite)}", show_alert=True)


@router.callback_query(F.data.startswith("entry:refine:"))
async def refine_saved_entry(callback: CallbackQuery, state: FSMContext) -> None:
    entry_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        entry = await DiaryService(session).get_entry(user, entry_id)

    if entry is None:
        await callback.answer("Не нашёл эту запись.", show_alert=True)
        return
    if entry.source not in {"ai_photo", "manual"}:
        await callback.answer("AI-уточнение доступно для AI-записей.", show_alert=True)
        return

    await state.update_data(entry_id=entry_id)
    await state.set_state(DiaryFlow.refining_saved_entry)
    await callback.message.edit_text(
        f"Уточняем: {food_label(entry)}.\n\n"
        "Напиши, что поправить: «добавь 20 г соуса», "
        "«это было 200 г», «убери хлеб», «была половина порции»."
    )
    await callback.answer()


@router.message(DiaryFlow.refining_saved_entry, F.text)
async def save_saved_entry_refinement(message: Message, state: FSMContext) -> None:
    refinement = " ".join((message.text or "").split())
    if not refinement:
        await message.answer("Напиши уточнение текстом, например: добавь 20 г соуса.")
        return
    if not await _ensure_ai_available(message):
        return

    data = await state.get_data()
    entry_id = int(data["entry_id"])
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        diary = DiaryService(session)
        entry = await diary.get_entry(user, entry_id)
        if entry is None:
            await state.clear()
            await message.answer("Не нашёл эту запись.")
            return
        estimate = estimate_from_entry(entry)

    await message.answer("Пересчитываю сохранённую запись.")
    try:
        refined = await AIFoodService().refine_estimate(estimate, refinement)
    except Exception:
        logger.exception("Saved food refinement failed")
        await message.answer("Не смог сейчас пересчитать запись. Попробуй ещё раз чуть проще.")
        return
    await _record_ai_request(message, "saved_food_refine")
    if not refined.foods:
        await message.answer("AI не смог уверенно пересчитать запись. Попробуй чуть проще.")
        return

    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        updated = await DiaryService(session).update_entry_estimate(
            user,
            entry_id,
            refined.foods[0],
        )

    await state.clear()
    if updated is None:
        await message.answer("Не нашёл эту запись.")
        return
    await message.answer(
        f"Обновил: {food_label(updated)} — {updated.weight_g or 0:.0f}г, "
        f"{updated.kcal:.0f} ккал.",
        reply_markup=after_save_keyboard(),
    )


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
async def show_activity(message: Message) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        activities = await WellnessService(session).today_activities(user)
    activity_ids = [activity.id for activity in activities]
    await message.answer(
        _activity_dashboard_text(activities, user.timezone),
        reply_markup=activity_menu_keyboard(activity_ids),
    )


@router.callback_query(F.data == "nav:activity")
async def show_activity_from_more(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        activities = await WellnessService(session).today_activities(user)
    activity_ids = [activity.id for activity in activities]
    await callback.message.edit_text(
        _activity_dashboard_text(activities, user.timezone),
        reply_markup=activity_menu_keyboard(activity_ids),
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
async def show_weight(message: Message) -> None:
    text = await _weight_dashboard_view(message.from_user.id, message.from_user.username)
    await message.answer(text, reply_markup=weight_dashboard_keyboard())


@router.callback_query(F.data == "nav:weight")
async def show_weight_from_more(callback: CallbackQuery) -> None:
    text = await _weight_dashboard_view(callback.from_user.id, callback.from_user.username)
    await callback.message.edit_text(text, reply_markup=weight_dashboard_keyboard())
    await callback.answer()


@router.callback_query(F.data == "weight:add")
async def ask_weight_from_dashboard(callback: CallbackQuery, state: FSMContext) -> None:
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


async def _weight_dashboard_view(telegram_id: int, username: str | None) -> str:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id,
            username,
        )
        trend = await WellnessService(session).weight_trend(user)

    if not trend.logs:
        return "⚖️ Вес\n\nПока нет записей. Добавь первый вес, и я покажу тренд."

    lines = [
        "⚖️ Вес",
        "",
        (
            f"Сейчас: {trend.latest_kg:.1f} кг"
            if trend.latest_kg is not None
            else "Сейчас: нет данных"
        ),
    ]
    if trend.average_7d_kg is not None:
        lines.append(f"Среднее за 7 дней: {trend.average_7d_kg:.1f} кг")
    if trend.delta_7d_kg is not None:
        sign = "+" if trend.delta_7d_kg > 0 else ""
        lines.append(f"Тренд: {trend.trend_label}, {sign}{trend.delta_7d_kg:.1f} кг")
    lines.extend(["", _weight_chart(trend.logs[-14:])])
    return "\n".join(lines)


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
    text = await _weight_dashboard_view(message.from_user.id, message.from_user.username)
    await message.answer(
        f"Записал вес: {weight:.1f} кг.\n\n{text}",
        reply_markup=weight_dashboard_keyboard(),
    )


@router.message(F.text.in_({"⭐ Любимое", "⭐ Избранное", "⚡ Шаблоны"}))
async def show_favorites(message: Message) -> None:
    text, reply_markup = await _favorites_view(message.from_user.id, message.from_user.username)
    await message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "nav:favorites")
@router.callback_query(F.data == "nav:templates")
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
            "Шаблонов пока нет. Можно добавить вручную или сохранить запись из «Сегодня» "
            "кнопкой ⭐.",
            favorites_keyboard([]),
        )
    lines = ["⚡ Шаблоны еды:", ""]
    for index, favorite in enumerate(favorites, start=1):
        weight = f", {favorite.weight_g:.0f}г" if favorite.weight_g else ""
        lines.append(f"#{index} {food_label(favorite)}{weight} — {favorite.kcal:.0f} ккал")
    lines.extend(["", "Нажми ➕ у шаблона, чтобы быстро добавить его в дневник без AI."])
    return (
        "\n".join(lines),
        favorites_keyboard([favorite.id for favorite in favorites]),
    )


@router.callback_query(F.data == "fav:manual")
async def ask_manual_favorite(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DiaryFlow.favorite_manual)
    await callback.message.edit_text(
        "Напиши шаблон так: название; граммы; ккал; белки; жиры; углеводы\n"
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
        f"Добавил шаблон: {food_label(favorite)}.",
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
    await callback.message.edit_text("Удалил шаблон." if deleted else "Не нашёл этот шаблон.")
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
    text = await _week_view(message.from_user.id, message.from_user.username)
    bot = await message.bot.me()
    if bot.username is None:
        await message.answer(text)
        return
    reply_markup = await _progress_share_markup(
        message.from_user.id,
        message.from_user.username,
        bot.username,
        text,
    )
    await message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "nav:week")
async def show_week_inline(callback: CallbackQuery) -> None:
    text = await _week_view(callback.from_user.id, callback.from_user.username)
    bot = await callback.bot.me()
    if bot.username is None:
        await callback.message.edit_text(text)
        await callback.answer()
        return
    reply_markup = await _progress_share_markup(
        callback.from_user.id,
        callback.from_user.username,
        bot.username,
        text,
    )
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data == "week:share-card")
async def send_week_share_card(callback: CallbackQuery) -> None:
    bot = await callback.bot.me()
    if bot.username is None:
        await callback.answer("Не смог собрать ссылку для этого бота.", show_alert=True)
        return

    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        growth = GrowthService(session)
        analytics = await DiaryService(session).weekly_analytics(user)
        missions = await growth.weekly_missions(user)
        referral_link = await growth.referral_link(user, bot.username)

    image_bytes = weekly_progress_card(analytics, missions, referral_link)
    await callback.message.answer_photo(
        BufferedInputFile(image_bytes, filename="kcal_week.png"),
        caption="Готово, карточка недели. Её удобно отправить друзьям или в сторис.",
    )
    await callback.answer()


@router.callback_query(F.data == "missions:claim")
async def claim_weekly_missions_bonus(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        until = await GrowthService(session).claim_weekly_mission_bonus(user)

    if until is None:
        await callback.answer(
            "Бонус пока недоступен: нужно закрыть 2 миссии недели.",
            show_alert=True,
        )
        return
    await callback.message.answer(f"Готово, добавил +1 день AI. Доступ открыт до {until:%d.%m.%Y}.")
    await callback.answer()


@router.message(lambda message: message.text == "📅 Месяц")
async def show_month(message: Message) -> None:
    await message.answer(await _month_view(message.from_user.id, message.from_user.username))


@router.callback_query(F.data == "nav:month")
async def show_month_inline(callback: CallbackQuery) -> None:
    text = await _month_view(callback.from_user.id, callback.from_user.username)
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
        habits = await WellnessService(session).habit_summary(user)
        missions = await GrowthService(session).weekly_missions(user)

    lines = [
        "📈 Недельный отчёт",
        "",
        f"Оценка: {weekly_score(analytics)}/10",
        f"Среднее: {analytics.average_kcal:.0f} / {analytics.target_kcal} ккал",
        f"Дней рядом с целью: {analytics.days_in_target}",
        "",
        *_week_highlight_lines(analytics),
        "",
        *_habit_lines(habits),
        "",
        *_weekly_mission_lines(missions),
        "",
        f"🧠 {weekly_coach_note(analytics)}",
    ]
    if has_subscription:
        lines.extend(f"📌 {note}" for note in automatic_pattern_notes(patterns))
    else:
        lines.append(f"🔒 {ADVANCED_PATTERNS_UPSELL}")
    lines.append("")
    for day in analytics.days:
        marker = "·" if day.entries_count else " "
        lines.append(
            f"{marker} {day.date_label}: {day.kcal:.0f} ккал, "
            f"Б {day.protein:.0f} / Ж {day.fat:.0f} / У {day.carbs:.0f}"
        )

    return "\n".join(lines)


async def _progress_share_markup(
    telegram_id: int,
    username: str | None,
    bot_username: str,
    week_text: str,
):
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=telegram_id,
            username=username,
        )
        growth = GrowthService(session)
        referral_link = await growth.referral_link(user, bot_username)
        missions = await growth.weekly_missions(user)

    score_line = next(
        (line for line in week_text.splitlines() if line.startswith("Оценка:")),
        "",
    )
    average_line = next(
        (line for line in week_text.splitlines() if line.startswith("Среднее:")),
        "",
    )
    share_text = "\n".join(
        line
        for line in (
            "Мой недельный прогресс в Kcal:",
            score_line,
            average_line,
            f"Попробуй тоже: {referral_link}",
        )
        if line
    )
    return progress_share_keyboard(
        progress_share_url(share_text),
        missions_bonus_available=missions.eligible_for_bonus,
    )


async def _month_view(telegram_id: int, username: str | None) -> str:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=telegram_id,
            username=username,
        )
        diary = DiaryService(session)
        analytics = await diary.weekly_analytics(user, days=30)
        habits = await WellnessService(session).habit_summary(user, days=30)
        weight = await WellnessService(session).weight_trend(user, days=30)

    tracked = [day for day in analytics.days if day.entries_count]
    if not tracked:
        return (
            "📅 Месячный отчёт\n\n"
            "Пока мало данных. Записывай еду несколько дней, и здесь появится нормальный разбор."
        )

    best = min(tracked, key=lambda day: abs(day.kcal - analytics.target_kcal))
    high_days = sum(1 for day in tracked if day.kcal > analytics.target_kcal + 250)
    low_days = sum(1 for day in tracked if day.kcal < analytics.target_kcal - 350)
    protein_average = sum(day.protein for day in tracked) / len(tracked)
    delta = analytics.average_kcal - analytics.target_kcal

    lines = [
        "📅 Месячный отчёт",
        "",
        f"Дней с дневником: {len(tracked)}/30",
        f"Среднее: {analytics.average_kcal:.0f} / {analytics.target_kcal} ккал",
        f"Дней рядом с целью: {analytics.days_in_target}",
        f"Лучший день по калориям: {best.date_label} ({best.kcal:.0f} ккал)",
        f"Белок в среднем: {protein_average:.0f} г/день",
        "",
        "Паттерны месяца:",
        _month_delta_line(delta),
        f"Дней с заметным перебором: {high_days}",
        f"Дней с сильным недобором: {low_days}",
        "",
        *_habit_lines(habits),
    ]
    if weight.latest_kg is not None:
        sign = "+" if (weight.delta_7d_kg or 0) > 0 else ""
        lines.extend(
            [
                "",
                "Вес:",
                f"Последний: {weight.latest_kg:.1f} кг",
                f"Тренд: {weight.trend_label}, {sign}{(weight.delta_7d_kg or 0):.1f} кг",
            ]
        )
    lines.extend(["", f"Фокус на следующий месяц: {_month_focus(delta, protein_average)}."])
    return "\n".join(lines)


def _week_highlight_lines(analytics) -> list[str]:
    tracked = [day for day in analytics.days if day.entries_count]
    if not tracked:
        return ["Итог: пока мало данных для разбора."]

    best = min(tracked, key=lambda day: abs(day.kcal - analytics.target_kcal))
    average_protein = sum(day.protein for day in tracked) / len(tracked)
    average_delta = analytics.average_kcal - analytics.target_kcal
    if abs(average_delta) <= 150:
        delta_text = "средняя калорийность рядом с целью"
    elif average_delta > 0:
        delta_text = f"средний перебор около {average_delta:.0f} ккал"
    else:
        delta_text = f"средний недобор около {abs(average_delta):.0f} ккал"

    return [
        "Коротко:",
        f"Лучший день по цели: {best.date_label} ({best.kcal:.0f} ккал).",
        f"Белок в среднем: {average_protein:.0f} г/день.",
        f"Главный вывод: {delta_text}.",
    ]


def _month_delta_line(delta: float) -> str:
    if abs(delta) <= 150:
        return "Средняя калорийность рядом с целью."
    if delta > 0:
        return f"В среднем перебор около {delta:.0f} ккал в день."
    return f"В среднем недобор около {abs(delta):.0f} ккал в день."


def _month_focus(delta: float, protein_average: float) -> str:
    if protein_average < 80:
        return "поднять белок в обычных приёмах пищи"
    if delta > 200:
        return "найти 1-2 частых источника лишних калорий"
    if delta < -300:
        return "не проваливаться в слишком низкую калорийность"
    return "сохранить текущий ритм и стабильность записей"


def _weekly_mission_lines(missions: WeeklyMissions) -> list[str]:
    lines = ["Миссии недели:"]
    for mission in missions.missions:
        marker = "✓" if mission.completed else "·"
        progress = f"{min(mission.current, mission.target)}/{mission.target}"
        lines.append(f"{marker} {mission.title}: {progress}")
    if missions.eligible_for_bonus:
        lines.append("Бонус: можно забрать +1 день AI.")
    elif missions.bonus_claimed:
        lines.append("Бонус недели уже забран.")
    else:
        lines.append("Выполни 2 миссии, чтобы забрать +1 день AI.")
    return lines


def _habit_lines(habits) -> list[str]:
    return [
        "Серии и привычки:",
        f"Еда: {habits.food_streak_days} дн. подряд, {habits.tracked_food_days_30}/30 дней.",
        f"Вода: {habits.water_streak_days} дн. подряд, {habits.tracked_water_days_30}/30 дней.",
        f"Вес: {habits.weight_streak_days} дн. подряд, {habits.tracked_weight_days_30}/30 дней.",
        f"Сильная привычка сейчас: {habits.best_habit}.",
    ]


def _weight_chart(logs) -> str:
    if len(logs) == 1:
        return f"График: {logs[0].weight_kg:.1f} кг"

    values = [log.weight_kg for log in logs]
    minimum = min(values)
    maximum = max(values)
    blocks = "▁▂▃▄▅▆▇█"
    if maximum == minimum:
        spark = blocks[3] * len(values)
    else:
        spark = "".join(
            blocks[round((value - minimum) / (maximum - minimum) * (len(blocks) - 1))]
            for value in values
        )
    return f"График, последние записи: {spark}\nДиапазон: {minimum:.1f}-{maximum:.1f} кг"


async def _day_view_for_user(
    telegram_id: int,
    username: str | None,
    *,
    days_ago: int,
):
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=telegram_id,
            username=username,
        )
        diary = DiaryService(session)
        summary = await diary.summary_for_day_offset(user, days_ago=days_ago)
        has_subscription = has_active_subscription(user)
        patterns = (
            await diary.nutrition_patterns(user)
            if has_subscription and days_ago == 0
            else None
        )
        wellness = WellnessService(session)
        water_ml = await wellness.water_ml_for_day_offset(user, days_ago=days_ago)
        activities = await wellness.activities_for_day_offset(user, days_ago=days_ago)
        timezone_name = user.timezone

    return _today_view(
        summary,
        water_ml,
        activities=activities,
        patterns=patterns,
        show_advanced_patterns=has_subscription and days_ago == 0,
        timezone_name=timezone_name,
        include_advice=days_ago == 0,
        title=_day_offset_title(timezone_name, days_ago=days_ago),
        mode="yesterday" if days_ago == 1 else "today",
    )


def _today_view(
    summary,
    water_ml: int,
    *,
    activities=None,
    patterns=None,
    show_advanced_patterns: bool = False,
    timezone_name: str = settings.default_timezone,
    include_advice: bool = False,
    title: str = "📊 Сегодня",
    mode: str = "today",
):
    activities = activities or []
    target_line = f"🔥 {summary.kcal:.0f} / {summary.target_kcal} ккал"
    if summary.activity_kcal:
        target_line += (
            f" (база {summary.base_target_kcal} + активность {summary.activity_kcal:.0f})"
        )

    lines = [
        title,
        "",
        target_line,
        _macro_line("Белки", summary.protein, summary.target_protein),
        _macro_line("Жиры", summary.fat, summary.target_fat),
        _macro_line("Углеводы", summary.carbs, summary.target_carbs),
        f"💧 Вода: {water_ml} мл",
    ]
    entry_ids: list[int] = []
    if summary.entries:
        entry_ids = [entry.id for entry in summary.entries]
        for label, entries in _entries_by_meal(summary.entries, timezone_name):
            if not entries:
                continue
            kcal = sum(entry.kcal for entry in entries)
            lines.extend(["", f"{label} - {kcal:.0f} ккал"])
            for entry in entries:
                index = summary.entries.index(entry) + 1
                lines.append(_entry_line(index, entry, timezone_name))
    else:
        lines.extend(["", "🍽 Записей пока нет"])

    if activities:
        lines.extend(["", "🏃 Активность"])
        for index, activity in enumerate(activities, start=1):
            lines.append(_activity_line(index, activity, timezone_name))

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

    return "\n".join(lines), food_entries_keyboard(entry_ids, mode=mode)


def _day_offset_title(timezone_name: str, *, days_ago: int) -> str:
    if days_ago == 1:
        return f"📊 Вчера, {_day_offset_date_label(timezone_name, days_ago=days_ago)}"
    return "📊 Сегодня"


def _day_offset_date_label(timezone_name: str, *, days_ago: int) -> str:
    tz = _safe_timezone(timezone_name)
    target_date = datetime.now(tz).date()
    if days_ago:
        target_date = target_date.fromordinal(target_date.toordinal() - days_ago)
    return target_date.strftime("%d.%m")


def _safe_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        logger.warning("Invalid user timezone %s, falling back to default", timezone_name)
        return ZoneInfo(settings.default_timezone)


def _entry_line(index: int, entry, timezone_name: str) -> str:
    weight = f", {entry.weight_g:.0f}г" if entry.weight_g else ""
    return (
        f"{index}. {_entry_time_label(entry.created_at, timezone_name)} "
        f"{food_label(entry)}{weight} — {entry.kcal:.0f} ккал"
    )


def _activity_management_text(activities, timezone_name: str) -> str:
    lines = ["🏃 Активность сегодня", ""]
    for index, activity in enumerate(activities, start=1):
        lines.append(_activity_line(index, activity, timezone_name))
    lines.extend(["", "Нажми на запись, чтобы удалить её из дневника."])
    return "\n".join(lines)


def _activity_dashboard_text(activities, timezone_name: str) -> str:
    if not activities:
        return "\n".join(
            [
                "🏃 Активность",
                "",
                "Сегодня активности пока нет.",
                "Можно добавить расход вручную или через Apple Health.",
            ]
        )
    total = sum(activity.kcal for activity in activities)
    lines = ["🏃 Активность", "", f"За сегодня: {total:.0f} ккал", ""]
    for index, activity in enumerate(activities, start=1):
        lines.append(_activity_line(index, activity, timezone_name))
    return "\n".join(lines)


def _activity_line(index: int, activity, timezone_name: str) -> str:
    return (
        f"{index}. {_entry_time_label(activity.created_at, timezone_name)} "
        f"{activity.activity_name} — {activity.kcal:.0f} ккал"
    )


def _meal_summary_lines(entries, timezone_name: str) -> list[str]:
    lines: list[str] = []
    for label, meal_entries in _entries_by_meal(entries, timezone_name):
        kcal = sum(entry.kcal for entry in meal_entries)
        count = len(meal_entries)
        suffix = f"{kcal:.0f} ккал" if count else "пока нет"
        if count:
            suffix += f" · {count}"
        lines.append(f"{label}: {suffix}")
    return lines


def _entries_by_meal(entries, timezone_name: str):
    buckets = {
        "breakfast": [],
        "lunch": [],
        "dinner": [],
        "snacks": [],
    }
    for entry in entries:
        buckets[_meal_key(entry.created_at, timezone_name)].append(entry)
    return [
        ("🌅 Завтрак", buckets["breakfast"]),
        ("☀️ Обед", buckets["lunch"]),
        ("🌙 Ужин", buckets["dinner"]),
        ("🍿 Перекусы", buckets["snacks"]),
    ]


def _meal_key(created_at: datetime, timezone_name: str) -> str:
    hour = int(_entry_time_label(created_at, timezone_name).split(":", 1)[0])
    if 5 <= hour < 12:
        return "breakfast"
    if 12 <= hour < 16:
        return "lunch"
    if 18 <= hour < 23:
        return "dinner"
    return "snacks"


def _entry_time_label(created_at: datetime, timezone_name: str) -> str:
    tz = _safe_timezone(timezone_name)
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
            "Поведение: если приём пищи уже записан, лишний пинг не отправляю.",
            "После тишины: мягко напомню вернуться, если дневник пустует 3+ дня.",
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
                    "Можно написать расход вручную: «я потратил 100 ккал».",
                    reply_markup=subscription_cta_keyboard(),
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
