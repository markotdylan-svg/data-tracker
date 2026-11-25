import json

import pytest


def coingecko_reply(prices: dict[str, float], extra_untracked: bool = True) -> bytes:
    """A CoinGecko /coins/markets reply for the given {coingecko id: price}."""
    coins = []
    for i, (cid, price) in enumerate(prices.items(), 1):
        coins.append({
            "id": cid, "symbol": "x", "name": cid.title(), "current_price": price,
            "market_cap": price * 1000, "market_cap_rank": i, "total_volume": price * 10,
            "high_24h": price * 1.1, "low_24h": price * 0.9, "price_change_percentage_24h": 1.5,
        })
    if extra_untracked:
        coins.append({"id": "not-tracked-coin", "symbol": "ntc", "current_price": 1.0})
    return json.dumps(coins).encode()


def kraken_reply(prices: dict[str, float]) -> bytes:
    """A Kraken Ticker reply for the given {kraken result key: last price}."""
    result = {}
    for key, p in prices.items():
        result[key] = {
            "a": [str(p), "1", "1.000"], "b": [str(p), "1", "1.000"], "c": [str(p), "0.5"],
            "v": ["10.0", "20.0"], "p": [str(p), str(p * 0.99)], "t": [5, 9],
            "l": [str(p * 0.95), str(p * 0.9)], "h": [str(p * 1.05), str(p * 1.1)], "o": str(p * 0.98),
        }
    return json.dumps({"error": [], "result": result}).encode()


@pytest.fixture
def make_getter():
    """Build a fake http_get: maps a source name to bytes, or to an exception to raise."""
    from tracker.sources import SOURCE_BY_NAME

    def factory(replies: dict):
        by_url = {SOURCE_BY_NAME[name].url: reply for name, reply in replies.items()}

        def getter(url):
            reply = by_url[url]
            if isinstance(reply, Exception):
                raise reply
            return reply
        return getter
    return factory
