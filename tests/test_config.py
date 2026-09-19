from pathlib import Path

from cc_cost.config import load_config


def _write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_config_reads_web_search_price(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
        [exchange_rate]
        usd_to_jpy = 150.0

        [server_tools.web_search]
        price_per_1k_requests = 10.0
        """,
    )

    config = load_config(path)

    assert config.web_search_price_per_1k_requests == 10.0


def test_load_config_defaults_web_search_price_to_none_when_absent(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        """
        [exchange_rate]
        usd_to_jpy = 150.0
        """,
    )

    config = load_config(path)

    assert config.web_search_price_per_1k_requests is None


def test_default_generated_config_includes_web_search_price(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"

    config = load_config(path)

    assert config.web_search_price_per_1k_requests == 10.0
