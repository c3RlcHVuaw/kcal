from __future__ import annotations

from typing import Any

from aiogram.types import (
    InlineKeyboardButton as _InlineKeyboardButton,
)
from aiogram.types import (
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from aiogram.types import (
    KeyboardButton as _KeyboardButton,
)

from kcal_tracker.config import settings

MAIN_MENU_TEXTS = {
    "➕ Еда",
    "Еда",
    "📷 Фото/штрихкод",
    "Фото/штрихкод",
    "📷 Сканировать продукт",
    "Сканировать продукт",
    "📷 Фото",
    "Фото",
    "✍️ Записать еду",
    "Записать еду",
    "🍔 Добавить еду",
    "Добавить еду",
    "✍️ Еда",
    "📊 Сегодня",
    "Сегодня",
    "📊 Мой день",
    "Мой день",
    "🔥 Остаток",
    "Остаток",
    "🔥 Калории",
    "Калории",
    "⚡ Частое",
    "Частое",
    "⭐ Частые продукты",
    "Частые продукты",
    "↩️ Как вчера",
    "Как вчера",
    "↩️ Повторить вчера",
    "Повторить вчера",
    "⭐ Любимое",
    "Любимое",
    "⭐ Избранное",
    "Избранное",
    "⚡ Шаблоны",
    "Шаблоны",
    "📅 Месяц",
    "Месяц",
    "📈 7 дней",
    "7 дней",
    "📈 Неделя",
    "Неделя",
    "💧 Вода",
    "Вода",
    "🍽 Что съесть?",
    "Что съесть?",
    "🍽 Что съесть",
    "Что съесть",
    "🏃 Активность",
    "Активность",
    "⚖️ Вес",
    "Вес",
    "⏰ Напомнить",
    "Напомнить",
    "⏰ Напоминания",
    "Напоминания",
    "⚙️ Настройки",
    "Настройки",
    "💎 Подписка",
    "Подписка",
    "🆘 Поддержка",
    "Поддержка",
    "☰ Ещё",
    "Ещё",
    "🏠 Меню",
    "Меню",
    "❌ Отмена",
    "Отмена",
}

BUTTON_CUSTOM_EMOJI_IDS: dict[str, str] = {
    "entry:delete": "5033287275287413303",
    "delete": "5033287275287413303",
    "удал": "5033287275287413303",
    "cancel": "5032973497861669622",
    "отмена": "5032973497861669622",
    "wrong": "5032973497861669622",
    "не то": "5032973497861669622",
    "confirm": "5206607081334906820",
    "сохран": "5206607081334906820",
    "готов": "5206607081334906820",
    "подтверд": "5206607081334906820",
    "add": "5030749344752468962",
    "добав": "5030749344752468962",
    "➕": "5030749344752468962",
    "payment": "4967518033061872209",
    "оплат": "4967518033061872209",
    "юkassa": "4967518033061872209",
    "subscription": "5427168083074628963",
    "premium": "5427168083074628963",
    "подпис": "5427168083074628963",
    "trial": "5406756500108501710",
    "bonus": "5461151367559141950",
    "бонус": "5461151367559141950",
    "claim": "5461151367559141950",
    "забрать": "5461151367559141950",
    "referral": "5337080053119336309",
    "приглас": "5337080053119336309",
    "photo": "4967502231877190509",
    "фото": "4967502231877190509",
    "scan": "4967502231877190509",
    "штрихкод": "4967502231877190509",
    "search": "5231012545799666522",
    "поиск": "5231012545799666522",
    "найти": "5231012545799666522",
    "nav:progress": "5244837092042750681",
    "progress": "5244837092042750681",
    "прогресс": "5244837092042750681",
    "ai": "5325547803936572038",
    "уточнить": "5325547803936572038",
    "settings": "5341715473882955310",
    "nav:service": "5341715473882955310",
    "service": "5341715473882955310",
    "сервис": "5341715473882955310",
    "⚙": "5341715473882955310",
    "настрой": "5341715473882955310",
    "water": "5393512611968995988",
    "nav:body": "5393512611968995988",
    "body": "5393512611968995988",
    "тело": "5393512611968995988",
    "💧": "5393512611968995988",
    "вода": "5393512611968995988",
    "воды": "5393512611968995988",
    "today": "5231200819986047254",
    "сегодня": "5231200819986047254",
    "дневник": "5231200819986047254",
    "week": "5244837092042750681",
    "недел": "5244837092042750681",
    "month": "5413879192267805083",
    "месяц": "5413879192267805083",
    "calendar": "5413879192267805083",
    "activity": "5424972470023104089",
    "актив": "5424972470023104089",
    "weight": "5416081784641168838",
    "вес": "5416081784641168838",
    "reminders": "5458603043203327669",
    "напомин": "5458603043203327669",
    "support": "5443038326535759644",
    "поддерж": "5443038326535759644",
    "menu": "5416041192905265756",
    "меню": "5416041192905265756",
    "home": "5416041192905265756",
    "назад": "4972453139463537420",
    "вернуться": "4972453139463537420",
    "←": "4972453139463537420",
    "↩": "4972453139463537420",
    "edit": "5395444784611480792",
    "редакт": "5395444784611480792",
    "исправ": "5395444784611480792",
    "граммов": "5395444784611480792",
    "название": "5395444784611480792",
    "калории": "5395444784611480792",
    "шаблон": "5438496463044752972",
    "favorite": "5438496463044752972",
    "избран": "5438496463044752972",
    "частое": "5438496463044752972",
    "еда": "5033300671290409647",
    "food": "5033300671290409647",
    "что съесть": "5033300671290409647",
    "экспорт": "5271604874419647061",
    "поделиться": "5271604874419647061",
}

CALLBACK_CUSTOM_EMOJI_IDS: tuple[tuple[str, str], ...] = (
    ("subscription:trial", "5406756500108501710"),
    ("subscription:winback", "4972453139463537420"),
    ("subscription:refund:confirm", "5206607081334906820"),
    ("subscription:refund", "5233326571099534068"),
    ("subscription:bonuses", "5461151367559141950"),
    ("subscription:referral-dashboard", "5231200819986047254"),
    ("subscription:referral", "5337080053119336309"),
    ("subscription:promo", "5222444124698853913"),
    ("subscription:yookassa", "4967518033061872209"),
    ("subscription:check", "5206607081334906820"),
    ("subscription:stars", "5438496463044752972"),
    ("subscription:plan:basic", "5382357040008021292"),
    ("subscription:plan:unlimited", "5341498088408234504"),
    ("subscription:subscribe", "5217822164362739968"),
    ("subscription:open", "5427168083074628963"),
    ("nav:service-tools", "5334544901428229844"),
    ("settings:open", "5341715473882955310"),
)

PLAIN_BUTTON_ICON_CHARS = set(
    " \t\n"
    "➕➖✅❌✏🗑📊📈📅💧🍽🏃⚖⏰⚙💎🆘☰🏠🔥⚡⭐↩←→➡⬅"
    "📷🍔✍🤖🔎✨🧩🙅½¼🧈🥤📉🚨🔄🖥🧠👥💰🎟📣👤🎁🤝💳"
    "\ufe0f"
)


def InlineKeyboardButton(text: str, **kwargs: Any) -> _InlineKeyboardButton:
    return _button(_InlineKeyboardButton, text=text, **kwargs)


def KeyboardButton(text: str, **kwargs: Any) -> _KeyboardButton:
    return _KeyboardButton(text=text, **kwargs)


def _button(button_type, *, text: str, **kwargs: Any):
    styled_kwargs = {
        **kwargs,
        "style": kwargs.get("style") or _button_style(text, kwargs.get("callback_data")),
    }
    icon_id = kwargs.get("icon_custom_emoji_id") or _custom_emoji_id(text, kwargs.get("callback_data"))
    if icon_id:
        styled_kwargs["icon_custom_emoji_id"] = icon_id
        styled_kwargs["text"] = _button_text_without_plain_icon(text)
    try:
        return button_type(**styled_kwargs)
    except Exception:
        # Older aiogram/Bot API versions may not know style/icon_custom_emoji_id yet.
        styled_kwargs.pop("text", None)
        styled_kwargs.pop("style", None)
        styled_kwargs.pop("icon_custom_emoji_id", None)
        return button_type(text=text, **styled_kwargs)


def _button_text_without_plain_icon(text: str) -> str:
    stripped = text.strip()
    while stripped and stripped[0] in PLAIN_BUTTON_ICON_CHARS:
        stripped = stripped[1:].strip()
    return stripped or text


def _button_style(text: str, callback_data: str | None = None) -> str:
    source = f"{text} {callback_data or ''}".lower()
    if any(
        token in source
        for token in (
            "cancel",
            "delete",
            ":del",
            ":wrong",
            ":off",
            "возврат",
            "отмена",
            "удал",
            "не то",
            "выключ",
        )
    ):
        return "danger"
    if any(
        token in source
        for token in (
            "confirm",
            ":add",
            ":all",
            ":done",
            ":start",
            "subscription:open",
            ":subscribe",
            ":trial",
            ":claim",
            "✅",
            "➕",
            "добав",
            "сохран",
            "готов",
            "создать",
            "оформ",
            "оплат",
            "отправить",
            "подтверд",
            "подпис",
            "продл",
            "забрать",
            "собрать",
            "включ",
        )
    ):
        return "success"
    return "primary"


def _custom_emoji_id(text: str, callback_data: str | None = None) -> str | None:
    if callback_data:
        for callback_prefix, emoji_id in CALLBACK_CUSTOM_EMOJI_IDS:
            if callback_data.startswith(callback_prefix):
                return emoji_id
    source = f"{text} {callback_data or ''}".lower()
    for key, emoji_id in BUTTON_CUSTOM_EMOJI_IDS.items():
        if key in source:
            return emoji_id
    return None


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
    rows.append([InlineKeyboardButton(text="↩️ Удалить последнее", callback_data="entry:delete-last")])
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
    allow_split: bool = False,
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
    if allow_split:
        rows.append([InlineKeyboardButton(text="🧩 Разбить блюдо", callback_data=f"{prefix}:split")])
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
        rows.append([InlineKeyboardButton(text="🤖 Уточнить через AI", callback_data="food:ai")])
    if allow_database:
        rows.append([InlineKeyboardButton(text="🔎 Найти в базе", callback_data="food:search")])
    rows.append([InlineKeyboardButton(text="✍️ Ввести вручную", callback_data="nav:add-food")])
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
    if entry_id is not None:
        rows.append(
            [
                InlineKeyboardButton(text="✏️ Исправить", callback_data=f"entry:edit-menu:{entry_id}"),
                InlineKeyboardButton(text="↩️ Отменить", callback_data=f"entry:delete:{entry_id}"),
            ]
        )
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


def entry_edit_keyboard(entry_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚖️ Граммовка", callback_data=f"entry:edit:{entry_id}"),
                InlineKeyboardButton(text="✏️ Название", callback_data=f"entry:edit-name:{entry_id}"),
            ],
            [
                InlineKeyboardButton(text="🔥 Калории", callback_data=f"entry:edit-kcal:{entry_id}"),
                InlineKeyboardButton(text="Б/Ж/У", callback_data=f"entry:edit-macros:{entry_id}"),
            ],
            [InlineKeyboardButton(text="📊 Сегодня", callback_data="nav:today")],
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
            [InlineKeyboardButton(text="Желаемый вес", callback_data="settings:target-weight")],
            [InlineKeyboardButton(text="Темп веса", callback_data="settings:weight-pace")],
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
                text="📊 Кабинет",
                callback_data="subscription:referral-dashboard",
            ),
        ],
    ]
    if bonuses_available:
        rows.append([InlineKeyboardButton(text="🎁 Бонусы и возврат", callback_data="subscription:bonuses")])
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


def subscription_payment_method_keyboard(
    plan_code: str,
    *,
    promo_code: str | None = None,
) -> InlineKeyboardMarkup:
    is_unlimited = plan_code == "unlimited"
    title = "Безлимит" if is_unlimited else "Старт"
    rub = settings.ai_unlimited_subscription_rub if is_unlimited else settings.ai_subscription_rub
    stars = (
        settings.ai_unlimited_subscription_stars if is_unlimited else settings.ai_subscription_stars
    )
    promo_suffix = f":{promo_code}" if promo_code else ""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Ввести промокод", callback_data=f"subscription:promo:ask:{plan_code}")],
            [
                InlineKeyboardButton(
                    text=f"СБП {rub} ₽",
                    callback_data=f"subscription:yookassa:{plan_code}:sbp{promo_suffix}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Карта/SberPay {rub} ₽",
                    callback_data=f"subscription:yookassa:{plan_code}:auto{promo_suffix}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Звёзды Telegram {stars} ⭐",
                    callback_data=f"subscription:stars:{plan_code}{promo_suffix}",
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
