from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.models import AdminSetting, AIUsage

OPENAI_BALANCE_KEY = "openai_balance"
GPT_4O_MINI_INPUT_PER_1M = 0.15
GPT_4O_MINI_OUTPUT_PER_1M = 0.60


@dataclass(frozen=True)
class OpenAICostSummary:
    balance_usd: float
    spent_usd: float
    remaining_usd: float
    initial_balance_usd: float
    manual_adjustments_usd: float
    month_requests: int
    today_requests: int
    month_input_tokens: int
    month_output_tokens: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    updated_at: datetime | None


class OpenAIBalanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def summary(self, *, today: date | None = None) -> OpenAICostSummary:
        today = today or datetime.now(UTC).date()
        month_start = today.replace(day=1)
        setting = await self._setting()
        balance_usd = _float_value(setting.value.get("balance_usd"), 0.0) if setting else 0.0
        initial_balance_usd = (
            _float_value(setting.value.get("initial_balance_usd"), balance_usd) if setting else 0.0
        )
        manual_adjustments_usd = (
            _float_value(setting.value.get("manual_adjustments_usd"), 0.0) if setting else 0.0
        )
        month_rows = await self.session.execute(
            select(
                AIUsage.request_type,
                func.coalesce(func.sum(AIUsage.request_count), 0),
                func.coalesce(func.sum(AIUsage.input_tokens), 0),
                func.coalesce(func.sum(AIUsage.output_tokens), 0),
            )
            .where(AIUsage.usage_date >= month_start)
            .group_by(AIUsage.request_type)
        )
        today_requests = await self.session.scalar(
            select(func.coalesce(func.sum(AIUsage.request_count), 0)).where(
                AIUsage.usage_date == today
            )
        )
        request_count = 0
        actual_input = 0
        actual_output = 0
        estimated_input = 0
        estimated_output = 0
        for request_type, count, input_tokens, output_tokens in month_rows.all():
            count = int(count or 0)
            input_tokens = int(input_tokens or 0)
            output_tokens = int(output_tokens or 0)
            request_count += count
            actual_input += input_tokens
            actual_output += output_tokens
            if input_tokens <= 0 and output_tokens <= 0:
                estimate = _estimated_tokens(request_type, count)
                estimated_input += estimate[0]
                estimated_output += estimate[1]

        billable_input = actual_input + estimated_input
        billable_output = actual_output + estimated_output
        spent_usd = _token_cost_usd(billable_input, billable_output)
        return OpenAICostSummary(
            balance_usd=balance_usd,
            spent_usd=spent_usd,
            remaining_usd=balance_usd - spent_usd,
            initial_balance_usd=initial_balance_usd,
            manual_adjustments_usd=manual_adjustments_usd,
            month_requests=request_count,
            today_requests=int(today_requests or 0),
            month_input_tokens=actual_input,
            month_output_tokens=actual_output,
            estimated_input_tokens=estimated_input,
            estimated_output_tokens=estimated_output,
            updated_at=setting.updated_at if setting else None,
        )

    async def set_balance(self, amount_usd: float) -> OpenAICostSummary:
        amount_usd = max(round(amount_usd, 2), 0.0)
        await self._write_balance(amount_usd)
        return await self.summary()

    async def adjust_balance(self, delta_usd: float) -> OpenAICostSummary:
        setting = await self._setting(for_update=True)
        current = _float_value(setting.value.get("balance_usd"), 0.0) if setting else 0.0
        await self._write_balance(current + delta_usd, setting=setting)
        return await self.summary()

    async def _write_balance(
        self,
        amount_usd: float,
        *,
        setting: AdminSetting | None = None,
    ) -> None:
        amount_usd = max(round(amount_usd, 2), 0.0)
        if setting is None:
            setting = await self._setting(for_update=True)
        if setting is None:
            setting = AdminSetting(
                key=OPENAI_BALANCE_KEY,
                value={
                    "balance_usd": amount_usd,
                    "initial_balance_usd": amount_usd,
                    "manual_adjustments_usd": 0.0,
                },
            )
            self.session.add(setting)
        else:
            current = _float_value(setting.value.get("balance_usd"), 0.0)
            value = dict(setting.value)
            value["balance_usd"] = amount_usd
            value["manual_adjustments_usd"] = round(
                _float_value(value.get("manual_adjustments_usd"), 0.0) + (amount_usd - current),
                2,
            )
            value.setdefault("initial_balance_usd", amount_usd)
            setting.value = value
        await self.session.commit()

    async def _setting(self, *, for_update: bool = False) -> AdminSetting | None:
        query = select(AdminSetting).where(AdminSetting.key == OPENAI_BALANCE_KEY)
        if for_update:
            query = query.with_for_update()
        return await self.session.scalar(query)


def _token_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return round(
        input_tokens * GPT_4O_MINI_INPUT_PER_1M / 1_000_000
        + output_tokens * GPT_4O_MINI_OUTPUT_PER_1M / 1_000_000,
        4,
    )


def _estimated_tokens(request_type: str, count: int) -> tuple[int, int]:
    per_request = {
        "webapp_photo": (1600, 420),
        "ai_photo": (1600, 420),
        "food_photo": (1600, 420),
        "webapp_manual_text": (700, 260),
        "webapp_food_search_ai": (650, 240),
        "webapp_food_refine": (520, 220),
        "food_text": (750, 280),
        "food_voice": (900, 300),
        "activity_text": (520, 180),
    }
    input_tokens, output_tokens = per_request.get(request_type, (750, 280))
    return input_tokens * count, output_tokens * count


def _float_value(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
