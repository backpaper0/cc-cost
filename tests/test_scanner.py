from __future__ import annotations

import datetime as dt
from pathlib import Path

from cc_cost.periods import PeriodRanges
from cc_cost.scanner import ProjectKey, find_sessions, scan_all, scan_session

from .conftest import assistant_entry, write_session

NOW = dt.datetime(2026, 10, 16, 12, 0).astimezone()
TS = "2026-10-16T01:00:00.000Z"
SID_A = "aaaaaaaa-1111-4111-8111-111111111111"
SID_B = "bbbbbbbb-2222-4222-8222-222222222222"


def _this_month_output(root: Path, project: str = "-proj") -> int:
    result, _ = scan_all([root], PeriodRanges.for_now(NOW))
    return result[ProjectKey(project)]["this_month"]["claude-sonnet-5"]["output"]


def test_same_request_in_main_and_subagent_is_counted_once(tmp_path: Path):
    write_session(
        tmp_path,
        "-proj",
        SID_A,
        main=[assistant_entry("req_dup", TS, output_tokens=100)],
        subagents={"agent-x": [assistant_entry("req_dup", TS, output_tokens=4, is_sidechain=True)]},
    )

    assert _this_month_output(tmp_path) == 100


def test_main_log_wins_over_subagent_snapshot_regardless_of_file_names(tmp_path: Path):
    # サブエージェント側の複製は出力トークンが途中値のスナップショット。メインログの値を採用する。
    write_session(
        tmp_path,
        "-proj",
        SID_A,
        main=[assistant_entry("req_dup", TS, output_tokens=2089)],
        subagents={"agent-zzz": [assistant_entry("req_dup", TS, output_tokens=4, is_sidechain=True)]},
    )

    session = find_sessions([tmp_path], SID_A)[0]
    usage = scan_session(session, [])
    assert usage.models["claude-sonnet-5"]["output"] == 2089


def test_same_request_in_different_sessions_is_counted_separately(tmp_path: Path):
    write_session(tmp_path, "-proj", SID_A, main=[assistant_entry("req_same", TS, output_tokens=10)])
    write_session(tmp_path, "-proj", SID_B, main=[assistant_entry("req_same", TS, output_tokens=20)])

    assert _this_month_output(tmp_path) == 30


def test_last_line_wins_within_a_file(tmp_path: Path):
    write_session(
        tmp_path,
        "-proj",
        SID_A,
        main=[assistant_entry("req_1", TS, output_tokens=1), assistant_entry("req_1", TS, output_tokens=50)],
    )

    assert _this_month_output(tmp_path) == 50


def test_scan_session_includes_subagents_and_time_range(tmp_path: Path):
    write_session(
        tmp_path,
        "-proj",
        SID_A,
        main=[
            assistant_entry("req_1", "2026-10-01T00:05:00.000Z", output_tokens=10),
            assistant_entry("req_3", "2026-10-01T02:30:59.000Z", output_tokens=30),
        ],
        subagents={"agent-x": [assistant_entry("req_2", "2026-10-01T01:00:00.000Z", output_tokens=20)]},
    )

    session = find_sessions([tmp_path], SID_A)[0]
    usage = scan_session(session, [])

    assert usage.models["claude-sonnet-5"]["output"] == 60
    assert usage.first_at == dt.datetime(2026, 10, 1, 9, 5).astimezone()
    assert usage.last_at == dt.datetime(2026, 10, 1, 11, 30, 59).astimezone()


def test_find_sessions_matches_by_prefix_across_roots_and_projects(tmp_path: Path):
    root1, root2 = tmp_path / "r1", tmp_path / "r2"
    write_session(root1, "-p1", SID_A, main=[])
    write_session(root2, "-p2", SID_B, main=[])

    assert [(s.root, s.dir_name, s.session_id) for s in find_sessions([root1, root2], "aaaa")] == [
        (root1, "-p1", SID_A)
    ]
    assert len(find_sessions([root1, root2], "")) == 2
    assert find_sessions([root1, root2], "cccc") == []


def test_find_sessions_returns_each_root_separately_for_same_full_id(tmp_path: Path):
    root1, root2 = tmp_path / "r1", tmp_path / "r2"
    write_session(root1, "-p", SID_A, main=[])
    write_session(root2, "-p", SID_A, main=[])

    assert [s.root for s in find_sessions([root1, root2], SID_A)] == [root1, root2]
