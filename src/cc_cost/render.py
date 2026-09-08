"""CLI出力(issue #5で決定した Variant B: プロジェクトごとのブロック形式)。"""

from __future__ import annotations

from .config import Config
from .periods import PERIOD_KEYS, PERIOD_LABELS
from .pricing import PeriodCost, compute_period_cost, unknown_models_in
from .scanner import UsageByProjectPeriodModel
from .usage import Usage

RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
DIM = "\033[2m"


def _c(code: str, text: str, use_color: bool) -> str:
    return f"{code}{text}{RESET}" if use_color else text


def _fmt_money(cost: PeriodCost) -> str:
    return f"${cost.usd:,.2f} (¥{cost.jpy:,.0f})"


def _fmt_tokens(n: int) -> str:
    return f"{n:,}"


def render(
    grouped: list[tuple[str, dict[str, dict[str, Usage]]]],
    config: Config,
    verbose: bool,
    use_color: bool,
) -> None:
    if not grouped:
        print("表示できる使用量が見つかりませんでした。")
        return

    for group_name, periods in grouped:
        print(_c(BOLD + CYAN, f"■ {group_name}", use_color))

        all_unknown_models: set[str] = set()

        for period_key in PERIOD_KEYS:
            models = periods.get(period_key, {})
            cost = compute_period_cost(models, config)
            unknown_models = unknown_models_in(models, config)
            all_unknown_models.update(unknown_models)

            label = PERIOD_LABELS[period_key]
            line = f"    {label:<6}: {_fmt_money(cost)}"
            if unknown_models:
                line += " " + _c(YELLOW, "(一部不明を含む)", use_color)
            print(line)

            if verbose and models:
                for model in sorted(models):
                    usage = models[model]
                    if not any(usage.values()):
                        continue
                    pricing = config.models.get(model)
                    amount = (
                        _fmt_money(compute_period_cost({model: usage}, config))
                        if pricing is not None
                        else "不明"
                    )
                    print(
                        f"        {model:<28} "
                        f"in={_fmt_tokens(usage.get('input', 0)):>10} "
                        f"out={_fmt_tokens(usage.get('output', 0)):>9} "
                        f"cache5m={_fmt_tokens(usage.get('cache_write_5m', 0)):>9} "
                        f"cache1h={_fmt_tokens(usage.get('cache_write_1h', 0)):>9} "
                        f"cacheRead={_fmt_tokens(usage.get('cache_read', 0)):>10}  {amount}"
                    )

        for model in sorted(all_unknown_models):
            print(f"    {_c(YELLOW, f'⚠ {model} は単価テーブルに未登録です(金額は不明として扱われます)', use_color)}")

        print()
