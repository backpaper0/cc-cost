import datetime as dt
import json
from pathlib import Path

from cc_cost.periods import PeriodRanges
from cc_cost.scanner import scan_all


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")


def _assistant_entry(request_id: str, timestamp: dt.datetime, web_search_requests: int) -> dict:
    return {
        "type": "assistant",
        "requestId": request_id,
        "timestamp": timestamp.isoformat(),
        "message": {
            "model": "claude-sonnet-5",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "server_tool_use": {"web_search_requests": web_search_requests},
            },
        },
    }


def test_scan_all_aggregates_web_search_requests_per_project_and_period(tmp_path: Path) -> None:
    now = dt.datetime.now().astimezone()
    root = tmp_path / "root"
    _write_jsonl(
        root / "-home-dev-project" / "session1.jsonl",
        [_assistant_entry("req-1", now, web_search_requests=3)],
    )

    period_ranges = PeriodRanges.for_now(now)
    _usage, web_search_by_project, warnings = scan_all([root], period_ranges)

    assert warnings == []
    ((_project_key, periods),) = web_search_by_project.items()
    assert periods["today"] == 3


def test_scan_all_sums_web_search_requests_across_multiple_entries(tmp_path: Path) -> None:
    now = dt.datetime.now().astimezone()
    root = tmp_path / "root"
    _write_jsonl(
        root / "-home-dev-project" / "session1.jsonl",
        [
            _assistant_entry("req-1", now, web_search_requests=3),
            _assistant_entry("req-2", now, web_search_requests=2),
        ],
    )

    period_ranges = PeriodRanges.for_now(now)
    _usage, web_search_by_project, _warnings = scan_all([root], period_ranges)

    ((_project_key, periods),) = web_search_by_project.items()
    assert periods["today"] == 5
