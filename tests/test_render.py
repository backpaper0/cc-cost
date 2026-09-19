import pytest

from cc_cost.config import Config, ModelPricing
from cc_cost.render import render


def _config(web_search_price_per_1k_requests: float | None) -> Config:
    return Config(
        usd_to_jpy=150.0,
        project_groups=[],
        models={"claude-sonnet-5": ModelPricing(input=2.0, output=10.0, cache_write_5m=2.5, cache_write_1h=4.0, cache_read=0.2)},
        roots=[],
        web_search_price_per_1k_requests=web_search_price_per_1k_requests,
    )


def _today_line(output: str) -> str:
    (line,) = [line for line in output.splitlines() if "本日" in line]
    return line


def test_render_shows_existing_total_and_combined_total_with_web_search(capsys: pytest.CaptureFixture[str]) -> None:
    config = _config(web_search_price_per_1k_requests=10.0)
    grouped = [
        (
            "my-project",
            {"today": {"claude-sonnet-5": {"input": 500_000, "output": 0, "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 0}}},
            {"today": 10},
        )
    ]

    render(grouped, config, verbose=False, use_color=False)

    line = _today_line(capsys.readouterr().out)
    assert "$1.00 (¥150)" in line
    assert "$1.10 (¥165)" in line


def test_render_shows_unknown_combined_total_when_web_search_price_not_configured(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(web_search_price_per_1k_requests=None)
    grouped = [
        (
            "my-project",
            {"today": {"claude-sonnet-5": {"input": 500_000, "output": 0, "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 0}}},
            {"today": 10},
        )
    ]

    render(grouped, config, verbose=False, use_color=False)

    line = _today_line(capsys.readouterr().out)
    assert "$1.00 (¥150)" in line
    assert "不明" in line


def test_render_verbose_shows_independent_web_search_row(capsys: pytest.CaptureFixture[str]) -> None:
    config = _config(web_search_price_per_1k_requests=10.0)
    grouped = [
        (
            "my-project",
            {"today": {"claude-sonnet-5": {"input": 500_000, "output": 0, "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 0}}},
            {"today": 10},
        )
    ]

    render(grouped, config, verbose=True, use_color=False)

    web_search_lines = [line for line in capsys.readouterr().out.splitlines() if line.strip().startswith("Web検索")]
    (line,) = web_search_lines
    assert "10" in line
    assert "$0.10 (¥15)" in line
