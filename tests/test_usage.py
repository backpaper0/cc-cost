from cc_cost.usage import web_search_requests_from_api_usage


def test_web_search_requests_from_api_usage_reads_server_tool_use_count() -> None:
    api_usage = {
        "input_tokens": 100,
        "output_tokens": 50,
        "server_tool_use": {"web_search_requests": 3, "web_fetch_requests": 1},
    }

    assert web_search_requests_from_api_usage(api_usage) == 3


def test_web_search_requests_from_api_usage_defaults_to_zero_when_absent() -> None:
    api_usage = {"input_tokens": 100, "output_tokens": 50}

    assert web_search_requests_from_api_usage(api_usage) == 0
