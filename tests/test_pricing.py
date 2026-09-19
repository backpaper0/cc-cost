from cc_cost.config import Config
from cc_cost.pricing import web_search_cost_usd


def _config(web_search_price_per_1k_requests: float | None) -> Config:
    return Config(
        usd_to_jpy=150.0,
        project_groups=[],
        models={},
        roots=[],
        web_search_price_per_1k_requests=web_search_price_per_1k_requests,
    )


def test_web_search_cost_usd_computes_from_request_count_and_price() -> None:
    config = _config(web_search_price_per_1k_requests=10.0)

    assert web_search_cost_usd(2000, config) == 20.0


def test_web_search_cost_usd_is_none_when_price_not_configured() -> None:
    config = _config(web_search_price_per_1k_requests=None)

    assert web_search_cost_usd(2000, config) is None
