"""cc-cost CLIのエントリポイント(issue #6で決定したオプション/引数、`--session` は issue #7)。"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from importlib import metadata
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, Config, load_config
from .grouping import group_projects, readable_dir_name, resolve_group_name
from .periods import PeriodRanges
from .render import render, render_session
from .scanner import SessionLog, find_sessions, project_key_for_session, scan_all, scan_session


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
    parser.add_argument(
        "--session",
        metavar="ID",
        help="指定したセッション(サイドチェーン込み)の合計コストを表示する(セッションIDの前方一致)",
    )
    parser.add_argument("--version", action="store_true", help="バージョンを表示して終了する")
    return parser


def _resolve_use_color(no_color_flag: bool) -> bool:
    if no_color_flag:
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    return sys.stdout.isatty()


def _print_candidates(prefix: str, sessions: list[SessionLog]) -> None:
    print(f"セッションID '{prefix}' に一致するセッションが複数あります:", file=sys.stderr)
    show_root = len({s.root for s in sessions}) > 1
    for session in sessions:
        line = (
            f"    {session.session_id}  {readable_dir_name(session.dir_name)}  "
            f"{session.last_modified().strftime('%Y-%m-%d %H:%M')}"
        )
        if show_root:
            line += f"  [{session.root}]"
        print(line, file=sys.stderr)


def _run_session(prefix: str, roots: list[Path], config: Config, verbose: bool, use_color: bool) -> int:
    sessions = find_sessions(roots, prefix)
    if not sessions:
        print(f"セッションID '{prefix}' に一致するセッションが見つかりません", file=sys.stderr)
        return 1
    if len(sessions) > 1:
        # 同じ全桁IDが複数のログルートにある場合も合算せず、候補として示す(docs/adr/0004)
        _print_candidates(prefix, sessions)
        return 1

    session = sessions[0]
    warnings: list[str] = []
    session_usage = scan_session(session, warnings)
    for warning in warnings:
        print(f"警告: {warning}", file=sys.stderr)

    _index, group_name = resolve_group_name(project_key_for_session(session, roots), config)
    render_session(group_name, session.session_id, session_usage, config, verbose=verbose, use_color=use_color)
    return 0


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

    if args.session is not None:
        return _run_session(args.session, existing_roots, config, verbose=args.verbose, use_color=use_color)

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
