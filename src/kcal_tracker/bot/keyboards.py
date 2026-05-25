from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from kcal_tracker.config import settings

MAIN_MENU_TEXTS = {
    "➕ Еда",
    "📷 Фото/штрихкод",
    "📷 Сканировать продукт",
    "📷 Фото",
    "✍️ Записать еду",
    "🍔 Добавить еду",
    "✍️ Еда",
    "📊 Сегодня",
    "📊 Мой день",
    "🔥 Остаток",
    "🔥 Калории",
    "⚡ Частое",
    "⭐ Частые продукты",
    "↩️ Как вчера",
    "↩️ Повторить вчера",
    "⭐ Любимое",
    "⭐ Избранное",
    "⚡ Шаблоны",
    "📅 Месяц",
    "📈 7 дней",
    "📈 Неделя",
    "💧 Вода",
    "🍽 Что съесть?",
    "🍽 Что съесть",
    "🏃 Активность",
    "⚖️ Вес",
    "⏰ Напомнить",
    "⏰ Напоминания",
    "⚙️ Настройки",
    "💎 Подписка",
    "🆘 Поддержка",
    "☰ Ещё",
    "🏠 Меню",
    "❌ Отмена",
}


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Еда"), KeyboardButton(text="📊 Сегодня")],
            [KeyboardButton(text="💧 Вода"), KeyboardButton(text="☰ Ещё")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напиши еду или пришли фото",
    )


def more_menu_keyboard(
    *,
    has_frequent_foods: bool = True,
    has_yesterday_entries: bool = True,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍽 Что съесть сейчас", callback_data="coach:meal")],
            [
                InlineKeyboardButton(text="🍽 Еда", callback_data="nav:food-tools"),
                InlineKeyboardButton(text="📈 Прогресс", callback_data="nav:progress-tools"),
            ],
            [
                InlineKeyboardButton(text="💧 Тело", callback_data="nav:body-tools"),
                InlineKeyboardButton(text="⚙️ Сервис", callback_data="nav:service-tools"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings:open"),
                InlineKeyboardButton(text="💎 Подписка", callback_data="subscription:open"),
            ],
        ]
    )


def food_tools_keyboard(
    *,
    has_frequent_foods: bool = True,
    has_yesterday_entries: bool = True,
) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="⚡ Шаблоны", callback_data="nav:templates")]]
    if has_frequent_foods:
        rows.insert(0, [InlineKeyboardButton(text="⚡ Частое", callback_data="nav:frequent")])
    if has_yesterday_entries:
        rows.append([InlineKeyboardButton(text="↩️ Как вчера", callback_data="nav:yesterday")])
    rows.append([InlineKeyboardButton(text="➕ Добавить еду", callback_data="nav:add-food")])
    rows.append([InlineKeyboardButton(text="☰ Ещё", callback_data="nav:more")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def progress_tools_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📈 7 дней", callback_data="nav:week"),
                InlineKeyboardButton(text="📅 Месяц", callback_data="nav:month"),
            ],
            [InlineKeyboardButton(text="📊 Сегодня", callback_data="nav:today")],
            [InlineKeyboardButton(text="☰ Ещё", callback_data="nav:more")],
        ]
    )


def body_tools_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💧 Вода", callback_data="nav:water")],
            [
                InlineKeyboardButton(text="🏃 Активность", callback_data="nav:activity"),
                InlineKeyboardButton(text="⚖️ Вес", callback_data="nav:weight"),
            ],
            [InlineKeyboardButton(text="☰ Ещё", callback_data="nav:more")],
        ]
    )


def service_tools_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support:open")],
            [InlineKeyboardButton(text="⏰ Напоминания", callback_data="nav:reminders")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings:open")],
            [InlineKeyboardButton(text="💎 Подписка", callback_data="subscription:open")],
            [InlineKeyboardButton(text="☰ Ещё", callback_data="nav:more")],
        ]
    )


def confirm_food_keyboard(prefix: str, *, allow_refine: bool = False) -> InlineKeyboardMarkup:
    return food_confirmation_keyboard(prefix, allow_refine=allow_refine)


def food_confirmation_keyboard(
    prefix: str,
    *,
    allow_refine: bool = False,
    allow_portions: bool = False,
    allow_photo_questions: bool = False,
    allow_ai_retry: bool = False,
    allow_database_retry: bool = False,
    allow_not_it: bool = True,
) -> InlineKeyboardMarkup:
    edit_row = [InlineKeyboardButton(text="✏️ Граммовка", callback_data=f"{prefix}:edit")]
    if allow_refine:
        edit_row.append(InlineKeyboardButton(text="🔎 Уточнить", callback_data=f"{prefix}:refine"))
    rows = [[InlineKeyboardButton(text="✅ Добавить", callback_data=f"{prefix}:confirm")]]
    if allow_portions:
        rows.append(
            [
                InlineKeyboardButton(text="½", callback_data=f"{prefix}:portion:0.5"),
                InlineKeyboardButton(text="1×", callback_data=f"{prefix}:portion:1"),
                InlineKeyboardButton(text="1½", callback_data=f"{prefix}:portion:1.5"),
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(text="2×", callback_data=f"{prefix}:portion:2"),
                InlineKeyboardButton(text="¼", callback_data=f"{prefix}:portion:0.25"),
            ]
        )
    if allow_photo_questions:
        rows.append(
            [
                InlineKeyboardButton(text="🧈 Соус/масло", callback_data=f"{prefix}:ask:sauce"),
                InlineKeyboardButton(text="🥤 Напиток", callback_data=f"{prefix}:ask:drink"),
            ]
        )
    retry_row = []
    if allow_ai_retry:
        retry_row.append(InlineKeyboardButton(text="✨ AI-разбор", callback_data=f"{prefix}:ai"))
    if allow_database_retry:
        retry_row.append(InlineKeyboardButton(text="🔎 Искать в базе", callback_data=f"{prefix}:search"))
    if retry_row:
        rows.append(retry_row)
    if allow_not_it:
        rows.append([InlineKeyboardButton(text="🙅 Не то", callback_data=f"{prefix}:wrong")])
    rows.append(edit_row)
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"{prefix}:cancel")])
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def food_recovery_keyboard(*, allow_ai: bool = True, allow_database: bool = True) -> InlineKeyboardMarkup:
    rows = []
    if allow_ai:
        rows.append([InlineKeyboardButton(text="✨ AI-разбор", callback_data="food:ai")])
    if allow_database:
        rows.append([InlineKeyboardButton(text="🔎 Искать в базе", callback_data="food:search")])
    rows.append([InlineKeyboardButton(text="✍️ Написать заново", callback_data="nav:add-food")])
    rows.append([InlineKeyboardButton(text="🆘 Поддержка", callback_data="support:open")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def calorie_warning_keyboard(confirm_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, добавить", callback_data=confirm_callback)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="food:cancel")],
        ]
    )


def after_save_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Сегодня", callback_data="nav:today"),
                InlineKeyboardButton(text="➕ Ещё еду", callback_data="nav:add-food"),
            ],
        ]
    )


def smart_after_food_save_keyboard(
    *,
    entry_id: int | None = None,
    kcal_left: float | None = None,
    protein_left: float | None = None,
    water_ml: int | None = None,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="📊 Сегодня", callback_data="nav:today"),
            InlineKeyboardButton(text="➕ Ещё еду", callback_data="nav:add-food"),
        ]
    ]
    smart_row: list[InlineKeyboardButton] = []
    if water_ml is not None and water_ml < 1000:
        smart_row.append(InlineKeyboardButton(text="💧 Вода", callback_data="water:add:250"))
    if kcal_left is not None and (kcal_left <= 350 or (protein_left or 0) >= 25):
        smart_row.append(InlineKeyboardButton(text="🍽 Что съесть?", callback_data="coach:meal"))
    if smart_row:
        rows.append(smart_row[:2])
    if entry_id is not None:
        rows.append([InlineKeyboardButton(text="⭐ В шаблон", callback_data=f"entry:fav:{entry_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def after_water_save_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Сегодня", callback_data="nav:today"),
                InlineKeyboardButton(text="💧 Ещё воды", callback_data="water:custom"),
            ],
        ]
    )


def after_activity_save_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Сегодня", callback_data="nav:today"),
                InlineKeyboardButton(text="🏃 Активность", callback_data="nav:activity"),
            ],
        ]
    )


def weight_dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Записать вес", callback_data="weight:add")],
            [InlineKeyboardButton(text="📈 Неделя", callback_data="nav:week")],
        ]
    )


def frequent_foods_keyboard(entry_ids: list[int]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"➕ #{index}",
                    callback_data=f"food:repeat:{entry_id}",
                )
            ]
            for index, entry_id in enumerate(entry_ids, start=1)
        ]
    )


def repeat_yesterday_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Добавить вчерашнее",
                    callback_data="food:repeat-yesterday:confirm",
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="food:repeat-yesterday:cancel")],
        ]
    )


def food_entries_keyboard(
    entry_ids: list[int],
    *,
    expanded: bool = False,
    mode: str = "today",
) -> InlineKeyboardMarkup:
    if not expanded:
        rows = []
        if mode == "yesterday":
            rows.append(
                [
                    InlineKeyboardButton(text="Сегодня", callback_data="nav:today"),
                    InlineKeyboardButton(text="Картинка дня", callback_data="day:yesterday-card"),
                ]
            )
        elif entry_ids:
            rows.append(
                [
                    InlineKeyboardButton(text="✏️ Редактировать", callback_data="entry:manage"),
                    InlineKeyboardButton(text="🍽 Что съесть?", callback_data="coach:meal"),
                    InlineKeyboardButton(text="← Вчера", callback_data="diary:yesterday"),
                ]
            )
        else:
            rows.append([InlineKeyboardButton(text="➕ Еду", callback_data="nav:add-food")])
        if mode == "today" and not entry_ids:
            rows.append([InlineKeyboardButton(text="← Вчера", callback_data="diary:yesterday")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    rows: list[list[InlineKeyboardButton]] = []
    for index, entry_id in enumerate(entry_ids, start=1):
        rows.append(
            [
                InlineKeyboardButton(text=f"✏️ #{index}", callback_data=f"entry:edit:{entry_id}"),
                InlineKeyboardButton(text=f"🗑 #{index}", callback_data=f"entry:delete:{entry_id}"),
                InlineKeyboardButton(text=f"⭐ #{index}", callback_data=f"entry:fav:{entry_id}"),
                InlineKeyboardButton(text=f"🔎 #{index}", callback_data=f"entry:refine:{entry_id}"),
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="📊 Свернуть", callback_data="nav:today"),
            InlineKeyboardButton(text="🍽 Что съесть?", callback_data="coach:meal"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def activity_menu_keyboard(activity_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="➕ Добавить активность", callback_data="activity:custom")]]
    if activity_ids:
        rows.append(
            [InlineKeyboardButton(text="🗑 Удалить запись", callback_data="activity:manage")]
        )
    rows.append([InlineKeyboardButton(text="📊 Сегодня", callback_data="nav:today")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def activity_logs_keyboard(
    activity_ids: list[int],
    *,
    expanded: bool = False,
) -> InlineKeyboardMarkup:
    if not expanded:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏃 Активность", callback_data="activity:manage")],
                [InlineKeyboardButton(text="📊 Сегодня", callback_data="nav:today")],
            ]
        )

    rows: list[list[InlineKeyboardButton]] = []
    for index, activity_id in enumerate(activity_ids, start=1):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 Активность #{index}",
                    callback_data=f"activity:delete:{activity_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="📊 Сегодня", callback_data="nav:today")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def water_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="+250 мл", callback_data="water:add:250"),
                InlineKeyboardButton(text="+500 мл", callback_data="water:add:500"),
            ],
            [InlineKeyboardButton(text="✍️ Другое количество", callback_data="water:custom")],
        ]
    )


def favorites_keyboard(favorite_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="➕ Добавить шаблон", callback_data="fav:manual")]
    ]
    for index, favorite_id in enumerate(favorite_ids, start=1):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"➕ #{index}",
                    callback_data=f"fav:add:{favorite_id}",
                ),
                InlineKeyboardButton(
                    text=f"🗑 #{index}",
                    callback_data=f"fav:del:{favorite_id}",
                ),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def multi_food_keyboard(count: int, added_indices: set[int] | None = None) -> InlineKeyboardMarkup:
    added_indices = added_indices or set()
    rows = [[InlineKeyboardButton(text="✅ Добавить всё", callback_data="foodmulti:all")]]
    rows.extend(
        [
            InlineKeyboardButton(
                text=f"✓ #{index}" if index - 1 in added_indices else f"➕ #{index}",
                callback_data=(
                    "foodmulti:noop"
                    if index - 1 in added_indices
                    else f"foodmulti:add:{index - 1}"
                ),
            )
        ]
        for index in range(1, count + 1)
    )
    if added_indices:
        rows.append([InlineKeyboardButton(text="✅ Готово", callback_data="foodmulti:done")])
    else:
        rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="foodmulti:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def food_search_results_keyboard(count: int, *, allow_ai: bool = True) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"Выбрать #{index}",
                callback_data=f"foodsearch:choose:{index - 1}",
            )
        ]
        for index in range(1, count + 1)
    ]
    if allow_ai:
        rows.append([InlineKeyboardButton(text="✨ Разобрать через AI", callback_data="foodsearch:ai")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="foodsearch:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reminders_keyboard(user) -> InlineKeyboardMarkup:
    toggle_text = (
        "Выключить все напоминания" if user.reminders_enabled else "Включить напоминания"
    )
    toggle_value = "off" if user.reminders_enabled else "on"
    meal_toggle_text = (
        "Выключить напоминания о еде"
        if user.meal_reminders_enabled
        else "Включить напоминания о еде"
    )
    meal_toggle_value = "off" if user.meal_reminders_enabled else "on"
    weight_toggle_text = (
        "Выключить напоминание о весе"
        if user.weight_reminders_enabled
        else "Включить напоминание о весе"
    )
    weight_toggle_value = "off" if user.weight_reminders_enabled else "on"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=f"reminders:{toggle_value}")],
            [
                InlineKeyboardButton(
                    text=meal_toggle_text,
                    callback_data=f"reminders:meal:{meal_toggle_value}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=weight_toggle_text,
                    callback_data=f"reminders:weight-toggle:{weight_toggle_value}",
                )
            ],
            [
                InlineKeyboardButton(text="Время утром", callback_data="reminders:breakfast"),
                InlineKeyboardButton(text="Время обеда", callback_data="reminders:lunch"),
            ],
            [InlineKeyboardButton(text="Время вечера", callback_data="reminders:dinner")],
            [InlineKeyboardButton(text="Время веса", callback_data="reminders:weight")],
        ]
    )


def language_keyboard(prefix: str = "onboarding") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Русский", callback_data=f"{prefix}:language:ru"),
                InlineKeyboardButton(text="English", callback_data=f"{prefix}:language:en"),
            ]
        ]
    )


def gender_keyboard(prefix: str = "onboarding") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Мужской", callback_data=f"{prefix}:gender:male"),
                InlineKeyboardButton(text="Женский", callback_data=f"{prefix}:gender:female"),
            ]
        ]
    )


def activity_keyboard(prefix: str = "onboarding") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Спокойная", callback_data=f"{prefix}:activity:low")],
            [InlineKeyboardButton(text="Обычная", callback_data=f"{prefix}:activity:medium")],
            [InlineKeyboardButton(text="Активная", callback_data=f"{prefix}:activity:high")],
        ]
    )


def goal_keyboard(prefix: str = "onboarding") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Снизить вес", callback_data=f"{prefix}:goal:loss")],
            [InlineKeyboardButton(text="Держать форму", callback_data=f"{prefix}:goal:maintain")],
            [InlineKeyboardButton(text="Набрать массу", callback_data=f"{prefix}:goal:gain")],
        ]
    )


def onboarding_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Собрать мой план",
                    callback_data="onboarding:start",
                )
            ]
        ]
    )


def onboarding_skip_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Пропустить",
                    callback_data=callback_data,
                )
            ]
        ]
    )


def onboarding_finish_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Добавить первую еду",
                    callback_data="nav:add-food",
                )
            ],
            [InlineKeyboardButton(text="📊 Открыть дневник", callback_data="nav:today")],
        ]
    )


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Язык", callback_data="settings:language")],
            [InlineKeyboardButton(text="Пол", callback_data="settings:gender")],
            [
                InlineKeyboardButton(
                    text="Дата рождения",
                    callback_data="settings:birth-date",
                )
            ],
            [InlineKeyboardButton(text="Рост", callback_data="settings:height")],
            [InlineKeyboardButton(text="Вес", callback_data="settings:weight")],
            [InlineKeyboardButton(text="Активность", callback_data="settings:activity")],
            [InlineKeyboardButton(text="Цель", callback_data="settings:goal")],
            [InlineKeyboardButton(text="Цель по калориям", callback_data="settings:kcal")],
            [InlineKeyboardButton(text="Цель по БЖУ", callback_data="settings:macros")],
            [InlineKeyboardButton(text="Apple Health", callback_data="settings:apple-health")],
            [InlineKeyboardButton(text="Экспорт данных", callback_data="settings:export")],
        ]
    )


def subscription_keyboard(
    *,
    active: bool = False,
    bonuses_available: bool = True,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="Продлить подписку" if active else "Оформить подписку",
                callback_data="subscription:subscribe",
            )
        ],
        [
            InlineKeyboardButton(text="🤝 Пригласить друга", callback_data="subscription:referral"),
            InlineKeyboardButton(
                text="📊 Реферальный кабинет",
                callback_data="subscription:referral-dashboard",
            ),
        ],
    ]
    if bonuses_available:
        rows.append([InlineKeyboardButton(text="🎁 Бонусы", callback_data="subscription:bonuses")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscription_plan_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(
                        f"Старт: умный дневник {settings.ai_subscription_rub} ₽ "
                        f"({settings.ai_basic_daily_request_limit}/день)"
                    ),
                    callback_data="subscription:plan:basic",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Безлимит: максимум AI {settings.ai_unlimited_subscription_rub} ₽",
                    callback_data="subscription:plan:unlimited",
                )
            ],
            [InlineKeyboardButton(text="Назад", callback_data="subscription:open")],
        ]
    )


def subscription_payment_method_keyboard(plan_code: str) -> InlineKeyboardMarkup:
    is_unlimited = plan_code == "unlimited"
    title = "Безлимит" if is_unlimited else "Старт"
    rub = settings.ai_unlimited_subscription_rub if is_unlimited else settings.ai_subscription_rub
    stars = (
        settings.ai_unlimited_subscription_stars if is_unlimited else settings.ai_subscription_stars
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"СБП {rub} ₽",
                    callback_data=f"subscription:yookassa:{plan_code}:sbp",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Карта/SberPay {rub} ₽",
                    callback_data=f"subscription:yookassa:{plan_code}:auto",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Звёзды Telegram {stars} ⭐",
                    callback_data=f"subscription:stars:{plan_code}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Назад к тарифам ({title})",
                    callback_data="subscription:subscribe",
                )
            ],
        ]
    )


def subscription_bonuses_keyboard(
    *,
    trial_available: bool,
    winback_available: bool,
    refund_available: bool,
) -> InlineKeyboardMarkup:
    rows = []
    if trial_available:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🎁 Пробный premium-день",
                    callback_data="subscription:trial",
                )
            ]
        )
    if winback_available:
        rows.append(
            [
                InlineKeyboardButton(
                    text="↩️ Вернуть AI на день",
                    callback_data="subscription:winback",
                )
            ]
        )
    if refund_available:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Возврат оплаты за 24 часа",
                    callback_data="subscription:refund",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Назад", callback_data="subscription:open")])
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def subscription_cta_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Посмотреть возможности Premium", callback_data="subscription:open")]
        ]
    )


def progress_share_keyboard(
    share_url: str,
    *,
    missions_bonus_available: bool = False,
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Поделиться прогрессом", url=share_url)],
        [InlineKeyboardButton(text="Картинка недели", callback_data="week:share-card")],
    ]
    if missions_bonus_available:
        rows.append(
            [InlineKeyboardButton(text="Забрать бонус недели", callback_data="missions:claim")]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )
