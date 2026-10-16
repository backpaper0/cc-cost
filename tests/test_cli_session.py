from __future__ import annotations

import os
from pathlib import Path

import pytest

from cc_cost.cli import main

from .conftest import assistant_entry, write_session

SID = "aaaaaaaa-1111-4111-8111-111111111111"
SID_OTHER = "aaaabbbb-2222-4222-8222-222222222222"

CONFIG = """\
roots = [{extra_root!r}]

[exchange_rate]
usd_to_jpy = 150.0

[[project_groups]]
pattern = "^-home-dev-grouped$"
name = "grouped"

[models.claude-sonnet-5]
input = 2.00
output = 10.00
cache_write_5m = 2.50
cache_write_1h = 4.00
cache_read = 0.20
"""


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """デフォルトのログルート(CLAUDE_CONFIG_DIR 経由)と追加のログルートを持つ合成環境。"""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    default_root = tmp_path / "claude" / "projects"
    extra_root = tmp_path / "extra" / "projects"
    default_root.mkdir(parents=True)
    extra_root.mkdir(parents=True)
    config_path = tmp_path / "config.toml"
    config_path.write_text(CONFIG.format(extra_root=str(extra_root)), encoding="utf-8")
    return default_root, extra_root, config_path


def _run(config_path: Path, *args: str) -> int:
    return main(["--config", str(config_path), "--no-color", *args])


def _write_standard_session(root: Path, project: str = "-home-dev-grouped") -> None:
    write_session(
        root,
        project,
        SID,
        main=[
            # 1,000,000 output tokens = $10.00
            assistant_entry("req_1", "2026-10-01T00:05:00.000Z", output_tokens=1_000_000),
            assistant_entry("req_dup", "2026-10-01T02:30:59.000Z", output_tokens=500_000),
        ],
        subagents={
            "agent-x": [
                # メインログと重複する requestId は1回だけ(メインログ側の値で)計上される
                assistant_entry("req_dup", "2026-10-01T02:30:59.000Z", output_tokens=4, is_sidechain=True),
                # 500,000 output tokens = $5.00
                assistant_entry("req_2", "2026-10-01T01:00:00.000Z", output_tokens=500_000, is_sidechain=True),
            ]
        },
    )


EXPECTED = """\
■ grouped
    セッション: aaaaaaaa-1111-4111-8111-111111111111
    期間      : 2026-10-01 09:05 〜 2026-10-01 11:30
    合計      : $20.00 (¥3,000)
"""


def test_full_id_shows_session_total_including_subagents(env, capsys):
    default_root, _extra, config_path = env
    _write_standard_session(default_root)

    assert _run(config_path, "--session", SID) == 0

    out = capsys.readouterr().out
    assert out == EXPECTED + "\n"


def test_unique_prefix_gives_same_result(env, capsys):
    default_root, _extra, config_path = env
    _write_standard_session(default_root)
    write_session(default_root, "-home-dev-grouped", SID_OTHER, main=[])

    assert _run(config_path, "--session", "aaaaaaaa") == 0
    assert capsys.readouterr().out == EXPECTED + "\n"


def test_session_in_extra_root_with_fallback_name(env, capsys):
    _default, extra_root, config_path = env
    _write_standard_session(extra_root, project="-home-dev-other")

    assert _run(config_path, "--session", SID) == 0
    assert capsys.readouterr().out.splitlines()[0] == "■ /home/dev/other"


def test_fallback_name_gets_root_suffix_on_collision(env, capsys):
    default_root, extra_root, config_path = env
    _write_standard_session(extra_root, project="-home-dev-other")
    write_session(default_root, "-home-dev-other", SID_OTHER, main=[])

    assert _run(config_path, "--session", SID) == 0
    assert capsys.readouterr().out.splitlines()[0] == f"■ /home/dev/other [{extra_root}]"


def test_no_matching_session(env, capsys):
    default_root, _extra, config_path = env
    _write_standard_session(default_root)

    assert _run(config_path, "--session", "zzzz") == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "zzzz" in captured.err


def test_ambiguous_prefix_lists_candidates(env, capsys):
    default_root, _extra, config_path = env
    _write_standard_session(default_root)
    write_session(default_root, "-home-dev-another", SID_OTHER, main=[])
    os.utime(default_root / "-home-dev-another" / f"{SID_OTHER}.jsonl", (0, 1_790_000_000))

    assert _run(config_path, "--session", "aaaa") == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "'aaaa'" in captured.err
    assert SID in captured.err
    assert f"{SID_OTHER}  /home/dev/another  2026-09-21 23:13" in captured.err
    assert str(default_root) not in captured.err


def test_same_full_id_in_two_roots_is_not_merged(env, capsys):
    default_root, extra_root, config_path = env
    _write_standard_session(default_root)
    _write_standard_session(extra_root)

    assert _run(config_path, "--session", SID) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    candidates = [line for line in captured.err.splitlines() if line.startswith(f"    {SID}  ")]
    assert len(candidates) == 2
    assert candidates[0].endswith(f"[{default_root}]")
    assert candidates[1].endswith(f"[{extra_root}]")


def test_verbose_and_unknown_model(env, capsys):
    default_root, _extra, config_path = env
    write_session(
        default_root,
        "-home-dev-grouped",
        SID,
        main=[
            assistant_entry("req_1", "2026-10-01T00:05:00.000Z", output_tokens=1_000_000),
            assistant_entry("req_2", "2026-10-01T00:06:00.000Z", model="mystery-model", output_tokens=10),
        ],
    )

    assert _run(config_path, "--session", SID, "--verbose") == 0
    out = capsys.readouterr().out
    assert "    合計      : $10.00 (¥1,500) (一部不明を含む)\n" in out
    assert "        claude-sonnet-5 " in out
    assert "out=1,000,000" in out
    assert "        mystery-model " in out
    assert "不明\n" in out
    assert "⚠ mystery-model は単価テーブルに未登録です" in out
