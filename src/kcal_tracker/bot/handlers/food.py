from __future__ import annotations

import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from kcal_tracker.bot.keyboards import (
    after_save_keyboard,
    confirm_food_keyboard,
    frequent_foods_keyboard,
    multi_food_keyboard,
    repeat_yesterday_keyboard,
)
from kcal_tracker.database import SessionLocal
from kcal_tracker.schemas import FoodEntryCreate, FoodEstimate, FoodEstimateList
from kcal_tracker.services.ai_audio import AIAudioService
from kcal_tracker.services.ai_food import AIFoodService
from kcal_tracker.services.ai_usage import AILimitReachedError, AIUsageService
from kcal_tracker.services.barcode import BarcodeNotFoundError, BarcodeService
from kcal_tracker.services.diary import DiaryService
from kcal_tracker.services.media import (
    MediaProcessingError,
    convert_audio_to_mp3,
    extract_frame_from_video,
    extract_frames_from_video,
)
from kcal_tracker.services.open_food_facts import OpenFoodFactsService, ProductNotFoundError
from kcal_tracker.services.subscriptions import has_active_subscription
from kcal_tracker.services.users import UserService

router = Router()


class FoodFlow(StatesGroup):
    waiting_manual = State()
    waiting_barcode_photo = State()
    confirming = State()
    editing_weight = State()


@router.message(F.text.in_({"✍️ Записать еду", "🍔 Добавить еду", "✍️ Еда"}))
async def ask_manual_food(message: Message, state: FSMContext) -> None:
    await state.set_state(FoodFlow.waiting_manual)
    await message.answer("Напиши, что было в приёме пищи. Например: «латте и два банана».")


@router.callback_query(F.data == "nav:add-food")
async def ask_manual_food_from_inline(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FoodFlow.waiting_manual)
    await callback.message.edit_text(
        "Напиши, что было в приёме пищи. Например: «латте и два банана»."
    )
    await callback.answer()


@router.message(F.text.in_({"📷 Фото/штрихкод", "📷 Сканировать продукт", "📷 Фото"}))
async def ask_barcode(message: Message, state: FSMContext) -> None:
    await state.set_state(FoodFlow.waiting_barcode_photo)
    await message.answer(
        "Пришли фото блюда для AI или фото/видео со штрихкодом. "
        "Если это штрихкод, постарайся держать его крупно и ровно."
    )


@router.callback_query(F.data == "nav:photo")
async def ask_barcode_from_inline(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FoodFlow.waiting_barcode_photo)
    await callback.message.edit_text(
        "Пришли фото блюда для AI или фото/видео со штрихкодом. "
        "Если это штрихкод, постарайся держать его крупно и ровно."
    )
    await callback.answer()


@router.message(FoodFlow.waiting_manual, F.text)
async def parse_manual_food(message: Message, state: FSMContext) -> None:
    if not await _ensure_ai_available(message):
        return

    estimates = await AIFoodService().parse_text(message.text or "")
    await _record_ai_request(message, "manual_text")
    if not estimates.foods:
        await message.answer("Не разобрал еду достаточно уверенно. Попробуй написать чуть проще.")
        return
    await _show_estimates_confirmation(message, state, estimates, "manual")


@router.message(F.voice)
async def handle_voice(message: Message, state: FSMContext) -> None:
    if not await _ensure_ai_available(message, request_count=2):
        return

    file = await message.bot.get_file(message.voice.file_id)
    audio_io = await message.bot.download_file(file.file_path)
    try:
        audio_bytes = await asyncio.to_thread(convert_audio_to_mp3, audio_io.read())
    except MediaProcessingError:
        await message.answer("Не получилось разобрать голосовое. Попробуй ещё раз, чуть короче.")
        return

    transcript = await AIAudioService().transcribe(audio_bytes)
    await _record_ai_request(message, "voice_transcribe")
    if not transcript:
        await message.answer("Не расслышал голос. Попробуй сказать короче и ближе к микрофону.")
        return

    estimates = await AIFoodService().parse_text(transcript)
    await _record_ai_request(message, "voice_parse")
    if not estimates.foods:
        await message.answer("Не разобрал еду достаточно уверенно. Попробуй сказать проще.")
        return

    await message.answer(f"Я услышал: {transcript}")
    await _show_estimates_confirmation(message, state, estimates, "manual")


@router.message(F.photo | F.video | F.video_note)
async def handle_photo(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()

    if current_state == FoodFlow.waiting_barcode_photo.state:
        image_frames = await _download_image_or_video_frames(message)
        if not image_frames:
            await message.answer("Не смог достать кадры из видео. Пришли фото штрихкода крупнее.")
            return

        async with SessionLocal() as session:
            barcode = await _decode_barcode_from_frames(image_frames)
            if barcode is None:
                if message.photo:
                    await _recognize_food_photo(message, state, image_frames[0])
                    return
                await message.answer(
                    "Штрихкод не считался. Попробуй фото ближе, без бликов и под прямым углом."
                )
                return
            try:
                product = await OpenFoodFactsService(session).get_product(barcode)
            except ProductNotFoundError:
                await message.answer(
                    "Штрихкод считался, но продукта пока нет в базе. "
                    "Можно добавить его вручную через «✍️ Записать еду»."
                )
                return

        estimate = FoodEstimate(
            name=product.product_name,
            weight_g=100,
            kcal=product.kcal_100g or 0,
            protein=product.protein_100g or 0,
            fat=product.fat_100g or 0,
            carbs=product.carbs_100g or 0,
            confidence=0.9,
        )
        await _show_confirmation(message, state, estimate, "barcode")
        return

    image_bytes = await _download_image_or_video_frame(message)
    if image_bytes is None:
        await message.answer(
            "Для AI-еды лучше прислать фото. Видео сейчас использую для штрихкодов."
        )
        return

    await _recognize_food_photo(message, state, image_bytes)


@router.message(F.text.in_({"⚡ Частое", "⭐ Частые продукты"}))
async def show_frequent_foods(message: Message) -> None:
    text, reply_markup = await _frequent_foods_view(
        message.from_user.id,
        message.from_user.username,
    )
    await message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "nav:frequent")
async def show_frequent_foods_inline(callback: CallbackQuery) -> None:
    text, reply_markup = await _frequent_foods_view(
        callback.from_user.id,
        callback.from_user.username,
    )
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


async def _frequent_foods_view(telegram_id: int, username: str | None):
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=telegram_id,
            username=username,
        )
        frequent = await DiaryService(session).frequent_foods(user)

    if not frequent:
        return (
            "Пока мало повторов. Когда появятся привычные продукты, соберу их здесь.",
            None,
        )

    lines = ["Частое:", ""]
    for index, item in enumerate(frequent, start=1):
        weight = f", {item.entry.weight_g:.0f}г" if item.entry.weight_g else ""
        lines.append(
            f"#{index} {item.entry.food_name}{weight} — {item.entry.kcal:.0f} ккал "
            f"({item.count} раза)"
        )
    entry_ids = [item.entry.id for item in frequent]
    return "\n".join(lines), frequent_foods_keyboard(entry_ids)


@router.message(F.text.in_({"↩️ Как вчера", "↩️ Повторить вчера"}))
async def ask_repeat_yesterday(message: Message) -> None:
    text, reply_markup = await _repeat_yesterday_view(
        message.from_user.id,
        message.from_user.username,
    )
    await message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "nav:yesterday")
async def ask_repeat_yesterday_inline(callback: CallbackQuery) -> None:
    text, reply_markup = await _repeat_yesterday_view(
        callback.from_user.id,
        callback.from_user.username,
    )
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


async def _repeat_yesterday_view(telegram_id: int, username: str | None):
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=telegram_id,
            username=username,
        )
        entries = await DiaryService(session).entries_for_day_offset(user, days_ago=1)

    if not entries:
        return "За вчера пока нечего повторять.", None

    kcal = sum(entry.kcal for entry in entries)
    return (
        f"Добавить вчерашний набор: {len(entries)} записей, {kcal:.0f} ккал?",
        repeat_yesterday_keyboard(),
    )


@router.callback_query(F.data == "food:repeat-yesterday:confirm")
async def repeat_yesterday(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        repeated = await DiaryService(session).repeat_yesterday(user)

    if not repeated:
        await callback.message.edit_text("За вчера пока нечего повторять.")
    else:
        kcal = sum(entry.kcal for entry in repeated)
        await callback.message.edit_text(
            f"Добавил как вчера: {len(repeated)} записей, {kcal:.0f} ккал.",
            reply_markup=after_save_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "food:repeat-yesterday:cancel")
async def cancel_repeat_yesterday(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Хорошо, ничего не добавляю.")
    await callback.answer()


@router.callback_query(F.data.startswith("food:repeat:"))
async def repeat_frequent_food(callback: CallbackQuery) -> None:
    entry_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        entry = await DiaryService(session).repeat_entry(user, entry_id)

    if entry is None:
        await callback.answer("Не нашёл эту запись.", show_alert=True)
        return
    await callback.message.edit_text(
        f"Готово: {entry.food_name} — {entry.kcal:.0f} ккал.",
        reply_markup=after_save_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "foodmulti:all")
async def confirm_all_foods(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    estimates = FoodEstimateList.model_validate_json(data["estimates"])
    source = data["source"]
    added_indices = set(data.get("added_indices", []))

    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        diary = DiaryService(session)
        added_count = 0
        for index, estimate in enumerate(estimates.foods):
            if index in added_indices:
                continue
            await diary.add_entry(user, FoodEntryCreate(**estimate.model_dump(), source=source))
            added_count += 1

    await state.clear()
    total_count = len(added_indices) + added_count
    await callback.message.edit_text(
        f"Добавил в дневник: {total_count} позиций.",
        reply_markup=after_save_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("foodmulti:add:"))
async def confirm_one_food(callback: CallbackQuery, state: FSMContext) -> None:
    index = int(callback.data.rsplit(":", 1)[1])
    data = await state.get_data()
    estimates = FoodEstimateList.model_validate_json(data["estimates"])
    added_indices = set(data.get("added_indices", []))
    if index >= len(estimates.foods):
        await callback.answer("Не нашёл позицию.", show_alert=True)
        return
    if index in added_indices:
        await callback.answer("Эта позиция уже добавлена.", show_alert=True)
        return
    estimate = estimates.foods[index]

    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        await DiaryService(session).add_entry(
            user,
            FoodEntryCreate(**estimate.model_dump(), source=data["source"]),
        )

    added_indices.add(index)
    if len(added_indices) == len(estimates.foods):
        await state.clear()
        await callback.message.edit_text(
            f"Готово, добавил все позиции: {len(estimates.foods)}.",
            reply_markup=after_save_keyboard(),
        )
        await callback.answer()
        return

    await state.update_data(added_indices=sorted(added_indices))
    await callback.message.edit_text(
        _format_multi_foods(estimates, added_indices),
        reply_markup=multi_food_keyboard(len(estimates.foods), added_indices),
    )
    await callback.answer()


@router.callback_query(F.data == "foodmulti:noop")
async def already_added_food(callback: CallbackQuery) -> None:
    await callback.answer("Уже добавлено.")


@router.callback_query(F.data == "foodmulti:done")
async def finish_multi_food(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    added_count = len(data.get("added_indices", []))
    await state.clear()
    await callback.message.edit_text(
        f"Готово. Добавлено позиций: {added_count}.",
        reply_markup=after_save_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "foodmulti:cancel")
async def cancel_multi_food(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Хорошо, ничего не добавляю.")
    await callback.answer()


@router.callback_query(F.data == "food:confirm")
async def confirm_food(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    estimate = FoodEstimate.model_validate_json(data["estimate"])
    source = data["source"]

    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        await DiaryService(session).add_entry(
            user,
            FoodEntryCreate(**estimate.model_dump(), source=source),
        )

    await state.clear()
    await callback.message.edit_text(
        f"Добавил: {estimate.name} — {estimate.kcal:.0f} ккал.",
        reply_markup=after_save_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "food:cancel")
async def cancel_food(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Хорошо, ничего не добавляю.")
    await callback.answer()


@router.callback_query(F.data == "food:edit")
async def edit_food(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FoodFlow.editing_weight)
    await callback.message.edit_text("Напиши новую граммовку числом. Например: 180")
    await callback.answer()


@router.message(FoodFlow.editing_weight, F.text)
async def update_food_weight(message: Message, state: FSMContext) -> None:
    grams = _parse_positive_float(message.text or "")
    if grams is None:
        await message.answer("Нужна граммовка числом, например 180.")
        return

    data = await state.get_data()
    estimate = FoodEstimate.model_validate_json(data["estimate"])
    old_grams = estimate.weight_g or 0
    if old_grams > 0:
        ratio = grams / old_grams
        estimate.kcal = round(estimate.kcal * ratio, 1)
        estimate.protein = round(estimate.protein * ratio, 1)
        estimate.fat = round(estimate.fat * ratio, 1)
        estimate.carbs = round(estimate.carbs * ratio, 1)
    estimate.weight_g = grams
    await state.update_data(estimate=estimate.model_dump_json())
    await _show_confirmation(message, state, estimate, data["source"])


async def _show_confirmation(
    message: Message,
    state: FSMContext,
    estimate: FoodEstimate,
    source: str,
) -> None:
    await state.set_state(FoodFlow.confirming)
    await state.update_data(estimate=estimate.model_dump_json(), source=source)
    await message.answer(
        _format_estimate_confirmation(estimate),
        reply_markup=confirm_food_keyboard("food"),
    )


async def _recognize_food_photo(message: Message, state: FSMContext, image_bytes: bytes) -> None:
    if not await _ensure_ai_available(message):
        return

    estimates = await AIFoodService().recognize_photo(image_bytes)
    await _record_ai_request(message, "photo")
    if not estimates.foods or (estimates.foods[0].confidence or 0) < 0.35:
        await message.answer("Не вижу еду достаточно уверенно. Попробуй другое фото или угол.")
        return
    await _show_estimates_confirmation(message, state, estimates, "ai_photo")


async def _show_estimates_confirmation(
    message: Message,
    state: FSMContext,
    estimates: FoodEstimateList,
    source: str,
) -> None:
    if len(estimates.foods) == 1:
        await _show_confirmation(message, state, estimates.foods[0], source)
        return
    await state.set_state(FoodFlow.confirming)
    await state.update_data(
        estimates=estimates.model_dump_json(),
        source=source,
        added_indices=[],
    )
    await message.answer(
        _format_multi_foods(estimates),
        reply_markup=multi_food_keyboard(len(estimates.foods)),
    )


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
                if await usage_service.remaining_trial(user) <= 0:
                    await message.answer(
                        "Бесплатные 3 AI-запроса закончились. "
                        "Подписку можно открыть в разделе «💎 Подписка»."
                    )
                else:
                    await message.answer(
                        "Лимит AI на сегодня закончился. Штрихкоды всё ещё работают."
                    )
                return False
            return True

        try:
            await usage_service.ensure_allowed(user, request_count=request_count)
        except AILimitReachedError:
            await message.answer("Лимит AI на сегодня закончился. Штрихкоды всё ещё работают.")
            return False
    return True


async def _record_ai_request(message: Message, request_type: str) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        await AIUsageService(session).record_request(user, request_type)


async def _download_image_or_video_frame(message: Message) -> bytes | None:
    if message.photo:
        file = await message.bot.get_file(message.photo[-1].file_id)
        image_io = await message.bot.download_file(file.file_path)
        return image_io.read()

    video = message.video or message.video_note
    if video is None:
        return None

    file = await message.bot.get_file(video.file_id)
    video_io = await message.bot.download_file(file.file_path)
    try:
        return await asyncio.to_thread(extract_frame_from_video, video_io.read())
    except MediaProcessingError:
        return None


async def _download_image_or_video_frames(message: Message) -> list[bytes]:
    if message.photo:
        file = await message.bot.get_file(message.photo[-1].file_id)
        image_io = await message.bot.download_file(file.file_path)
        return [image_io.read()]

    video = message.video or message.video_note
    if video is None:
        return []

    file = await message.bot.get_file(video.file_id)
    video_io = await message.bot.download_file(file.file_path)
    try:
        frame_limit = 16 if message.video_note else 10
        return await asyncio.to_thread(extract_frames_from_video, video_io.read(), frame_limit)
    except MediaProcessingError:
        return []


async def _decode_barcode_from_frames(frames: list[bytes]) -> str | None:
    barcode_service = BarcodeService()
    for frame in frames:
        try:
            return await barcode_service.decode_image(frame)
        except BarcodeNotFoundError:
            continue
    return None


def _format_estimate_confirmation(estimate: FoodEstimate) -> str:
    lines = [
        "Я нашёл:",
        "",
        f"{estimate.name} — {estimate.weight_g or 0:.0f}г",
        f"🔥 {estimate.kcal:.0f} ккал",
        f"Б {estimate.protein:.0f} / Ж {estimate.fat:.0f} / У {estimate.carbs:.0f} г",
    ]
    if estimate.confidence is not None and estimate.confidence < 0.7:
        lines.extend(["", "Оценка примерная, проверь граммовку перед сохранением."])
    lines.extend(["", "Добавить в дневник?"])
    return "\n".join(lines)


def _format_multi_foods(
    estimates: FoodEstimateList,
    added_indices: set[int] | None = None,
) -> str:
    added_indices = added_indices or set()
    lines = ["Я нашёл несколько позиций:", ""]
    for index, estimate in enumerate(estimates.foods, start=1):
        marker = "✓" if index - 1 in added_indices else "#"
        weight = f", {estimate.weight_g:.0f}г" if estimate.weight_g else ""
        lines.append(
            f"{marker}{index} {estimate.name}{weight} — {estimate.kcal:.0f} ккал, "
            f"Б {estimate.protein:.0f} / Ж {estimate.fat:.0f} / У {estimate.carbs:.0f}"
        )
    lines.extend(["", "Добавь нужные позиции или всё сразу."])
    return "\n".join(lines)


def _parse_positive_float(value: str) -> float | None:
    try:
        parsed = float(value.replace(",", ".").strip())
    except ValueError:
        return None
    if parsed <= 0 or parsed > 10000:
        return None
    return parsed
