from __future__ import annotations

import asyncio
import logging
import re

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from kcal_tracker.bot.keyboards import (
    MAIN_MENU_TEXTS,
    after_save_keyboard,
    calorie_warning_keyboard,
    food_confirmation_keyboard,
    food_search_results_keyboard,
    frequent_foods_keyboard,
    multi_food_keyboard,
    repeat_yesterday_keyboard,
    smart_after_food_save_keyboard,
    subscription_cta_keyboard,
)
from kcal_tracker.config import settings
from kcal_tracker.database import SessionLocal
from kcal_tracker.schemas import FoodEntryCreate, FoodEstimate, FoodEstimateList
from kcal_tracker.services.ai_audio import AIAudioService
from kcal_tracker.services.ai_food import AIFoodService
from kcal_tracker.services.ai_usage import AILimitReachedError, AIUsageService
from kcal_tracker.services.barcode import BarcodeNotFoundError, BarcodeService, normalize_barcode
from kcal_tracker.services.diary import DiaryService, estimate_from_entry
from kcal_tracker.services.fatsecret import FatSecretService
from kcal_tracker.services.food_insights import enrich_food_payload, food_label
from kcal_tracker.services.food_search import estimate_common_food
from kcal_tracker.services.media import (
    MediaProcessingError,
    convert_audio_to_mp3,
    extract_frame_from_video,
    extract_frames_from_video,
)
from kcal_tracker.services.nutrition import high_calorie_add_warning
from kcal_tracker.services.open_food_facts import OpenFoodFactsService, ProductNotFoundError
from kcal_tracker.services.subscriptions import has_active_subscription
from kcal_tracker.services.users import UserService
from kcal_tracker.services.wellness import WellnessService

router = Router()
logger = logging.getLogger(__name__)

MIN_SEARCH_RELEVANCE = 0.34


class FoodFlow(StatesGroup):
    waiting_manual = State()
    waiting_barcode_photo = State()
    confirming = State()
    editing_weight = State()
    refining = State()


FOOD_INPUT_PROMPT = (
    "Напиши еду текстом, пришли фото блюда или фото/видео со штрихкодом. "
    "Например: «латте и два банана»."
)


@router.message(
    F.text.in_(
        {
            "➕ Еда",
            "✍️ Записать еду",
            "🍔 Добавить еду",
            "✍️ Еда",
            "📷 Фото/штрихкод",
            "📷 Сканировать продукт",
            "📷 Фото",
        }
    )
)
async def ask_food_input(message: Message, state: FSMContext) -> None:
    await state.set_state(FoodFlow.waiting_barcode_photo)
    await message.answer(FOOD_INPUT_PROMPT)


@router.callback_query(F.data == "nav:add-food")
async def ask_manual_food_from_inline(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FoodFlow.waiting_barcode_photo)
    await callback.message.edit_text(FOOD_INPUT_PROMPT)
    await callback.answer()


@router.callback_query(F.data == "nav:photo")
async def ask_barcode_from_inline(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FoodFlow.waiting_barcode_photo)
    await callback.message.edit_text(FOOD_INPUT_PROMPT)
    await callback.answer()


@router.message(FoodFlow.waiting_manual, F.text)
@router.message(FoodFlow.waiting_barcode_photo, F.text)
async def parse_manual_food(message: Message, state: FSMContext) -> None:
    if await _show_history_confirmation(message, state):
        return

    query = " ".join((message.text or "").split())
    free_estimates = await _free_food_estimates(query)
    if len(free_estimates) == 1:
        if _is_confident_single_search_match(query, free_estimates[0]):
            await _show_confirmation(message, state, free_estimates[0], "food_search")
            return
        await _show_search_results(message, state, free_estimates, query=query)
        return
    if len(free_estimates) > 1:
        await _show_search_results(message, state, free_estimates, query=query)
        return

    if not await _can_use_ai(message):
        await message.answer(
            "Не нашёл достаточно похожий продукт в базе. "
            "Попробуй написать точнее, отправить штрихкод или фото. "
            "AI-разбор может понять свободное описание и сразу подготовить запись.",
            reply_markup=subscription_cta_keyboard(),
        )
        return

    estimates = await AIFoodService().parse_text(query)
    await _record_ai_request(message, "manual_text")
    if not estimates.foods:
        await message.answer("Не разобрал еду достаточно уверенно. Попробуй написать чуть проще.")
        return
    await _show_estimates_confirmation(message, state, estimates, "manual")


@router.message(StateFilter(None), F.text, lambda message: _looks_like_quick_food_text(message.text or ""))
async def quick_food_input(message: Message, state: FSMContext) -> None:
    await parse_manual_food(message, state)


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
    waiting_for_barcode = current_state == FoodFlow.waiting_barcode_photo.state

    if waiting_for_barcode:
        if message.video_note:
            await message.answer("Кружочек получил, ищу штрихкод. Это может занять пару секунд.")
        elif message.video:
            await message.answer("Видео получил, ищу штрихкод. Это может занять пару секунд.")

    image_frames = await _download_image_or_video_frames(message)
    if not image_frames:
        await message.answer("Не смог достать кадры из видео. Пришли фото штрихкода крупнее.")
        return

    async with SessionLocal() as session:
        barcode_timeout = 25 if message.video or message.video_note else 8
        barcode = await _decode_barcode_from_frames(image_frames, timeout=barcode_timeout)
        if barcode is not None:
            logger.info("Barcode decoded from incoming media: %s", barcode)
            try:
                product = await OpenFoodFactsService(session).get_product(barcode)
            except ProductNotFoundError:
                await message.answer(
                    f"Штрихкод {barcode} считался, но продукта пока нет в базе. "
                    "Можно добавить его вручную через «➕ Еда»."
                )
                return

            estimate = enrich_food_payload(
                FoodEstimate(
                    name=product.product_name,
                    weight_g=100,
                    kcal=product.kcal_100g or 0,
                    protein=product.protein_100g or 0,
                    fat=product.fat_100g or 0,
                    carbs=product.carbs_100g or 0,
                    confidence=0.9,
                )
            )
            await _show_confirmation(message, state, estimate, "barcode")
            return

    logger.info(
        "Barcode was not decoded from incoming media: user=%s photo=%s video=%s video_note=%s",
        message.from_user.id if message.from_user else None,
        bool(message.photo),
        bool(message.video),
        bool(message.video_note),
    )

    if waiting_for_barcode and not message.photo:
        await message.answer(_barcode_retry_text(message))
        return

    if message.photo:
        if waiting_for_barcode and not await _can_use_ai(message):
            await message.answer(
                "Штрихкод не считался. Попробуй снять ближе и ровнее, "
                "чтобы полоски занимали большую часть кадра. "
                "Premium в такой ситуации может распознать саму еду по фото.",
                reply_markup=subscription_cta_keyboard(),
            )
            return

        await _recognize_food_photo(
            message,
            state,
            image_frames[0],
            text_hint=message.caption,
        )
        return

    await message.answer("Для AI-еды лучше прислать фото. Видео сейчас использую для штрихкодов.")


async def _free_food_estimate(text: str) -> FoodEstimate | None:
    estimates = await _free_food_estimates(text, limit=1)
    return estimates[0] if estimates else None


async def _show_history_confirmation(message: Message, state: FSMContext) -> bool:
    estimate = await _history_food_estimate(
        message.text or "",
        message.from_user.id,
        message.from_user.username,
    )
    if estimate is None:
        return False
    await _show_confirmation(
        message,
        state,
        estimate,
        "history",
        intro="Обычно ты добавляешь это так:",
        query=message.text or "",
    )
    return True


async def _history_food_estimate(
    text: str,
    telegram_id: int,
    username: str | None,
) -> FoodEstimate | None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(telegram_id, username)
        entry = await DiaryService(session).recent_matching_entry(user, text)
    if entry is None:
        return None
    estimate = estimate_from_entry(entry)
    grams = _extract_requested_grams(text)
    if grams is not None and estimate.weight_g:
        estimate = _scale_estimate(estimate, grams / estimate.weight_g)
    estimate.confidence = estimate.confidence or 0.92
    return estimate


async def _free_food_estimates(text: str, *, limit: int = 5) -> list[FoodEstimate]:
    barcode = normalize_barcode(text)
    async with SessionLocal() as session:
        if barcode is not None:
            try:
                product = await OpenFoodFactsService(session).get_product(barcode)
            except ProductNotFoundError:
                return []
            return [
                enrich_food_payload(
                    FoodEstimate(
                        name=product.product_name,
                        weight_g=100,
                        kcal=product.kcal_100g or 0,
                        protein=product.protein_100g or 0,
                        fat=product.fat_100g or 0,
                        carbs=product.carbs_100g or 0,
                        confidence=0.9,
                    )
                )
            ]
        estimate = estimate_common_food(text)
        if estimate is not None:
            return [estimate]
        try:
            estimates = await asyncio.wait_for(
                OpenFoodFactsService(session).search_products(text, limit=limit),
                timeout=settings.food_search_openfoodfacts_timeout_seconds,
            )
        except TimeoutError:
            logger.info("OpenFoodFacts text search timed out query=%r", text)
            estimates = []
        except Exception:
            logger.debug("OpenFoodFacts text search failed", exc_info=True)
            estimates = []
    estimates = _filter_relevant_estimates(text, estimates, limit=limit)
    if estimates:
        return estimates

    try:
        estimates = await asyncio.wait_for(
            FatSecretService().search_products(text, limit=limit),
            timeout=settings.food_search_fatsecret_timeout_seconds,
        )
    except TimeoutError:
        logger.info("FatSecret text search timed out query=%r", text)
        estimates = []
    except Exception:
        logger.debug("FatSecret text search failed", exc_info=True)
        estimates = []
    return _filter_relevant_estimates(text, estimates, limit=limit)


def _looks_like_quick_food_text(text: str) -> bool:
    value = " ".join(text.split())
    if not value or value in MAIN_MENU_TEXTS or value.startswith("/"):
        return False
    if len(value) < 3 or len(value) > 160:
        return False
    lowered = value.casefold()
    if lowered.endswith("?") or lowered.startswith(("как ", "что ", "почему ", "зачем ")):
        return False
    if lowered.startswith(("вода", "воды", "выпил", "выпила", "вес ", "бег ", "тренировка")):
        return False
    if re.search(r"\d", value):
        return bool(re.search(r"[a-zа-яё]", lowered)) or normalize_barcode(value) is not None
    food_words = (
        "завтрак",
        "обед",
        "ужин",
        "перекус",
        "кофе",
        "латте",
        "чай",
        "йогурт",
        "творог",
        "курица",
        "рыба",
        "рис",
        "гречка",
        "суп",
        "салат",
        "омлет",
        "яйца",
        "банан",
        "яблоко",
        "хлеб",
        "сыр",
    )
    return any(word in lowered for word in food_words)


async def _show_search_results(
    message: Message,
    state: FSMContext,
    estimates: list[FoodEstimate],
    *,
    query: str,
) -> None:
    await state.set_state(FoodFlow.confirming)
    estimate_list = FoodEstimateList(foods=estimates)
    await state.update_data(
        search_estimates=estimate_list.model_dump_json(),
        search_query=query,
        source="food_search",
    )
    await message.answer(
        _format_search_results(estimates, query=query),
        reply_markup=food_search_results_keyboard(len(estimates)),
    )


@router.callback_query(F.data.startswith("foodsearch:choose:"))
async def choose_food_search_result(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        index = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Не понял вариант.", show_alert=True)
        return

    data = await state.get_data()
    if "search_estimates" not in data:
        await callback.answer("Поиск уже устарел. Напиши продукт ещё раз.", show_alert=True)
        return
    estimates = FoodEstimateList.model_validate_json(data["search_estimates"])
    if index >= len(estimates.foods):
        await callback.answer("Не нашёл этот вариант.", show_alert=True)
        return

    await state.update_data(estimate=estimates.foods[index].model_dump_json(), source="food_search")
    await callback.message.edit_text(
        _format_estimate_confirmation(estimates.foods[index]),
        reply_markup=food_confirmation_keyboard("food"),
    )
    await callback.answer()


@router.callback_query(F.data == "food:search")
async def retry_confirmation_with_database_search(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    query = str(data.get("search_query") or "").strip()
    if not query:
        await callback.answer("Запрос уже устарел. Напиши продукт ещё раз.", show_alert=True)
        return

    estimates = await _free_food_estimates(query)
    if not estimates:
        await callback.message.edit_text(
            "В базе не нашёл похожий продукт. Можно разобрать через AI или написать точнее.",
            reply_markup=food_search_results_keyboard(0),
        )
        await callback.answer()
        return

    await state.set_state(FoodFlow.confirming)
    estimate_list = FoodEstimateList(foods=estimates)
    await state.update_data(search_estimates=estimate_list.model_dump_json(), source="food_search")
    await callback.message.edit_text(
        _format_search_results(estimates, query=query),
        reply_markup=food_search_results_keyboard(len(estimates)),
    )
    await callback.answer()


@router.callback_query(F.data == "food:ai")
async def retry_confirmation_with_ai(callback: CallbackQuery, state: FSMContext) -> None:
    await parse_search_query_with_ai(callback, state)


@router.callback_query(F.data == "foodsearch:cancel")
async def cancel_food_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Хорошо, ничего не добавляю.")
    await callback.answer()


@router.callback_query(F.data == "foodsearch:ai")
async def parse_search_query_with_ai(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    query = str(data.get("search_query") or "").strip()
    if not query:
        await callback.answer("Поиск уже устарел. Напиши продукт ещё раз.", show_alert=True)
        return
    if not await _ensure_ai_available_for_callback(callback):
        return

    await callback.message.edit_text("Ок, разбираю это через AI.")
    try:
        estimates = await AIFoodService().parse_text(query)
    except Exception:
        logger.exception("AI food search fallback failed")
        await callback.message.answer("AI сейчас не смог разобрать текст. Попробуй чуть проще.")
        await callback.answer()
        return

    await _record_ai_request_for_callback(callback, "manual_text")
    if not estimates.foods:
        await callback.message.answer("AI тоже не разобрал еду уверенно. Попробуй переформулировать.")
        await callback.answer()
        return

    await _show_estimates_confirmation(callback.message, state, estimates, "manual")
    await callback.answer()


def _dedupe_estimates(estimates: list[FoodEstimate], *, limit: int) -> list[FoodEstimate]:
    deduped: list[FoodEstimate] = []
    seen: set[str] = set()
    for estimate in estimates:
        key = f"{estimate.name.casefold()}:{round(estimate.kcal or 0)}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(estimate)
    return deduped[:limit]


def _filter_relevant_estimates(
    query: str,
    estimates: list[FoodEstimate],
    *,
    limit: int,
) -> list[FoodEstimate]:
    scored: list[tuple[float, FoodEstimate]] = []
    for estimate in estimates:
        score = _search_relevance(query, estimate.name)
        if score < MIN_SEARCH_RELEVANCE:
            continue
        confidence = estimate.confidence or 0
        estimate.confidence = max(confidence, min(score, 0.88))
        scored.append((score, estimate))
    scored.sort(key=lambda item: (item[0], item[1].confidence or 0), reverse=True)
    return _dedupe_estimates([estimate for _, estimate in scored], limit=limit)


def _is_confident_single_search_match(query: str, estimate: FoodEstimate) -> bool:
    return _search_relevance(query, estimate.name) >= 0.68 or (estimate.confidence or 0) >= 0.88


def _search_relevance(query: str, name: str) -> float:
    query_tokens = _search_tokens(query)
    name_tokens = _search_tokens(name)
    if not query_tokens or not name_tokens:
        return 0
    exact_overlap = query_tokens & name_tokens
    if exact_overlap:
        return len(exact_overlap) / max(len(query_tokens), 1)

    fuzzy_hits = 0
    for query_token in query_tokens:
        if len(query_token) < 4:
            continue
        if any(query_token in name_token or name_token in query_token for name_token in name_tokens):
            fuzzy_hits += 1
    if fuzzy_hits:
        return fuzzy_hits / max(len(query_tokens), 1) * 0.75
    return 0


def _search_tokens(value: str) -> set[str]:
    normalized = re.sub(r"[^0-9a-zа-яё]+", " ", value.casefold())
    tokens = {token for token in normalized.split() if len(token) >= 3}
    stop_words = {
        "мне",
        "это",
        "или",
        "для",
        "без",
        "со",
        "вкусом",
        "примерно",
        "около",
        "грамм",
        "граммов",
    }
    return tokens - stop_words


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
            f"#{index} {food_label(item.entry)}{weight} — {item.entry.kcal:.0f} ккал "
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
        f"Готово: {food_label(entry)} — {entry.kcal:.0f} ккал.",
        reply_markup=after_save_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "foodmulti:all")
async def confirm_all_foods(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    estimates = FoodEstimateList.model_validate_json(data["estimates"])
    source = data["source"]
    added_indices = set(data.get("added_indices", []))

    warning = await _multi_food_warning(
        callback.from_user.id,
        callback.from_user.username,
        estimates,
        added_indices,
    )
    if warning:
        await callback.message.edit_text(
            warning,
            reply_markup=calorie_warning_keyboard("foodmulti:all-anyway"),
        )
        await callback.answer()
        return

    await _add_all_foods(callback, state, estimates, source, added_indices)


@router.callback_query(F.data == "foodmulti:all-anyway")
async def confirm_all_foods_anyway(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    estimates = FoodEstimateList.model_validate_json(data["estimates"])
    source = data["source"]
    added_indices = set(data.get("added_indices", []))
    await _add_all_foods(callback, state, estimates, source, added_indices)


async def _add_all_foods(
    callback: CallbackQuery,
    state: FSMContext,
    estimates: FoodEstimateList,
    source: str,
    added_indices: set[int],
) -> None:
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

    warning = await _food_warning(callback.from_user.id, callback.from_user.username, estimate)
    if warning:
        await callback.message.edit_text(
            warning,
            reply_markup=calorie_warning_keyboard(f"foodmulti:add-anyway:{index}"),
        )
        await callback.answer()
        return

    await _add_one_food(callback, state, index, estimate, data["source"], estimates, added_indices)


@router.callback_query(F.data.startswith("foodmulti:add-anyway:"))
async def confirm_one_food_anyway(callback: CallbackQuery, state: FSMContext) -> None:
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
    await _add_one_food(
        callback,
        state,
        index,
        estimates.foods[index],
        data["source"],
        estimates,
        added_indices,
    )


async def _add_one_food(
    callback: CallbackQuery,
    state: FSMContext,
    index: int,
    estimate: FoodEstimate,
    source: str,
    estimates: FoodEstimateList,
    added_indices: set[int],
) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        await DiaryService(session).add_entry(
            user,
            FoodEntryCreate(**estimate.model_dump(), source=source),
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

    warning = await _food_warning(callback.from_user.id, callback.from_user.username, estimate)
    if warning:
        await callback.message.edit_text(
            warning,
            reply_markup=calorie_warning_keyboard("food:confirm-anyway"),
        )
        await callback.answer()
        return

    await _add_confirmed_food(callback, state, estimate, source)


@router.callback_query(F.data == "food:confirm-anyway")
async def confirm_food_anyway(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    estimate = FoodEstimate.model_validate_json(data["estimate"])
    await _add_confirmed_food(callback, state, estimate, data["source"])


async def _add_confirmed_food(
    callback: CallbackQuery,
    state: FSMContext,
    estimate: FoodEstimate,
    source: str,
) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        diary = DiaryService(session)
        entry = await diary.add_entry(
            user,
            FoodEntryCreate(**estimate.model_dump(), source=source),
        )
        summary = await diary.today_summary(user)
        water_ml = await WellnessService(session).today_water_ml(user)

    await state.clear()
    await callback.message.edit_text(
        _format_saved_food(estimate),
        reply_markup=smart_after_food_save_keyboard(
            entry_id=entry.id,
            kcal_left=summary.target_kcal - summary.kcal,
            protein_left=summary.target_protein - summary.protein,
            water_ml=water_ml,
        ),
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


@router.callback_query(F.data.startswith("food:portion:"))
async def update_food_portion(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("source") != "ai_photo" or "estimate" not in data:
        await callback.answer("Быстрые порции доступны только для фото.", show_alert=True)
        return

    try:
        ratio = float(callback.data.rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Не понял порцию.", show_alert=True)
        return

    base_json = data.get("base_estimate") or data["estimate"]
    estimate = _scale_estimate(FoodEstimate.model_validate_json(base_json), ratio)
    await state.update_data(estimate=estimate.model_dump_json())
    await callback.message.edit_text(
        _format_estimate_confirmation(estimate, show_portion_hint=True),
        reply_markup=food_confirmation_keyboard(
            "food",
            allow_refine=True,
            allow_portions=True,
            allow_photo_questions=True,
        ),
    )
    await callback.answer(f"Порция: {ratio:g}×")


@router.callback_query(F.data.startswith("food:ask:"))
async def ask_photo_detail(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("source") != "ai_photo" or "estimate" not in data:
        await callback.answer("Вопросы доступны только для фото.", show_alert=True)
        return

    detail = callback.data.rsplit(":", 1)[1]
    prompts = {
        "sauce": (
            "Опиши соус, масло, сыр или сахар. Например: "
            "«примерно 20 г майонеза» или «жарилось на масле»."
        ),
        "drink": (
            "Опиши напиток рядом с едой. Например: "
            "«латте 300 мл» или «кола 0.5 без сахара»."
        ),
    }
    await state.set_state(FoodFlow.refining)
    await callback.message.edit_text(prompts.get(detail, "Что уточнить для AI?"))
    await callback.answer()


@router.callback_query(F.data == "food:refine")
async def refine_food(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("source") not in {"ai_photo", "manual"} or "estimate" not in data:
        await callback.answer("Уточнение доступно только для AI-оценки.", show_alert=True)
        return

    await state.set_state(FoodFlow.refining)
    await callback.message.edit_text(
        "Что уточнить для AI? Например: «ещё полито джемом» или «это половина порции»."
    )
    await callback.answer()


@router.message(FoodFlow.refining, F.text)
async def update_food_refinement(message: Message, state: FSMContext) -> None:
    refinement = " ".join((message.text or "").split())
    if not refinement:
        await message.answer("Напиши уточнение текстом, например: ещё 20 г джема.")
        return
    if not await _ensure_ai_available(message):
        return

    data = await state.get_data()
    estimate = FoodEstimate.model_validate_json(data["estimate"])
    await message.answer("Уточняю оценку с учётом комментария.")
    try:
        refined = await AIFoodService().refine_estimate(estimate, refinement)
    except Exception:
        logger.exception("AI food refinement failed")
        await message.answer("Не смог сейчас уточнить оценку. Попробуй ещё раз чуть проще.")
        return

    await _record_ai_request(message, "food_refine")
    if not refined.foods:
        await message.answer("AI не смог уверенно уточнить оценку. Попробуй переформулировать.")
        return

    await state.update_data(base_estimate=refined.foods[0].model_dump_json())
    await _show_confirmation(message, state, refined.foods[0], data["source"])


async def _show_confirmation(
    message: Message,
    state: FSMContext,
    estimate: FoodEstimate,
    source: str,
    *,
    intro: str = "Я нашёл:",
    query: str | None = None,
) -> None:
    await state.set_state(FoodFlow.confirming)
    data = await state.get_data()
    update = {"estimate": estimate.model_dump_json(), "source": source}
    if query:
        update["search_query"] = " ".join(query.split())
    if source == "ai_photo" and "base_estimate" not in data:
        update["base_estimate"] = estimate.model_dump_json()
    await state.update_data(**update)
    await message.answer(
        _format_estimate_confirmation(
            estimate,
            show_portion_hint=source == "ai_photo",
            intro=intro,
        ),
        reply_markup=food_confirmation_keyboard(
            "food",
            allow_refine=source in {"ai_photo", "manual"},
            allow_portions=source == "ai_photo",
            allow_photo_questions=source == "ai_photo",
            allow_ai_retry=source in {"history", "food_search"},
            allow_database_retry=source == "history",
        ),
    )


async def _recognize_food_photo(
    message: Message,
    state: FSMContext,
    image_bytes: bytes,
    text_hint: str | None = None,
) -> None:
    if not await _ensure_ai_available(message):
        return

    await message.answer(
        "Фото получил, распознаю еду. Обычно это занимает несколько секунд."
    )
    try:
        estimates = await AIFoodService().recognize_photo(image_bytes, text_hint=text_hint)
    except Exception:
        logger.exception("AI photo recognition failed")
        await message.answer(
            "Не смог сейчас распознать фото. "
            "Попробуй отправить его ещё раз или напиши еду текстом."
        )
        return

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
                        "Пробные AI-распознавания закончились. "
                        "Premium откроет фото, голос, уточнения еды и умные подсказки дня.",
                        reply_markup=subscription_cta_keyboard(),
                    )
                else:
                    await message.answer(
                        "AI на сегодня закончился. Штрихкоды и ручной ввод всё ещё работают."
                    )
                return False
            return True

        try:
            await usage_service.ensure_allowed(user, request_count=request_count)
        except AILimitReachedError:
            await message.answer("AI на сегодня закончился. Штрихкоды и ручной ввод всё ещё работают.")
            return False
    return True


async def _ensure_ai_available_for_callback(
    callback: CallbackQuery,
    request_count: int = 1,
) -> bool:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        usage_service = AIUsageService(session)
        try:
            if has_active_subscription(user):
                await usage_service.ensure_allowed(user, request_count=request_count)
            else:
                await usage_service.ensure_trial_allowed(user, request_count=request_count)
        except AILimitReachedError:
            await callback.message.answer(
                "AI-разбор сейчас недоступен. Можно выбрать вариант из базы, "
                "написать точнее или оформить Premium.",
                reply_markup=subscription_cta_keyboard(),
            )
            await callback.answer("AI недоступен", show_alert=True)
            return False
    return True


async def _can_use_ai(message: Message, request_count: int = 1) -> bool:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        usage_service = AIUsageService(session)
        try:
            if has_active_subscription(user):
                await usage_service.ensure_allowed(user, request_count=request_count)
            else:
                await usage_service.ensure_trial_allowed(user, request_count=request_count)
        except AILimitReachedError:
            return False
    return True


async def _record_ai_request(message: Message, request_type: str) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        await AIUsageService(session).record_request(user, request_type)


async def _record_ai_request_for_callback(callback: CallbackQuery, request_type: str) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
        )
        await AIUsageService(session).record_request(user, request_type)


async def _food_warning(
    telegram_id: int,
    username: str | None,
    estimate: FoodEstimate,
) -> str | None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=telegram_id,
            username=username,
        )
        summary = await DiaryService(session).today_summary(user)
    return high_calorie_add_warning(summary, estimate)


async def _multi_food_warning(
    telegram_id: int,
    username: str | None,
    estimates: FoodEstimateList,
    added_indices: set[int],
) -> str | None:
    pending = [
        estimate
        for index, estimate in enumerate(estimates.foods)
        if index not in added_indices
    ]
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=telegram_id,
            username=username,
        )
        summary = await DiaryService(session).today_summary(user)

    for estimate in pending:
        warning = high_calorie_add_warning(summary, estimate)
        if warning:
            return warning.replace("Точно добавить?", "Точно добавить эти позиции?")

    pending_kcal = sum(estimate.kcal for estimate in pending)
    if pending_kcal and summary.kcal + pending_kcal > summary.target_kcal:
        return (
            "Если добавить всё, день выйдет примерно на "
            f"{summary.kcal + pending_kcal:.0f} ккал при цели {summary.target_kcal}. "
            "Точно добавить все позиции?"
        )
    return None


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


async def _decode_barcode_from_frames(frames: list[bytes], *, timeout: int = 25) -> str | None:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_decode_barcode_from_frames_sync, frames),
            timeout=timeout,
        )
    except TimeoutError:
        logger.warning("Barcode decoding timed out")
        return None
    except Exception:
        logger.exception("Barcode decoding failed")
        return None


def _decode_barcode_from_frames_sync(frames: list[bytes]) -> str | None:
    barcode_service = BarcodeService()
    for frame in frames:
        try:
            return barcode_service.decode_image(frame)
        except BarcodeNotFoundError:
            continue
    return None


def _barcode_retry_text(message: Message) -> str:
    if message.video_note:
        return (
            "Штрихкод из кружочка не считался. Лучше пришли обычное фото штрихкода "
            "крупно, ровно и без движения."
        )
    return (
        "Штрихкод не считался. Попробуй фото ближе, без бликов и под прямым углом "
        "или отправь цифры под штрихкодом."
    )


def _format_estimate_confirmation(
    estimate: FoodEstimate,
    *,
    show_portion_hint: bool = False,
    intro: str = "Я нашёл:",
) -> str:
    lines = [
        intro,
        "",
        f"{food_label(estimate)} — {estimate.weight_g or 0:.0f}г",
        f"🔥 {estimate.kcal:.0f} ккал",
        f"Б {estimate.protein:.0f} / Ж {estimate.fat:.0f} / У {estimate.carbs:.0f} г",
    ]
    if estimate.advice:
        lines.extend(["", f"💡 {estimate.advice}"])
    if estimate.confidence is not None and estimate.confidence < 0.7:
        lines.extend(["", "Оценка примерная, проверь граммовку перед сохранением."])
    if show_portion_hint:
        lines.extend(
            [
                "",
                "Проверь фото-вопросы: вся ли это порция, было ли масло/соус, "
                "сыр, сахар или напиток рядом. Если да — уточни перед сохранением.",
            ]
        )
    lines.extend(["", "Добавить в дневник?"])
    return "\n".join(lines)


def _format_search_results(estimates: list[FoodEstimate], *, query: str) -> str:
    lines = [
        f"По запросу «{query}» нашёл варианты в базе.",
        "Выбери только если продукт действительно похож:",
        "",
    ]
    for index, estimate in enumerate(estimates, start=1):
        lines.append(
            f"#{index} {food_label(estimate)} — {estimate.weight_g or 100:.0f}г, "
            f"{estimate.kcal:.0f} ккал"
        )
        lines.append(
            f"   Б {estimate.protein:.0f} / Ж {estimate.fat:.0f} / У {estimate.carbs:.0f} г"
        )
    lines.extend(["", "Если ничего не подходит, нажми AI-разбор или напиши точнее."])
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
            f"{marker}{index} {food_label(estimate)}{weight} — {estimate.kcal:.0f} ккал, "
            f"Б {estimate.protein:.0f} / Ж {estimate.fat:.0f} / У {estimate.carbs:.0f}"
        )
        if estimate.advice:
            lines.append(f"   💡 {estimate.advice}")
    lines.extend(["", "Добавь нужные позиции или всё сразу."])
    return "\n".join(lines)


def _format_saved_food(estimate: FoodEstimate) -> str:
    lines = [f"Добавил: {food_label(estimate)} — {estimate.kcal:.0f} ккал."]
    if estimate.advice:
        lines.append(f"💡 {estimate.advice}")
    return "\n".join(lines)


def _parse_positive_float(value: str) -> float | None:
    try:
        parsed = float(value.replace(",", ".").strip())
    except ValueError:
        return None
    if parsed <= 0 or parsed > 10000:
        return None
    return parsed


def _extract_requested_grams(value: str) -> float | None:
    match = re.search(r"(\d+(?:[,.]\d+)?)\s*(?:г|гр|грамм|граммов)\b", value.casefold())
    if not match:
        return None
    try:
        grams = float(match.group(1).replace(",", "."))
    except ValueError:
        return None
    if grams <= 0 or grams > 10000:
        return None
    return grams


def _scale_estimate(estimate: FoodEstimate, ratio: float) -> FoodEstimate:
    ratio = max(0.05, min(ratio, 10))
    if estimate.weight_g is not None:
        estimate.weight_g = round(estimate.weight_g * ratio, 1)
    estimate.kcal = round(estimate.kcal * ratio, 1)
    estimate.protein = round(estimate.protein * ratio, 1)
    estimate.fat = round(estimate.fat * ratio, 1)
    estimate.carbs = round(estimate.carbs * ratio, 1)
    if estimate.advice:
        estimate.advice = estimate.advice[:255]
    return estimate
