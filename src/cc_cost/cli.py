"""cc-cost CLIのエントリポイント(issue #6で決定したオプション/引数)。"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from importlib import metadata
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, load_config
from .grouping import group_projects
from .periods import PeriodRanges
from .render import render
from .scanner import scan_all


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cc-cost",
        description="Claude Code のセッションログから使用コスト(USD/JPY)を算出して表示する",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"設定ファイルのパス(デフォルト: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument("--verbose", action="store_true", help="モデル別のトークン内訳を表示する")
    parser.add_argument("--no-color", action="store_true", help="色付き出力を無効化する")
    parser.add_argument("--version", action="store_true", help="バージョンを表示して終了する")
    return parser


def _resolve_use_color(no_color_flag: bool) -> bool:
    if no_color_flag:
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    return sys.stdout.isatty()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        try:
            version = metadata.version("cc-cost")
        except metadata.PackageNotFoundError:
            version = "unknown"
        print(f"cc-cost {version}")
        return 0

    use_color = _resolve_use_color(args.no_color)

    try:
        config = load_config(args.config)
    except Exception as e:  # noqa: BLE001 - CLIの最終防衛ラインとして意図的に広く捕捉
        print(f"設定ファイルの読み込みに失敗しました: {args.config} ({e})", file=sys.stderr)
        return 1

    existing_roots = [root for root in config.roots if root.is_dir()]
    for root in config.roots:
        if root not in existing_roots:
            print(f"警告: ログルートが見つかりません: {root}", file=sys.stderr)
    if not existing_roots:
        print(f"ログディレクトリが見つかりません: {', '.join(str(r) for r in config.roots)}", file=sys.stderr)
        return 1

    now = dt.datetime.now().astimezone()
    period_ranges = PeriodRanges.for_now(now)

    usage_by_project, warnings = scan_all(existing_roots, period_ranges)
    for warning in warnings:
        print(f"警告: {warning}", file=sys.stderr)

    grouped = group_projects(usage_by_project, config)
    render(grouped, config, verbose=args.verbose, use_color=use_color)
    return 0


if __name__ == "__main__":
    sys.exit(main())
