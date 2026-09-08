#!/usr/bin/env python3
"""
PROTOTYPE — throwaway. Answers: "issue #5: CLI出力フォーマットはどう見せるか?"

三つの構造的に異なるレイアウト案(A/B/C)を、架空のモックデータで実際にターミナルへ
表示して見比べるためのスクリプト。本実装のモジュール設計とは無関係。

使い方:
    python3 prototypes/cli_output_prototype.py --variant a
    python3 prototypes/cli_output_prototype.py --variant b --verbose
    python3 prototypes/cli_output_prototype.py --variant c
    python3 prototypes/cli_output_prototype.py --all          # 3案まとめて表示
"""

import argparse

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
GREEN = "\033[32m"
RED = "\033[31m"

PERIOD_LABELS = [
    ("today", "本日"),
    ("this_month", "今月"),
    ("last_month", "先月"),
    ("two_months_ago", "先々月"),
]

# 架空のモックデータ。うち "internal-tool" は単価テーブルに無いモデルを含む。
PROJECTS = [
    {
        "name": "cc-cost",
        "periods": {
            "today": {"usd": 0.42, "jpy": 63},
            "this_month": {"usd": 12.35, "jpy": 1852},
            "last_month": {"usd": 45.10, "jpy": 6765},
            "two_months_ago": {"usd": 30.02, "jpy": 4503},
        },
        "models": {
            "claude-sonnet-5": {
                "input": 120_000, "output": 45_000,
                "cache_write_5m": 80_000, "cache_write_1h": 0, "cache_read": 900_000,
                "usd": 9.80, "jpy": 1470,
            },
            "claude-opus-5": {
                "input": 8_000, "output": 3_000,
                "cache_write_5m": 0, "cache_write_1h": 20_000, "cache_read": 60_000,
                "usd": 2.55, "jpy": 382,
            },
        },
    },
    {
        "name": "ecsite-example",
        "periods": {
            "today": {"usd": 0.0, "jpy": 0},
            "this_month": {"usd": 3.10, "jpy": 465},
            "last_month": {"usd": 8.44, "jpy": 1266},
            "two_months_ago": {"usd": 0.0, "jpy": 0},
        },
        "models": {
            "claude-haiku-4-5-20251001": {
                "input": 50_000, "output": 20_000,
                "cache_write_5m": 10_000, "cache_write_1h": 0, "cache_read": 200_000,
                "usd": 3.10, "jpy": 465,
            },
        },
    },
    {
        "name": "internal-tool",
        "periods": {
            "today": {"usd": 1.05, "jpy": 158, "unknown_usd": True},
            "this_month": {"usd": 22.00, "jpy": 3300, "unknown_usd": True},
            "last_month": {"usd": 5.00, "jpy": 750},
            "two_months_ago": {"usd": 0.0, "jpy": 0},
        },
        "models": {
            "claude-sonnet-5": {
                "input": 30_000, "output": 10_000,
                "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 50_000,
                "usd": 5.00, "jpy": 750,
            },
            "claude-mystery-1": {
                "input": 15_000, "output": 6_000,
                "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 0,
                "usd": None, "jpy": None,
            },
        },
        "warning": "claude-mystery-1 は単価テーブルに未登録です(金額は不明として扱われます)",
    },
    {
        "name": "mattpocock-skills-demo",
        "periods": {
            "today": {"usd": 0.0, "jpy": 0},
            "this_month": {"usd": 0.0, "jpy": 0},
            "last_month": {"usd": 1.20, "jpy": 180},
            "two_months_ago": {"usd": 2.40, "jpy": 360},
        },
        "models": {
            "claude-sonnet-5": {
                "input": 5_000, "output": 2_000,
                "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 10_000,
                "usd": 1.20, "jpy": 180,
            },
        },
    },
]


def fmt_money(usd, jpy):
    if usd is None:
        return "不明"
    return f"${usd:,.2f} (¥{jpy:,.0f})"


def fmt_tokens(n):
    return f"{n:,}"


# ---------------------------------------------------------------------------
# Variant A: 罫線つきの表形式。行=プロジェクト、列=期間。
# ---------------------------------------------------------------------------

def variant_a(verbose: bool):
    print(f"{BOLD}[Variant A] 表形式(行=プロジェクト、列=期間){RESET}\n")

    headers = ["プロジェクト"] + [label for _, label in PERIOD_LABELS]
    rows = []
    for p in PROJECTS:
        row = [p["name"]]
        for key, _ in PERIOD_LABELS:
            period = p["periods"][key]
            cell = fmt_money(period["usd"], period["jpy"])
            if period.get("unknown_usd"):
                cell += f" {YELLOW}*{RESET}"
            row.append(cell)
        rows.append(row)

    widths = [
        max(_display_width(headers[i]), *(_display_width(r[i]) for r in rows))
        for i in range(len(headers))
    ]

    def draw_sep(left, mid, right, fill="─"):
        print(left + mid.join(fill * (w + 2) for w in widths) + right)

    def draw_row(cells):
        parts = []
        for i, c in enumerate(cells):
            pad = widths[i] - _display_width(c)
            parts.append(" " + c + " " * pad + " ")
        print("│" + "│".join(parts) + "│")

    draw_sep("┌", "┬", "┐")
    draw_row(headers)
    draw_sep("├", "┼", "┤")
    for row in rows:
        draw_row(row)
    draw_sep("└", "┴", "┘")

    warnings = [p["warning"] for p in PROJECTS if "warning" in p]
    if warnings:
        print()
        for w in warnings:
            print(f"{YELLOW}⚠ {w}{RESET}")

    if verbose:
        print(f"\n{DIM}--verbose: モデル別内訳(今月分){RESET}")
        for p in PROJECTS:
            print(f"\n{CYAN}{p['name']}{RESET}")
            _print_model_table(p["models"])


# ---------------------------------------------------------------------------
# Variant B: プロジェクトごとのブロック形式。
# ---------------------------------------------------------------------------

def variant_b(verbose: bool):
    print(f"{BOLD}[Variant B] ブロック形式(プロジェクトごとに縦積み){RESET}\n")

    for p in PROJECTS:
        print(f"{BOLD}{CYAN}■ {p['name']}{RESET}")
        for key, label in PERIOD_LABELS:
            period = p["periods"][key]
            marker = f" {YELLOW}(一部不明を含む){RESET}" if period.get("unknown_usd") else ""
            print(f"    {label:<6}: {fmt_money(period['usd'], period['jpy'])}{marker}")
        if "warning" in p:
            print(f"    {YELLOW}⚠ {p['warning']}{RESET}")
        if verbose:
            print(f"    {DIM}--- モデル別内訳(今月分) ---{RESET}")
            for model, m in p["models"].items():
                amount = fmt_money(m["usd"], m["jpy"])
                print(
                    f"      {model:<28} in={fmt_tokens(m['input']):>10} "
                    f"out={fmt_tokens(m['output']):>9} "
                    f"cache5m={fmt_tokens(m['cache_write_5m']):>9} "
                    f"cache1h={fmt_tokens(m['cache_write_1h']):>9} "
                    f"cacheRead={fmt_tokens(m['cache_read']):>10}  {amount}"
                )
        print()


# ---------------------------------------------------------------------------
# Variant C: 1プロジェクト1行の超コンパクト・ダッシュボード形式。
# ---------------------------------------------------------------------------

def variant_c(verbose: bool):
    print(f"{BOLD}[Variant C] 1行コンパクト形式{RESET}\n")

    name_w = max(len(p["name"]) for p in PROJECTS) + 2
    for p in PROJECTS:
        parts = []
        for key, label in PERIOD_LABELS:
            period = p["periods"][key]
            color = GREEN if period["usd"] and period["usd"] > 20 else ""
            flag = f"{YELLOW}*{RESET}" if period.get("unknown_usd") else ""
            parts.append(f"{DIM}{label}{RESET} {color}{fmt_money(period['usd'], period['jpy'])}{RESET}{flag}")
        line = f"{p['name']:<{name_w}}" + f" {DIM}・{RESET} ".join(parts)
        print(line)
        if "warning" in p:
            print(f"{'':<{name_w}}{YELLOW}⚠ {p['warning']}{RESET}")

    print(f"\n{DIM}* = 単価不明なモデルを含む(トークン数は集計済み、金額は一部不明){RESET}")

    if verbose:
        print(f"\n{DIM}--verbose: モデル別内訳(今月分){RESET}")
        for p in PROJECTS:
            print(f"\n{CYAN}{p['name']}{RESET}")
            _print_model_table(p["models"])


def _print_model_table(models):
    for model, m in models.items():
        amount = fmt_money(m["usd"], m["jpy"])
        print(
            f"  {model:<28} in={fmt_tokens(m['input']):>10} "
            f"out={fmt_tokens(m['output']):>9} "
            f"cache5m={fmt_tokens(m['cache_write_5m']):>9} "
            f"cache1h={fmt_tokens(m['cache_write_1h']):>9} "
            f"cacheRead={fmt_tokens(m['cache_read']):>10}  {amount}"
        )


def _strip_ansi(s: str) -> str:
    import re
    return re.sub(r"\033\[[0-9;]*m", "", s)


def _display_width(s: str) -> int:
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in _strip_ansi(s))


VARIANTS = {"a": variant_a, "b": variant_b, "c": variant_c}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=VARIANTS.keys(), default="a")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--all", action="store_true", help="3案まとめて表示")
    args = parser.parse_args()

    if args.all:
        for key, fn in VARIANTS.items():
            fn(args.verbose)
            print("\n" + "=" * 70 + "\n")
    else:
        VARIANTS[args.variant](args.verbose)


if __name__ == "__main__":
    main()
