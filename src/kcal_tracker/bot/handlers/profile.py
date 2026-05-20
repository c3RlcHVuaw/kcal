from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from kcal_tracker.bot.keyboards import (
    activity_keyboard,
    gender_keyboard,
    goal_keyboard,
    language_keyboard,
    main_menu,
    settings_keyboard,
)
from kcal_tracker.config import settings as app_settings
from kcal_tracker.database import SessionLocal
from kcal_tracker.services.export import ExportService
from kcal_tracker.services.profile import (
    apply_default_macro_targets,
    calculate_daily_kcal_target,
    profile_summary,
)
from kcal_tracker.services.users import UserService

router = Router()


class OnboardingFlow(StatesGroup):
    age = State()
    height = State()
    weight = State()


class SettingsFlow(StatesGroup):
    age = State()
    height = State()
    weight = State()
    kcal = State()
    macros = State()


@router.callback_query(F.data.startswith("onboarding:language:"))
async def onboarding_language(callback: CallbackQuery) -> None:
    language = callback.data.rsplit(":", 1)[1]
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        user.language = language
        await session.commit()
    await callback.message.edit_text(
        "Укажи пол, чтобы я точнее посчитал цель.",
        reply_markup=gender_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("onboarding:gender:"))
async def onboarding_gender(callback: CallbackQuery, state: FSMContext) -> None:
    gender = callback.data.rsplit(":", 1)[1]
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        user.gender = gender
        await session.commit()
    await state.set_state(OnboardingFlow.age)
    await callback.message.edit_text("Сколько тебе лет?")
    await callback.answer()


@router.message(OnboardingFlow.age, F.text)
async def onboarding_age(message: Message, state: FSMContext) -> None:
    age = _parse_int(message.text, 10, 100)
    if age is None:
        await message.answer("Напиши возраст числом, например 29.")
        return
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        user.age = age
        await session.commit()
    await state.set_state(OnboardingFlow.height)
    await message.answer("Теперь рост в сантиметрах.")


@router.message(OnboardingFlow.height, F.text)
async def onboarding_height(message: Message, state: FSMContext) -> None:
    height = _parse_float(message.text, 100, 240)
    if height is None:
        await message.answer("Напиши рост числом, например 178.")
        return
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        user.height = height
        await session.commit()
    await state.set_state(OnboardingFlow.weight)
    await message.answer("И текущий вес в кг.")


@router.message(OnboardingFlow.weight, F.text)
async def onboarding_weight(message: Message, state: FSMContext) -> None:
    weight = _parse_float(message.text, 30, 250)
    if weight is None:
        await message.answer("Напиши вес числом, например 74.")
        return
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        user.weight = weight
        await session.commit()
    await state.clear()
    await message.answer("Какая у тебя обычная активность?", reply_markup=activity_keyboard())


@router.callback_query(F.data.startswith("onboarding:activity:"))
async def onboarding_activity(callback: CallbackQuery) -> None:
    activity = callback.data.rsplit(":", 1)[1]
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        user.activity = activity
        await session.commit()
    await callback.message.edit_text("Какая сейчас цель?", reply_markup=goal_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("onboarding:goal:"))
async def onboarding_goal(callback: CallbackQuery) -> None:
    goal = callback.data.rsplit(":", 1)[1]
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        user.goal = goal
        user.daily_kcal_target = calculate_daily_kcal_target(user)
        apply_default_macro_targets(user)
        user.onboarding_completed = True
        target = user.daily_kcal_target
        await session.commit()
    await callback.message.edit_text(f"Предлагаю ориентир: {target} ккал в день.")
    await callback.message.answer("Готово. Можно вести дневник.", reply_markup=main_menu())
    await callback.answer()


@router.message(F.text == "⚙️ Настройки")
async def settings(message: Message) -> None:
    text = await _settings_view(message.from_user.id, message.from_user.username)
    await message.answer(text, reply_markup=settings_keyboard())


@router.callback_query(F.data == "settings:open")
async def settings_inline(callback: CallbackQuery) -> None:
    text = await _settings_view(callback.from_user.id, callback.from_user.username)
    await callback.message.edit_text(text, reply_markup=settings_keyboard())
    await callback.answer()


async def _settings_view(telegram_id: int, username: str | None) -> str:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id,
            username,
        )
        return profile_summary(user)


@router.callback_query(F.data == "settings:export")
async def export_data(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        export = ExportService(session)
        food_csv = await export.food_csv(user)
        wellness_csv = await export.wellness_csv(user)

    await callback.message.answer_document(
        BufferedInputFile(food_csv.encode("utf-8"), filename="kcal_food.csv"),
        caption="Еда: все записи дневника.",
    )
    await callback.message.answer_document(
        BufferedInputFile(wellness_csv.encode("utf-8"), filename="kcal_wellness.csv"),
        caption="Вода, вес и активность.",
    )
    await callback.answer("Экспорт готов.")


@router.callback_query(F.data == "settings:apple-health")
async def apple_health_shortcut(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user_service = UserService(session)
        user = await user_service.get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        token = await user_service.ensure_apple_health_token(user)

    endpoint = f"{app_settings.public_api_url.rstrip('/')}/integrations/apple-health/{token}"
    text = _apple_health_shortcut_text(endpoint)
    await callback.message.edit_text(text, reply_markup=settings_keyboard())
    await callback.answer()


@router.callback_query(F.data == "settings:language")
async def settings_language(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Выбери язык.", reply_markup=language_keyboard("settings"))
    await callback.answer()


@router.callback_query(F.data.startswith("settings:language:"))
async def settings_language_save(callback: CallbackQuery) -> None:
    await _save_profile_value(
        callback,
        "language",
        callback.data.rsplit(":", 1)[1],
        recalculate=False,
    )


@router.callback_query(F.data == "settings:gender")
async def settings_gender(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Пол?", reply_markup=gender_keyboard("settings"))
    await callback.answer()


@router.callback_query(F.data.startswith("settings:gender:"))
async def settings_gender_save(callback: CallbackQuery) -> None:
    await _save_profile_value(callback, "gender", callback.data.rsplit(":", 1)[1])


@router.callback_query(F.data == "settings:activity")
async def settings_activity(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Активность?", reply_markup=activity_keyboard("settings"))
    await callback.answer()


@router.callback_query(F.data.startswith("settings:activity:"))
async def settings_activity_save(callback: CallbackQuery) -> None:
    await _save_profile_value(callback, "activity", callback.data.rsplit(":", 1)[1])


@router.callback_query(F.data == "settings:goal")
async def settings_goal(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Цель?", reply_markup=goal_keyboard("settings"))
    await callback.answer()


@router.callback_query(F.data.startswith("settings:goal:"))
async def settings_goal_save(callback: CallbackQuery) -> None:
    await _save_profile_value(callback, "goal", callback.data.rsplit(":", 1)[1], recalculate=True)


@router.callback_query(
    F.data.in_(
        {"settings:age", "settings:height", "settings:weight", "settings:kcal", "settings:macros"}
    )
)
async def settings_ask_number(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    await state.update_data(settings_field=field)
    await state.set_state(getattr(SettingsFlow, field))
    labels = {
        "age": "Возраст?",
        "height": "Рост?",
        "weight": "Вес?",
        "kcal": "Сколько ккал в день поставить целью?",
        "macros": "Цель по БЖУ через слэш: 130/70/220",
    }
    await callback.message.edit_text(labels[field])
    await callback.answer()


@router.message(SettingsFlow.age, F.text)
@router.message(SettingsFlow.height, F.text)
@router.message(SettingsFlow.weight, F.text)
@router.message(SettingsFlow.kcal, F.text)
@router.message(SettingsFlow.macros, F.text)
async def settings_save_number(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data["settings_field"]
    value = _parse_settings_value(field, message.text or "")
    if value is None:
        await message.answer("Не похоже на корректное значение. Попробуй ещё раз.")
        return

    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        if field == "macros":
            protein, fat, carbs = value
            user.protein_target_g = protein
            user.fat_target_g = fat
            user.carbs_target_g = carbs
        elif field == "kcal":
            user.daily_kcal_target = int(value)
            apply_default_macro_targets(user)
        else:
            setattr(user, field, value)
            user.daily_kcal_target = calculate_daily_kcal_target(user)
            apply_default_macro_targets(user)
        await session.commit()
        await session.refresh(user)
        text = profile_summary(user)
    await state.clear()
    await message.answer(text, reply_markup=settings_keyboard())


async def _save_profile_value(
    callback: CallbackQuery,
    field: str,
    value: str,
    recalculate: bool = True,
) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        setattr(user, field, value)
        if recalculate:
            user.daily_kcal_target = calculate_daily_kcal_target(user)
            apply_default_macro_targets(user)
        await session.commit()
        await session.refresh(user)
        text = profile_summary(user)
    await callback.message.edit_text(text, reply_markup=settings_keyboard())
    await callback.answer()


def _parse_int(text: str | None, minimum: int, maximum: int) -> int | None:
    if not text:
        return None
    try:
        value = int(text.strip())
    except ValueError:
        return None
    return value if minimum <= value <= maximum else None


def _parse_float(text: str | None, minimum: float, maximum: float) -> float | None:
    if not text:
        return None
    try:
        value = float(text.replace(",", ".").strip())
    except ValueError:
        return None
    return value if minimum <= value <= maximum else None


def _parse_settings_value(field: str, text: str) -> int | float | None:
    if field == "age":
        return _parse_int(text, 10, 100)
    if field == "height":
        return _parse_float(text, 100, 240)
    if field == "weight":
        return _parse_float(text, 30, 250)
    if field == "kcal":
        return _parse_int(text, 1000, 6000)
    if field == "macros":
        return _parse_macros(text)
    return None


def _parse_macros(text: str) -> tuple[float, float, float] | None:
    normalized = text.replace(",", ".").replace(" ", "")
    parts = normalized.split("/")
    if len(parts) != 3:
        return None
    try:
        protein, fat, carbs = (float(part) for part in parts)
    except ValueError:
        return None
    if not (20 <= protein <= 400 and 20 <= fat <= 250 and 20 <= carbs <= 800):
        return None
    return protein, fat, carbs


def _apple_health_shortcut_text(endpoint: str) -> str:
    return "\n".join(
        [
            "Apple Health через Команды iOS",
            "",
            "1. Открой Команды на iPhone.",
            "2. Создай личную автоматизацию, например утром или вечером.",
            "3. Добавь действия «Найти образцы здоровья» для веса, шагов или активной энергии.",
            "4. Добавь «Получить содержимое URL».",
            "5. Method: POST.",
            "6. Request Body: JSON.",
            "7. URL:",
            endpoint,
            "",
            "Пример JSON:",
            '{"weight_kg": 74.5, "steps": 8200, "active_kcal": 340}',
            "",
            "Можно отправлять только часть полей. Для шагов и active_kcal отправляй "
            "накопленное значение за сегодня: бот добавит только разницу с прошлой "
            "синхронизацией, чтобы часовой webhook не задваивал активность.",
        ]
    )
