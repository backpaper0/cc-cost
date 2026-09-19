"""使用量(トークン数)の集計単位。dictベースにして、合算をシンプルな要素ごとの加算にする。"""

from __future__ import annotations

Usage = dict[str, int]

USAGE_KEYS = ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")


def zero_usage() -> Usage:
    return {k: 0 for k in USAGE_KEYS}


def add_usage(a: Usage, b: Usage) -> Usage:
    return {k: a.get(k, 0) + b.get(k, 0) for k in USAGE_KEYS}


def usage_from_api_usage(api_usage: dict) -> Usage:
    """セッションログの1件の `message.usage` から Usage を組み立てる。

    `cache_creation`(5分TTL/1時間TTLの内訳)が無い古い形式のログは、
    issue #4 の決定により全額5分TTL書込として扱う。
    """
    cache_creation = api_usage.get("cache_creation")
    if cache_creation:
        cache_write_5m = cache_creation.get("ephemeral_5m_input_tokens", 0) or 0
        cache_write_1h = cache_creation.get("ephemeral_1h_input_tokens", 0) or 0
    else:
        cache_write_5m = api_usage.get("cache_creation_input_tokens", 0) or 0
        cache_write_1h = 0

    return {
        "input": api_usage.get("input_tokens", 0) or 0,
        "output": api_usage.get("output_tokens", 0) or 0,
        "cache_write_5m": cache_write_5m,
        "cache_write_1h": cache_write_1h,
        "cache_read": api_usage.get("cache_read_input_tokens", 0) or 0,
    }


def web_search_requests_from_api_usage(api_usage: dict) -> int:
    """`message.usage.server_tool_use.web_search_requests` を取り出す。

    web_search はトークン課金とは別建てで従量課金($10/1,000リクエスト)されるが、
    usageオブジェクトにはトークンと同じ粒度でリクエスト回数が乗っているだけなので、
    5種類のトークンとは別の並行したカウンタとして扱う。
    """
    server_tool_use = api_usage.get("server_tool_use")
    if not isinstance(server_tool_use, dict):
        return 0
    return server_tool_use.get("web_search_requests", 0) or 0
