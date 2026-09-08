"""config.toml の読み込みと、不在時のデフォルト設定ファイル自動生成。

スキーマは issue #4(config.tomlスキーマとusage集計ロジック方針の決定)で確定したもの。
単価は issue #2(Anthropic料金体系の調査)の結果を初期値として埋め込む。
複数ログルート対応は docs/adr/0004-multiple-log-roots.md の決定に基づく。
"""

from __future__ import annotations

import dataclasses
import os
import re
import tomllib
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "cc-cost" / "config.toml"


def resolve_default_root() -> Path:
    """デフォルトのログルートを返す。

    Claude Code 自体が `.claude` ディレクトリ全体の場所を変える
    `CLAUDE_CONFIG_DIR` 環境変数を尊重する(未設定なら `$HOME/.claude`)。
    """
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(config_dir) if config_dir else Path.home() / ".claude"
    return base / "projects"


# 出典: https://platform.claude.com/docs/en/about-claude/pricing (確認日: 2026-09-09)
# 単位: USD / 1,000,000 トークン
DEFAULT_CONFIG_TOML = """\
# cc-cost 設定ファイル(初回実行時に自動生成されました)
# 必要に応じて書き換えてください。

# デフォルトのログルート($CLAUDE_CONFIG_DIR/projects、未設定なら $HOME/.claude/projects)
# に加えてスキャンしたい追加のログルート(絶対パス)。トップレベルのキーなので、
# 必ずどの [section] よりも前に書くこと。
# CLAUDE_CONFIG_DIR を切り替えて複数の .claude を使い分けている場合などに使う。
#
# roots = ["/path/to/another/.claude/projects"]

[exchange_rate]
# USD -> JPY 換算レート
usd_to_jpy = 150.0

# ログルート配下のディレクトリ名にマッチする正規表現(Pythonのre.searchで判定)。
# 定義した順に評価し、最初にマッチしたグループに割り当てる。
# name 側では \\1 のようにキャプチャグループを参照できる。
# どのパターンにもマッチしないプロジェクトは、ディレクトリ名を読みやすいパス形式
# (先頭の "-" を "/" に変換したもの)に変換した名前がそのままグループ名になる。
#
# 例:
# [[project_groups]]
# pattern = "^-home-dev-workspace-cc-cost$"
# name = "cc-cost"

# モデルごとの単価(USD / 1,000,000 トークン)。
# 出典: https://platform.claude.com/docs/en/about-claude/pricing (確認日: 2026-09-09)

[models.claude-sonnet-5]
input = 2.00
output = 10.00
cache_write_5m = 2.50
cache_write_1h = 4.00
cache_read = 0.20

[models.claude-opus-5]
input = 5.00
output = 25.00
cache_write_5m = 6.25
cache_write_1h = 10.00
cache_read = 0.50

[models.claude-fable-5-1]
input = 10.00
output = 50.00
cache_write_5m = 12.50
cache_write_1h = 20.00
cache_read = 0.25

[models."claude-haiku-4-5-20251001"]
input = 1.00
output = 5.00
cache_write_5m = 1.25
cache_write_1h = 2.00
cache_read = 0.10
"""


@dataclasses.dataclass(frozen=True)
class ModelPricing:
    input: float
    output: float
    cache_write_5m: float
    cache_write_1h: float
    cache_read: float


@dataclasses.dataclass(frozen=True)
class ProjectGroup:
    pattern: re.Pattern[str]
    name: str


@dataclasses.dataclass(frozen=True)
class Config:
    usd_to_jpy: float
    project_groups: list[ProjectGroup]
    models: dict[str, ModelPricing]
    roots: list[Path]


def ensure_config_file(path: Path) -> bool:
    """設定ファイルが無ければデフォルト値で作成する。作成した場合True を返す。"""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
    return True


def load_config(path: Path) -> Config:
    ensure_config_file(path)

    with path.open("rb") as f:
        data = tomllib.load(f)

    usd_to_jpy = float(data.get("exchange_rate", {}).get("usd_to_jpy", 0.0))

    project_groups = [
        ProjectGroup(pattern=re.compile(g["pattern"]), name=g["name"])
        for g in data.get("project_groups", [])
    ]

    models = {
        model_id: ModelPricing(
            input=float(m["input"]),
            output=float(m["output"]),
            cache_write_5m=float(m["cache_write_5m"]),
            cache_write_1h=float(m["cache_write_1h"]),
            cache_read=float(m["cache_read"]),
        )
        for model_id, m in data.get("models", {}).items()
    }

    roots: list[Path] = []
    seen_roots: set[Path] = set()
    for raw_root in [resolve_default_root(), *(Path(r) for r in data.get("roots", []))]:
        root = raw_root.expanduser()
        if root not in seen_roots:
            seen_roots.add(root)
            roots.append(root)

    return Config(usd_to_jpy=usd_to_jpy, project_groups=project_groups, models=models, roots=roots)
