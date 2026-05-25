from __future__ import annotations

from datetime import date, datetime

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
    onboarding_finish_keyboard,
    onboarding_skip_keyboard,
    onboarding_start_keyboard,
    settings_keyboard,
)
from kcal_tracker.config import settings as app_settings
from kcal_tracker.database import SessionLocal
from kcal_tracker.services.export import ExportService
from kcal_tracker.services.profile import (
    age_from_birth_date,
    apply_default_macro_targets,
    calculate_daily_kcal_target,
    profile_summary,
)
from kcal_tracker.services.users import UserService

router = Router()


class OnboardingFlow(StatesGroup):
    birth_date = State()
    height = State()
    weight = State()


class SettingsFlow(StatesGroup):
    birth_date = State()
    height = State()
    weight = State()
    target_weight = State()
    weight_pace = State()
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
        _onboarding_intro_text(),
        reply_markup=onboarding_start_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "onboarding:start")
async def onboarding_start(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Шаг 1 из 5. Какая цель сейчас главная?",
        reply_markup=goal_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("onboarding:goal:"))
async def onboarding_goal(callback: CallbackQuery) -> None:
    goal = callback.data.rsplit(":", 1)[1]
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        user.goal = goal
        await session.commit()
    await callback.message.edit_text(
        "Шаг 2 из 5. Укажи пол, чтобы я точнее посчитал дневную норму.",
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
    await state.set_state(OnboardingFlow.birth_date)
    await callback.message.edit_text(
        _birth_date_prompt(),
        reply_markup=onboarding_skip_keyboard("onboarding:birth-date:skip"),
    )
    await callback.answer()


@router.message(OnboardingFlow.birth_date, F.text)
async def onboarding_birth_date(message: Message, state: FSMContext) -> None:
    birth_date = _parse_birth_date(message.text)
    if birth_date is None:
        await message.answer(
            "Напиши дату в формате 14.08.1998 или нажми «Пропустить»."
        )
        return
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        user.birth_date = birth_date
        user.age = age_from_birth_date(birth_date)
        await session.commit()
    await state.set_state(OnboardingFlow.height)
    await message.answer(
        "Шаг 4 из 5. Теперь рост в сантиметрах. "
        "Это помогает точнее посчитать норму.",
        reply_markup=onboarding_skip_keyboard("onboarding:height:skip"),
    )


@router.callback_query(F.data == "onboarding:birth-date:skip")
async def onboarding_birth_date_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OnboardingFlow.height)
    await callback.message.edit_text(
        "Ок, можно заполнить позже. "
        "Шаг 4 из 5. Теперь рост в сантиметрах.",
        reply_markup=onboarding_skip_keyboard("onboarding:height:skip"),
    )
    await callback.answer()


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
    await message.answer("Шаг 5 из 5. И текущий вес в кг.")


@router.callback_query(F.data == "onboarding:height:skip")
async def onboarding_height_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OnboardingFlow.weight)
    await callback.message.edit_text(
        "Ок, рост можно добавить позже. Шаг 5 из 5: напиши текущий вес в кг."
    )
    await callback.answer()


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
    await message.answer(
        "Какая у тебя обычная активность?",
        reply_markup=activity_keyboard(),
    )


@router.callback_query(F.data.startswith("onboarding:activity:"))
async def onboarding_activity(callback: CallbackQuery, state: FSMContext) -> None:
    activity = callback.data.rsplit(":", 1)[1]
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        user.activity = activity
        user.daily_kcal_target = calculate_daily_kcal_target(user)
        apply_default_macro_targets(user)
        user.onboarding_completed = True
        target = user.daily_kcal_target
        protein = user.protein_target_g
        fat = user.fat_target_g
        carbs = user.carbs_target_g
        await session.commit()
    await state.clear()
    await callback.message.edit_text(
        _onboarding_finish_text(target, protein=protein, fat=fat, carbs=carbs),
        reply_markup=onboarding_finish_keyboard(),
    )
    await callback.message.answer("Главное меню ниже.", reply_markup=main_menu())
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
    await callback.message.edit_text(
        "Выбери язык.",
        reply_markup=language_keyboard("settings"),
    )
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
    await callback.message.edit_text(
        "Активность?",
        reply_markup=activity_keyboard("settings"),
    )
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
        {
            "settings:age",
            "settings:birth-date",
            "settings:height",
            "settings:weight",
            "settings:target-weight",
            "settings:weight-pace",
            "settings:kcal",
            "settings:macros",
        }
    )
)
async def settings_ask_number(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1].replace("-", "_")
    if field == "age":
        field = "birth_date"
    await state.update_data(settings_field=field)
    await state.set_state(getattr(SettingsFlow, field))
    labels = {
        "birth_date": _birth_date_prompt(),
        "height": "Рост?",
        "weight": "Вес?",
        "target_weight": "Желаемый вес в кг?",
        "weight_pace": "Темп изменения веса в кг за неделю? Например: 0.5",
        "kcal": "Сколько ккал в день поставить целью?",
        "macros": "Цель по БЖУ через слэш: 130/70/220",
    }
    await callback.message.edit_text(labels[field])
    await callback.answer()


@router.message(SettingsFlow.birth_date, F.text)
@router.message(SettingsFlow.height, F.text)
@router.message(SettingsFlow.weight, F.text)
@router.message(SettingsFlow.target_weight, F.text)
@router.message(SettingsFlow.weight_pace, F.text)
@router.message(SettingsFlow.kcal, F.text)
@router.message(SettingsFlow.macros, F.text)
async def settings_save_number(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data["settings_field"]
    value = _parse_settings_value(field, message.text or "")
    if value is None:
        await message.answer(
            "Не похоже на корректное значение. Попробуй ещё раз."
        )
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
        elif field == "birth_date":
            user.birth_date = value
            user.age = age_from_birth_date(value)
            user.daily_kcal_target = calculate_daily_kcal_target(user)
            apply_default_macro_targets(user)
        elif field == "target_weight":
            user.target_weight_kg = float(value)
        elif field == "weight_pace":
            user.weekly_weight_change_kg = float(value)
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


def _parse_birth_date(text: str | None) -> date | None:
    if not text:
        return None
    value = text.strip()
    for date_format in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            birth_date = datetime.strptime(value, date_format).date()
        except ValueError:
            continue
        age = age_from_birth_date(birth_date)
        if 10 <= age <= 100:
            return birth_date
    return None


def _parse_settings_value(
    field: str,
    text: str,
) -> int | float | date | tuple[float, float, float] | None:
    if field == "birth_date":
        return _parse_birth_date(text)
    if field == "height":
        return _parse_float(text, 100, 240)
    if field == "weight":
        return _parse_float(text, 30, 250)
    if field == "target_weight":
        return _parse_float(text, 30, 250)
    if field == "weight_pace":
        return _parse_float(text, 0.1, 1.5)
    if field == "kcal":
        return _parse_int(text, 1000, 6000)
    if field == "macros":
        return _parse_macros(text)
    return None


def _onboarding_intro_text() -> str:
    return "\n".join(
        [
            "Соберу твой личный дневной план калорий и БЖУ.",
            "",
            "В конце покажу цель на день, белки, жиры и углеводы. "
            "Потом можно сразу записать первую еду текстом, фото или штрихкодом.",
            "",
            "5 коротких шагов, меньше минуты.",
        ]
    )


def _birth_date_prompt() -> str:
    return "\n".join(
        [
            "Шаг 3 из 5. Дата рождения?",
            "",
            "Она нужна только для расчёта возраста "
            "и более точной нормы калорий.",
            "Формат: 14.08.1998",
        ]
    )


def _onboarding_finish_text(
    target: int,
    *,
    protein: float | None = None,
    fat: float | None = None,
    carbs: float | None = None,
) -> str:
    macro_line = ""
    if protein is not None and fat is not None and carbs is not None:
        macro_line = f"БЖУ: {protein:.0f}/{fat:.0f}/{carbs:.0f} г."
    return "\n".join(
        line
        for line in [
            f"Готово. Твоя цель на день: {target} ккал.",
            macro_line,
            "",
            "Теперь главный экран будет показывать остаток, прогресс по БЖУ "
            "и следующий полезный шаг.",
            "",
            "Лучше всего начать с первой реальной записи: так дневник сразу станет полезным.",
        ]
        if line
    )


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
