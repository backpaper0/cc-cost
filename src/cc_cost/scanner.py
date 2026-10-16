"""セッションログ(`<ログルート>/<project-dir>/` 配下の `*.jsonl`)を走査し、
セッション単位で重複排除したAPI呼び出しのusageを集計する。

集計アルゴリズムは issue #3(セッションログのusage集計ルールの調査)と issue #7 の結論に基づく:
- usage を持ちうるのは `type == "assistant"` の行のみ。
- 同一の `requestId`(無ければ `message.id`、それも無ければ行の `uuid`)を持つ複数行は、
  同一API呼び出しの重複(完全複製、または出力トークンのみ増加する途中スナップショット)
  であり、最後に出現したログエントリのusageだけを1回計上する。
- 重複排除は「セッション内」で行う。セッションは、メインログ `<session-uuid>.jsonl` と、
  同名ディレクトリ配下のログ(サイドチェーンを記録した `<session-uuid>/subagents/agent-*.jsonl`)
  の集合である。セッションをまたいだキーの一致は信用しない(別々に計上する)。
- 複数ファイルにまたがる場合の「最後」は、同名ディレクトリ配下のログをパス順に読み、
  メインログを最後に読む順序で決める。実データでは、サイドチェーンを開始したAPI呼び出しが
  サイドチェーンのログの先頭にも複製されることがあり、その複製は出力トークンが途中値の
  スナップショットだった(メインログ側が確定値)。メインログを最後に読むことで確定値が採用される。
- サイドチェーン(`isSidechain: true`)も課金対象として集計に含める(docs/adr/0002)。

複数ログルート対応(docs/adr/0004-multiple-log-roots.md)により、走査対象のログルートは
複数ありうる。ルートをまたいで同名のプロジェクトディレクトリが存在しても、常に別プロジェクト
として扱い、usageを合算することはしない(単に同じ名前を名乗る別の作業ディレクトリの可能性が
あるため)。表示上の衝突を避けるため、その場合のみ `ProjectKey.collision_suffix` にルートの
識別情報を付与する。同じセッションIDが複数のルートにあっても、別セッションとして扱う。
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from collections.abc import Iterable
from pathlib import Path

from .periods import PeriodRanges
from .usage import Usage, add_usage, usage_from_api_usage, zero_usage


@dataclasses.dataclass(frozen=True)
class ProjectKey:
    """プロジェクトを一意に識別するキー。

    `dir_name` はプロジェクトグループの正規表現マッチに使う元のディレクトリ名。
    `collision_suffix` は、同名のディレクトリが複数のログルートに存在する場合のみ
    設定される表示用のルート識別情報(例: `[/path/to/root]`)。
    """

    dir_name: str
    collision_suffix: str | None = None


# ProjectKey -> period_key -> model -> Usage
UsageByProjectPeriodModel = dict[ProjectKey, dict[str, dict[str, Usage]]]


@dataclasses.dataclass(frozen=True)
class SessionLog:
    """1つのセッションを構成するセッションログ(JSONL)の集合。

    `paths` は重複排除で読む順序に並んでいる(同名ディレクトリ配下のログをパス順、メインログを最後)。
    """

    root: Path
    dir_name: str
    session_id: str
    paths: tuple[Path, ...]

    def last_modified(self) -> dt.datetime:
        return max(dt.datetime.fromtimestamp(p.stat().st_mtime).astimezone() for p in self.paths)


@dataclasses.dataclass(frozen=True)
class SessionUsage:
    """セッション内で重複排除した、モデル別のusageと最初/最後のAPI呼び出しの日時。"""

    models: dict[str, Usage]
    first_at: dt.datetime | None
    last_at: dt.datetime | None


def _parse_timestamp(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def _scan_jsonl_file(
    path: Path, last_by_key: dict[str, tuple[str, dt.datetime, Usage]], warnings: list[str]
) -> None:
    """1ファイルを読み、API呼び出しのキーごとに (model, ローカル日時, Usage) を `last_by_key` へ上書きする。"""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        warnings.append(f"{path}: 読み込みに失敗しました({e})")
        return

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

        # 同一キーが複数回現れた場合は、後から出現したログエントリで上書きする
        # (ファイル内では最後のログエントリが常に最終確定usageを持つことを実データで確認済み。
        # ファイルをまたぐ場合の順序はモジュールdocstringを参照)。
        last_by_key[key] = (model, timestamp.astimezone(), usage)


def _scan_session_calls(session: SessionLog, warnings: list[str]) -> list[tuple[str, dt.datetime, Usage]]:
    """セッション内で重複排除したAPI呼び出しの (model, ローカル日時, Usage) のリストを返す。"""
    last_by_key: dict[str, tuple[str, dt.datetime, Usage]] = {}
    for path in session.paths:
        _scan_jsonl_file(path, last_by_key, warnings)
    return list(last_by_key.values())


def scan_session(session: SessionLog, warnings: list[str]) -> SessionUsage:
    """1つのセッション(サイドチェーン込み)のusageを、期間で分けずに合計する。"""
    models: dict[str, Usage] = {}
    timestamps: list[dt.datetime] = []
    for model, local_ts, usage in _scan_session_calls(session, warnings):
        models[model] = add_usage(models.get(model, zero_usage()), usage)
        timestamps.append(local_ts)
    return SessionUsage(
        models=models,
        first_at=min(timestamps, default=None),
        last_at=max(timestamps, default=None),
    )


def _sessions_in_project(root: Path, project_dir: Path) -> list[SessionLog]:
    """プロジェクトディレクトリ内のセッションを、セッションIDの順に返す。"""
    main_by_id: dict[str, Path] = {}
    nested_by_id: dict[str, list[Path]] = {}
    for entry in project_dir.iterdir():
        if entry.is_file() and entry.suffix == ".jsonl":
            main_by_id[entry.stem] = entry
        elif entry.is_dir():
            nested = sorted(entry.rglob("*.jsonl"))
            if nested:
                nested_by_id[entry.name] = nested

    sessions = []
    for session_id in sorted(main_by_id.keys() | nested_by_id.keys()):
        # 重複排除で後勝ちにするため、メインログを最後に並べる
        main = [main_by_id[session_id]] if session_id in main_by_id else []
        paths = (*nested_by_id.get(session_id, []), *main)
        sessions.append(SessionLog(root=root, dir_name=project_dir.name, session_id=session_id, paths=paths))
    return sessions


def _project_dirs(root: Path) -> list[Path]:
    return sorted(p for p in root.iterdir() if p.is_dir())


def find_sessions(roots: list[Path], prefix: str) -> list[SessionLog]:
    """セッションIDが `prefix` で始まるセッションを、全ログルート・全プロジェクトから探す。"""
    return [
        session
        for root in roots
        for project_dir in _project_dirs(root)
        for session in _sessions_in_project(root, project_dir)
        if session.session_id.startswith(prefix)
    ]


def _project_keys(projects: Iterable[tuple[Path, str]]) -> dict[tuple[Path, str], ProjectKey]:
    """(ログルート, ディレクトリ名) ごとの ProjectKey を返す。

    同名のディレクトリが複数のルートにある場合のみ、`collision_suffix` にルートのパスを付ける。
    """
    projects = list(projects)
    dir_name_counts: dict[str, int] = {}
    for _root, dir_name in projects:
        dir_name_counts[dir_name] = dir_name_counts.get(dir_name, 0) + 1
    return {
        (root, dir_name): ProjectKey(
            dir_name=dir_name, collision_suffix=f"[{root}]" if dir_name_counts[dir_name] > 1 else None
        )
        for root, dir_name in projects
    }


def _scan_project(
    root: Path, project_dir: Path, period_ranges: PeriodRanges, warnings: list[str]
) -> dict[str, dict[str, Usage]]:
    """1つのプロジェクトを走査し、period_key -> model -> Usage を返す。"""
    project_totals: dict[str, dict[str, Usage]] = {}
    for session in _sessions_in_project(root, project_dir):
        for model, local_ts, usage in _scan_session_calls(session, warnings):
            for period_key in period_ranges.periods_for(local_ts.date()):
                period_bucket = project_totals.setdefault(period_key, {})
                period_bucket[model] = add_usage(period_bucket.get(model, zero_usage()), usage)
    return project_totals


def project_key_for_session(session: SessionLog, roots: list[Path], period_ranges: PeriodRanges) -> ProjectKey:
    """セッションが属するプロジェクトの ProjectKey を、期間別集計(`scan_all`)と同じ基準で返す。

    名前の衝突は、期間内に使用量を持つ同名のプロジェクトが他のログルートにあるかどうかで判定する。
    全体を走査せずに済むよう、同名のプロジェクトだけを走査する。
    """
    others = [
        (root, session.dir_name)
        for root in roots
        if root != session.root
        and (root / session.dir_name).is_dir()
        and _scan_project(root, root / session.dir_name, period_ranges, [])
    ]
    return _project_keys([(session.root, session.dir_name), *others])[(session.root, session.dir_name)]


def _scan_root(root: Path, period_ranges: PeriodRanges, warnings: list[str]) -> dict[str, dict[str, dict[str, Usage]]]:
    """1つのログルートを走査し、dir_name -> period_key -> model -> Usage を返す。"""
    by_dir_name: dict[str, dict[str, dict[str, Usage]]] = {}
    for project_dir in _project_dirs(root):
        project_totals = _scan_project(root, project_dir, period_ranges, warnings)
        if project_totals:
            by_dir_name[project_dir.name] = project_totals
    return by_dir_name


def scan_all(roots: list[Path], period_ranges: PeriodRanges) -> tuple[UsageByProjectPeriodModel, list[str]]:
    """複数のログルートを走査する。各ルートは呼び出し側で存在確認済みであること。"""
    warnings: list[str] = []
    per_root = [(root, _scan_root(root, period_ranges, warnings)) for root in roots]

    keys = _project_keys((root, dir_name) for root, by_dir_name in per_root for dir_name in by_dir_name)

    result: UsageByProjectPeriodModel = {}
    for root, by_dir_name in per_root:
        for dir_name, project_totals in by_dir_name.items():
            result[keys[(root, dir_name)]] = project_totals

    return result, warnings
