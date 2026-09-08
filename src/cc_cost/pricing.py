"""usage(トークン数)と単価テーブルから金額(USD/JPY)を算出する。"""

from __future__ import annotations

import dataclasses

from .config import Config, ModelPricing
from .usage import Usage

TOKENS_PER_UNIT = 1_000_000.0


def cost_usd(usage: Usage, pricing: ModelPricing) -> float:
    return (
        usage.get("input", 0) / TOKENS_PER_UNIT * pricing.input
        + usage.get("output", 0) / TOKENS_PER_UNIT * pricing.output
        + usage.get("cache_write_5m", 0) / TOKENS_PER_UNIT * pricing.cache_write_5m
        + usage.get("cache_write_1h", 0) / TOKENS_PER_UNIT * pricing.cache_write_1h
        + usage.get("cache_read", 0) / TOKENS_PER_UNIT * pricing.cache_read
    )


def to_jpy(usd: float, config: Config) -> float:
    return usd * config.usd_to_jpy


@dataclasses.dataclass(frozen=True)
class PeriodCost:
    usd: float
    jpy: float
    has_unknown_model: bool


def compute_period_cost(models: dict[str, Usage], config: Config) -> PeriodCost:
    total_usd = 0.0
    has_unknown = False
    for model, usage in models.items():
        pricing = config.models.get(model)
        if pricing is None:
            if any(usage.values()):
                has_unknown = True
            continue
        total_usd += cost_usd(usage, pricing)
    return PeriodCost(usd=total_usd, jpy=to_jpy(total_usd, config), has_unknown_model=has_unknown)


def unknown_models_in(models: dict[str, Usage], config: Config) -> list[str]:
    return sorted(
        model
        for model, usage in models.items()
        if model not in config.models and any(usage.values())
    )
