from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from kcal_tracker.config import settings

MAIN_MENU_TEXTS = {
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
    "📈 7 дней",
    "📈 Неделя",
    "💧 Вода",
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
            [KeyboardButton(text="📷 Фото"), KeyboardButton(text="✍️ Еда")],
            [KeyboardButton(text="📊 Сегодня"), KeyboardButton(text="🔥 Остаток")],
            [KeyboardButton(text="💧 Вода"), KeyboardButton(text="☰ Ещё")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напиши еду или выбери действие",
    )


def more_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡ Частое", callback_data="nav:frequent"),
                InlineKeyboardButton(text="↩️ Как вчера", callback_data="nav:yesterday"),
            ],
            [
                InlineKeyboardButton(text="⭐ Любимое", callback_data="nav:favorites"),
                InlineKeyboardButton(text="📈 7 дней", callback_data="nav:week"),
            ],
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


def confirm_food_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Добавить", callback_data=f"{prefix}:confirm")],
            [InlineKeyboardButton(text="✏️ Граммовка", callback_data=f"{prefix}:edit")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"{prefix}:cancel")],
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
                InlineKeyboardButton(text="🏃 Ещё активность", callback_data="activity:custom"),
            ],
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


def food_entries_keyboard(entry_ids: list[int]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, entry_id in enumerate(entry_ids, start=1):
        rows.append(
            [
                InlineKeyboardButton(text=f"✏️ #{index}", callback_data=f"entry:edit:{entry_id}"),
                InlineKeyboardButton(text=f"🗑 #{index}", callback_data=f"entry:delete:{entry_id}"),
                InlineKeyboardButton(text=f"⭐ #{index}", callback_data=f"entry:fav:{entry_id}"),
            ]
        )
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
        [InlineKeyboardButton(text="➕ Добавить любимое", callback_data="fav:manual")]
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


def reminders_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    toggle_text = "Выключить напоминания" if enabled else "Включить напоминания"
    toggle_value = "off" if enabled else "on"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=f"reminders:{toggle_value}")],
            [InlineKeyboardButton(text="Время ужина", callback_data="reminders:dinner")],
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
        ]
    )


def subscription_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Открыть AI за {settings.ai_subscription_stars} ⭐",
                    callback_data="subscription:buy",
                )
            ],
        ]
    )
