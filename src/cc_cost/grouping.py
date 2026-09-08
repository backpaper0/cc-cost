"""プロジェクトディレクトリを設定ファイルのパターンでグルーピングし、
表示順序(パターン定義順、マッチしないものは末尾にアルファベット順)を決める。
"""

from __future__ import annotations

from .config import Config
from .scanner import UsageByProjectPeriodModel
from .usage import Usage, add_usage


def resolve_group_name(project_dir_name: str, config: Config) -> tuple[int | None, str]:
    """(マッチしたパターンのインデックス, グループ名) を返す。マッチしなければ (None, フォールバック名)。"""
    for index, group in enumerate(config.project_groups):
        m = group.pattern.search(project_dir_name)
        if m:
            name = group.name
            for i, value in enumerate(m.groups(), start=1):
                name = name.replace(f"\\{i}", value or "")
            return index, name

    if project_dir_name.startswith("-"):
        return None, project_dir_name.replace("-", "/")
    return None, project_dir_name


def group_projects(
    usage_by_project: UsageByProjectPeriodModel, config: Config
) -> list[tuple[str, dict[str, dict[str, Usage]]]]:
    """project_dir単位のusageを、グループ名でマージした上で表示順に並べる。"""
    merged: dict[str, dict[str, dict[str, Usage]]] = {}
    order_key: dict[str, tuple[int, str]] = {}
    num_patterns = len(config.project_groups)

    for project_dir_name, periods in usage_by_project.items():
        matched_index, group_name = resolve_group_name(project_dir_name, config)
        key = (matched_index if matched_index is not None else num_patterns, group_name)
        order_key[group_name] = min(order_key.get(group_name, key), key)

        bucket = merged.setdefault(group_name, {})
        for period_key, models in periods.items():
            period_bucket = bucket.setdefault(period_key, {})
            for model, usage in models.items():
                period_bucket[model] = add_usage(period_bucket.get(model, {}), usage)

    ordered_names = sorted(merged.keys(), key=lambda name: order_key[name])
    return [(name, merged[name]) for name in ordered_names]
