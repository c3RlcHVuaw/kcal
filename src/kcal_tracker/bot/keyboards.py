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


def more_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍽 Что съесть?", callback_data="coach:meal")],
            [
                InlineKeyboardButton(text="⚡ Частое", callback_data="nav:frequent"),
                InlineKeyboardButton(text="⚡ Шаблоны", callback_data="nav:templates"),
            ],
            [
                InlineKeyboardButton(text="↩️ Как вчера", callback_data="nav:yesterday"),
                InlineKeyboardButton(text="📈 7 дней", callback_data="nav:week"),
            ],
            [InlineKeyboardButton(text="📅 Месяц", callback_data="nav:month")],
            [
                InlineKeyboardButton(text="🏃 Активность", callback_data="nav:activity"),
                InlineKeyboardButton(text="⚖️ Вес", callback_data="nav:weight"),
            ],
            [
                InlineKeyboardButton(text="⏰ Напомнить", callback_data="nav:reminders"),
                InlineKeyboardButton(text="💎 Подписка", callback_data="subscription:open"),
            ],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings:open")],
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
    rows.append(edit_row)
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"{prefix}:cancel")])
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


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
) -> InlineKeyboardMarkup:
    if not expanded:
        rows = []
        if entry_ids:
            rows.append(
                [
                    InlineKeyboardButton(text="✏️ Редактировать", callback_data="entry:manage"),
                    InlineKeyboardButton(text="🍽 Что съесть?", callback_data="coach:meal"),
                ]
            )
        else:
            rows.append([InlineKeyboardButton(text="➕ Еду", callback_data="nav:add-food")])
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


def food_search_results_keyboard(count: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"Выбрать #{index}",
                callback_data=f"foodsearch:choose:{index - 1}",
            )
        ]
        for index in range(1, count + 1)
    ]
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


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Язык", callback_data="settings:language")],
            [InlineKeyboardButton(text="Пол", callback_data="settings:gender")],
            [InlineKeyboardButton(text="Возраст", callback_data="settings:age")],
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


def subscription_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Оформить подписку", callback_data="subscription:subscribe")],
        [
            InlineKeyboardButton(text="🤝 Пригласить друга", callback_data="subscription:referral"),
            InlineKeyboardButton(
                text="📊 Реферальный кабинет",
                callback_data="subscription:referral-dashboard",
            ),
        ],
        [InlineKeyboardButton(text="🎁 Бонусы", callback_data="subscription:bonuses")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscription_payment_method_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"СБП Старт {settings.ai_subscription_rub} ₽",
                    callback_data="subscription:yookassa:basic:sbp",
                ),
                InlineKeyboardButton(
                    text=f"Карта/SberPay Старт {settings.ai_subscription_rub} ₽",
                    callback_data="subscription:yookassa:basic:auto",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"Звёзды Telegram Старт {settings.ai_subscription_stars} ⭐",
                    callback_data="subscription:stars:basic",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"СБП Безлимит {settings.ai_unlimited_subscription_rub} ₽",
                    callback_data="subscription:yookassa:unlimited:sbp",
                ),
                InlineKeyboardButton(
                    text=f"Карта/SberPay Безлимит {settings.ai_unlimited_subscription_rub} ₽",
                    callback_data="subscription:yookassa:unlimited:auto",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=(
                        "Звёзды Telegram Безлимит "
                        f"{settings.ai_unlimited_subscription_stars} ⭐"
                    ),
                    callback_data="subscription:stars:unlimited",
                )
            ],
            [InlineKeyboardButton(text="Назад", callback_data="subscription:open")],
        ]
    )


def subscription_bonuses_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎁 Пробный premium-день",
                    callback_data="subscription:trial",
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Вернуть AI на день",
                    callback_data="subscription:winback",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Возврат оплаты за 24 часа",
                    callback_data="subscription:refund",
                )
            ],
            [InlineKeyboardButton(text="Назад", callback_data="subscription:open")],
        ]
    )


def subscription_cta_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оформить подписку", callback_data="subscription:subscribe")]
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
