"""CLI出力(issue #5で決定した Variant B: プロジェクトごとのブロック形式)。"""

from __future__ import annotations

import datetime as dt
import sys
from collections.abc import Iterable

from .config import Config
from .grouping import readable_dir_name
from .periods import PERIOD_KEYS, PERIOD_LABELS
from .pricing import PeriodCost, compute_period_cost, unknown_models_in
from .scanner import SessionLog, SessionUsage
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


def _fmt_datetime(value: dt.datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value is not None else "-"


def _print_model_breakdown(models: dict[str, Usage], config: Config) -> None:
    for model in sorted(models):
        usage = models[model]
        if not any(usage.values()):
            continue
        pricing = config.models.get(model)
        amount = _fmt_money(compute_period_cost({model: usage}, config)) if pricing is not None else "不明"
        print(
            f"        {model:<28} "
            f"in={_fmt_tokens(usage.get('input', 0)):>10} "
            f"out={_fmt_tokens(usage.get('output', 0)):>9} "
            f"cache5m={_fmt_tokens(usage.get('cache_write_5m', 0)):>9} "
            f"cache1h={_fmt_tokens(usage.get('cache_write_1h', 0)):>9} "
            f"cacheRead={_fmt_tokens(usage.get('cache_read', 0)):>10}  {amount}"
        )


def _print_unknown_model_warnings(unknown_models: Iterable[str], use_color: bool) -> None:
    for model in sorted(unknown_models):
        print(f"    {_c(YELLOW, f'⚠ {model} は単価テーブルに未登録です(金額は不明として扱われます)', use_color)}")


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

            if verbose:
                _print_model_breakdown(models, config)

        _print_unknown_model_warnings(all_unknown_models, use_color)

        print()


def render_session(
    group_name: str,
    session_id: str,
    session_usage: SessionUsage,
    config: Config,
    verbose: bool,
    use_color: bool,
) -> None:
    """1つのセッション(サイドチェーン込み)の合計コストを、期間で分けずに表示する。"""
    models = session_usage.models
    cost = compute_period_cost(models, config)
    unknown_models = unknown_models_in(models, config)

    print(_c(BOLD + CYAN, f"■ {group_name}", use_color))
    print(f"    セッション: {session_id}")
    print(f"    期間      : {_fmt_datetime(session_usage.first_at)} 〜 {_fmt_datetime(session_usage.last_at)}")
    line = f"    合計      : {_fmt_money(cost)}"
    if unknown_models:
        line += " " + _c(YELLOW, "(一部不明を含む)", use_color)
    print(line)

    if verbose:
        _print_model_breakdown(models, config)

    _print_unknown_model_warnings(unknown_models, use_color)
    print()


def render_session_candidates(prefix: str, sessions: list[SessionLog]) -> None:
    """前方一致で複数のセッションに一致したときの候補一覧を stderr に出す。

    候補が複数のログルートにまたがるときは、区別できるようにログルートのパスを付ける。
    """
    print(f"セッションID '{prefix}' に一致するセッションが複数あります:", file=sys.stderr)
    show_root = len({s.root for s in sessions}) > 1
    for session in sessions:
        line = (
            f"    {session.session_id}  {readable_dir_name(session.dir_name)}  "
            f"{_fmt_datetime(session.last_modified())}"
        )
        if show_root:
            line += f"  [{session.root}]"
        print(line, file=sys.stderr)
