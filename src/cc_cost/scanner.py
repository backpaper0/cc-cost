"""セッションログ(`$HOME/.claude/projects/**/*.jsonl`)を走査し、
プロジェクト×期間×モデルごとのトークン使用量を集計する。

集計アルゴリズムは issue #3(セッションログのusage集計ルールの調査)の結論に基づく:
- usage を持ちうるのは `type == "assistant"` の行のみ。
- 同一の `requestId`(無ければ `message.id`、それも無ければ行の `uuid`)を持つ複数行は、
  同一API呼び出しの重複(完全複製、または出力トークンのみ増加する途中スナップショット)
  であり、ファイル内で最後に出現した行のusageだけを1回計上する。
- dedupは必ず「同一ファイル内」に限定する(ファイルをまたいだrequestId一致を信用しない)。
- サイドチェーン(`isSidechain: true`)は別ファイル(`subagents/agent-*.jsonl`)に分離されて
  いるため、ファイルごとの結果を単純合算するだけで二重計上・欠落なく扱える。
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .periods import PeriodRanges
from .usage import Usage, add_usage, usage_from_api_usage, zero_usage

# project_dir_name -> period_key -> model -> Usage
UsageByProjectPeriodModel = dict[str, dict[str, dict[str, Usage]]]


def _parse_timestamp(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def _scan_jsonl_file(path: Path, warnings: list[str]) -> list[tuple[str, dt.datetime, Usage]]:
    """1ファイルをdedupし、(model, ローカル日時, Usage) のリストを返す。"""
    last_by_key: dict[str, tuple[str, dt.datetime, Usage]] = {}

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        warnings.append(f"{path}: 読み込みに失敗しました({e})")
        return []

    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            warnings.append(f"{path}:{lineno}: JSONとして解析できない行をスキップしました({e})")
            continue

        if not isinstance(entry, dict) or entry.get("type") != "assistant":
            continue

        message = entry.get("message")
        if not isinstance(message, dict):
            continue

        api_usage = message.get("usage")
        if not isinstance(api_usage, dict):
            continue

        key = entry.get("requestId") or message.get("id") or entry.get("uuid")
        if key is None:
            continue

        timestamp = _parse_timestamp(entry.get("timestamp"))
        if timestamp is None:
            continue

        model = message.get("model") or "unknown"
        usage = usage_from_api_usage(api_usage)

        # 同一キーが複数回現れた場合は、後から出現した行で上書きする
        # (ファイル内で最後の行が常に最終確定usageを持つことを実データで確認済み)。
        last_by_key[key] = (model, timestamp.astimezone(), usage)

    return list(last_by_key.values())


def scan_all(projects_root: Path, period_ranges: PeriodRanges) -> tuple[UsageByProjectPeriodModel, list[str]]:
    warnings: list[str] = []
    result: UsageByProjectPeriodModel = {}

    for project_dir in sorted(p for p in projects_root.iterdir() if p.is_dir()):
        project_totals: dict[str, dict[str, Usage]] = {}

        for jsonl_path in sorted(project_dir.rglob("*.jsonl")):
            for model, local_ts, usage in _scan_jsonl_file(jsonl_path, warnings):
                for period_key in period_ranges.periods_for(local_ts.date()):
                    period_bucket = project_totals.setdefault(period_key, {})
                    period_bucket[model] = add_usage(period_bucket.get(model, zero_usage()), usage)

        if project_totals:
            result[project_dir.name] = project_totals

    return result, warnings
