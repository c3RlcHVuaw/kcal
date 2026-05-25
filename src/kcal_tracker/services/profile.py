from __future__ import annotations

from datetime import date
from math import ceil

from kcal_tracker.models import User
from kcal_tracker.schemas import WeightGoalRead

ACTIVITY_MULTIPLIERS = {
    "low": 1.2,
    "medium": 1.45,
    "high": 1.7,
}

GOAL_ADJUSTMENTS = {
    "loss": -350,
    "maintain": 0,
    "gain": 300,
}


def age_from_birth_date(birth_date: date, today: date | None = None) -> int:
    today = today or date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def user_age(user: User, today: date | None = None) -> int | None:
    birth_date = getattr(user, "birth_date", None)
    if birth_date:
        return age_from_birth_date(birth_date, today)
    return getattr(user, "age", None)


def calculate_daily_kcal_target(user: User) -> int:
    age = user_age(user)
    if not user.gender or not user.weight or not user.height or not age:
        return user.daily_kcal_target

    gender_offset = 5 if user.gender == "male" else -161
    bmr = 10 * user.weight + 6.25 * user.height - 5 * age + gender_offset
    activity = ACTIVITY_MULTIPLIERS.get(user.activity or "medium", 1.45)
    goal = GOAL_ADJUSTMENTS.get(user.goal or "maintain", 0)
    return max(round((bmr * activity + goal) / 50) * 50, 1200)


def default_weekly_weight_change(goal: str | None) -> float | None:
    if goal == "loss":
        return 0.5
    if goal == "gain":
        return 0.25
    return None


def weight_goal_summary(user: User) -> WeightGoalRead:
    weekly_change = user.weekly_weight_change_kg or default_weekly_weight_change(user.goal)
    forecast_weeks = _forecast_weeks(
        current_weight=user.weight,
        target_weight=user.target_weight_kg,
        weekly_change=weekly_change,
        goal=user.goal,
    )
    return WeightGoalRead(
        goal=user.goal,
        current_weight_kg=user.weight,
        target_weight_kg=user.target_weight_kg,
        weekly_weight_change_kg=weekly_change,
        daily_kcal_target=user.daily_kcal_target,
        forecast_weeks=forecast_weeks,
        forecast_text=weight_goal_forecast_text(user, forecast_weeks=forecast_weeks),
    )


def weight_goal_forecast_text(user: User, *, forecast_weeks: int | None = None) -> str:
    if user.goal == "maintain":
        return "Цель: держать текущий вес без резких качелей."
    if user.weight is None:
        return "Добавь текущий вес, чтобы увидеть прогноз."
    if user.target_weight_kg is None:
        return "Добавь желаемый вес, чтобы увидеть прогноз."
    weekly_change = user.weekly_weight_change_kg or default_weekly_weight_change(user.goal)
    if weekly_change is None:
        return "Выбери темп изменения веса, чтобы увидеть прогноз."
    if forecast_weeks is None:
        forecast_weeks = _forecast_weeks(
            current_weight=user.weight,
            target_weight=user.target_weight_kg,
            weekly_change=weekly_change,
            goal=user.goal,
        )
    if forecast_weeks is None:
        return "Проверь цель: желаемый вес должен совпадать с выбранным направлением."
    direction = "дефиците" if user.goal == "loss" else "профиците"
    return f"При таком среднем {direction} примерно {forecast_weeks} нед."


def _forecast_weeks(
    *,
    current_weight: float | None,
    target_weight: float | None,
    weekly_change: float | None,
    goal: str | None,
) -> int | None:
    if current_weight is None or target_weight is None or weekly_change is None:
        return None
    if weekly_change <= 0:
        return None
    delta = target_weight - current_weight
    if goal == "loss" and delta >= 0:
        return None
    if goal == "gain" and delta <= 0:
        return None
    if goal not in {"loss", "gain"}:
        return None
    return max(ceil(abs(delta) / weekly_change), 1)


def calculate_macro_targets(user: User) -> tuple[float, float, float]:
    kcal = user.daily_kcal_target
    protein = user.protein_target_g
    fat = user.fat_target_g
    carbs = user.carbs_target_g
    if protein is None:
        protein = round((user.weight or 75) * 1.6)
    if fat is None:
        fat = round(kcal * 0.3 / 9)
    if carbs is None:
        carbs = round(max(kcal - protein * 4 - fat * 9, 0) / 4)
    return protein, fat, carbs


def apply_default_macro_targets(user: User) -> None:
    protein, fat, carbs = calculate_macro_targets(user)
    user.protein_target_g = protein
    user.fat_target_g = fat
    user.carbs_target_g = carbs


def profile_summary(user: User) -> str:
    subscription = "активна" if user.subscription_expires_at else "не активна"
    protein, fat, carbs = calculate_macro_targets(user)
    birth_date = getattr(user, "birth_date", None)
    age = user_age(user)
    birth_date_label = birth_date.strftime("%d.%m.%Y") if birth_date else "не указана"
    age_label = f" ({age} лет)" if age else ""
    weight_goal = weight_goal_summary(user)
    return "\n".join(
        [
            "Профиль:",
            "",
            f"Язык: {user.language}",
            f"Пол: {user.gender or 'не указан'}",
            f"Дата рождения: {birth_date_label}{age_label}",
            f"Рост: {user.height or 'не указан'} см",
            f"Вес: {user.weight or 'не указан'} кг",
            f"Активность: {user.activity or 'не указана'}",
            f"Цель: {user.goal or 'не указана'}",
            f"Желаемый вес: {user.target_weight_kg or 'не указан'} кг",
            f"Темп: {weight_goal.weekly_weight_change_kg or 'не указан'} кг/нед",
            f"Прогноз: {weight_goal.forecast_text}",
            f"Калории: {user.daily_kcal_target} ккал/день",
            f"БЖУ: {protein:.0f} / {fat:.0f} / {carbs:.0f} г",
            f"Напоминания: {'включены' if user.reminders_enabled else 'выключены'}",
            f"AI-подписка: {subscription}",
        ]
    )
