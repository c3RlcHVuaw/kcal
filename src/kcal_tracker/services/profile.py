from __future__ import annotations

from kcal_tracker.models import User

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


def calculate_daily_kcal_target(user: User) -> int:
    if not user.gender or not user.weight or not user.height or not user.age:
        return user.daily_kcal_target

    gender_offset = 5 if user.gender == "male" else -161
    bmr = 10 * user.weight + 6.25 * user.height - 5 * user.age + gender_offset
    activity = ACTIVITY_MULTIPLIERS.get(user.activity or "medium", 1.45)
    goal = GOAL_ADJUSTMENTS.get(user.goal or "maintain", 0)
    return max(round((bmr * activity + goal) / 50) * 50, 1200)


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
    return "\n".join(
        [
            "Профиль:",
            "",
            f"Язык: {user.language}",
            f"Пол: {user.gender or 'не указан'}",
            f"Возраст: {user.age or 'не указан'}",
            f"Рост: {user.height or 'не указан'} см",
            f"Вес: {user.weight or 'не указан'} кг",
            f"Активность: {user.activity or 'не указана'}",
            f"Цель: {user.goal or 'не указана'}",
            f"Калории: {user.daily_kcal_target} ккал/день",
            f"БЖУ: {protein:.0f} / {fat:.0f} / {carbs:.0f} г",
            f"Напоминания: {'включены' if user.reminders_enabled else 'выключены'}",
            f"AI-подписка: {subscription}",
        ]
    )
