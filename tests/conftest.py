"""合成のログルートを一時ディレクトリに組み立てるためのヘルパー。"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest


def assistant_entry(
    request_id: str,
    timestamp: str,
    *,
    model: str = "claude-sonnet-5",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read: int = 0,
    is_sidechain: bool = False,
) -> dict:
    return {
        "type": "assistant",
        "requestId": request_id,
        "timestamp": timestamp,
        "isSidechain": is_sidechain,
        "message": {
            "id": f"msg_{request_id}",
            "model": model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_input_tokens": cache_read,
            },
        },
    }


def write_jsonl(path: Path, entries: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return path


def write_session(
    root: Path,
    project: str,
    session_id: str,
    main: list[dict],
    subagents: dict[str, list[dict]] | None = None,
) -> None:
    write_jsonl(root / project / f"{session_id}.jsonl", main)
    for name, entries in (subagents or {}).items():
        write_jsonl(root / project / session_id / "subagents" / f"{name}.jsonl", entries)


@pytest.fixture(autouse=True)
def tokyo_tz(monkeypatch: pytest.MonkeyPatch):
    """表示や期間判定がローカルタイムゾーンに依存するため、テストでは Asia/Tokyo に固定する。"""
    monkeypatch.setenv("TZ", "Asia/Tokyo")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()
