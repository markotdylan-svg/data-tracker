"""Convert one source's raw reply into rows with the common history columns.

Each converter takes the raw bytes exactly as the source returned them and the
UTC date of the run, and returns one dict per tracked item. Items the source
returns that are not tracked are dropped. A value the source does not report is
None (written as an empty cell).
"""

import json

from .sources import COIN_BY_SYMBOL, COINGECKO_IDS, KRAKEN_PAIRS

COLUMNS = [
    "date",             # UTC date of the run, YYYY-MM-DD
    "item_id",          # <source>:<symbol>
    "item",             # item name
    "source",           # coingecko or kraken
    "symbol",           # ticker symbol, upper case
    "category",         # my grouping of the coin
    "price_usd",        # last price, USD
    "change_24h_pct",   # price change over the source's 24-hour window, percent
    "high_24h_usd",     # highest price in the 24-hour window, USD
    "low_24h_usd",      # lowest price in the 24-hour window, USD
    "volume_24h_usd",   # traded volume over 24 hours, USD
    "market_cap_usd",   # market capitalization, USD (CoinGecko only)
    "market_cap_rank",  # rank by market cap among all coins (CoinGecko only)
]
NUMERIC = COLUMNS[6:]


def num(x) -> float | None:
    """A number from a JSON value, or None when it is missing or not a number."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _row(date: str, source: str, symbol: str, item: str, **values) -> dict:
    coin = COIN_BY_SYMBOL[symbol]
    row = {c: None for c in COLUMNS}
    row.update(
        date=date,
        item_id=f"{source}:{symbol}",
        item=item,
        source=source,
        symbol=symbol.upper(),
        category=coin.category,
    )
    row.update(values)
    return row


def convert_coingecko(raw: bytes, date: str) -> list[dict]:
    """CoinGecko /coins/markets: a JSON list with one object per coin."""
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("CoinGecko reply is not a list")
    rows = []
    for c in data:
        symbol = COINGECKO_IDS.get(c.get("id"))
        if symbol is None:
            continue
        rank = num(c.get("market_cap_rank"))
        rows.append(_row(
            date, "coingecko", symbol, COIN_BY_SYMBOL[symbol].name,
            price_usd=num(c.get("current_price")),
            change_24h_pct=num(c.get("price_change_percentage_24h")),
            high_24h_usd=num(c.get("high_24h")),
            low_24h_usd=num(c.get("low_24h")),
            volume_24h_usd=num(c.get("total_volume")),
            market_cap_usd=num(c.get("market_cap")),
            market_cap_rank=int(rank) if rank is not None else None,
        ))
    return rows


def convert_kraken(raw: bytes, date: str) -> list[dict]:
    """Kraken /0/public/Ticker: {"error": [...], "result": {pair: ticker}}.

    Ticker fields used (index 1 is the rolling last 24 hours):
      c[0] last trade price, h[1] / l[1] 24-hour high / low,
      v[1] 24-hour volume in the coin, p[1] 24-hour volume-weighted average price.
    volume_24h_usd = v[1] * p[1]. Kraken gives no price from 24 hours ago (its
    "o" is the 00:00 UTC open), so change_24h_pct is left empty, as are the
    market cap columns.
    """
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("result"), dict):
        raise ValueError(f"Kraken reply has no result: {data.get('error') if isinstance(data, dict) else data!r}"[:200])
    result = data["result"]
    rows = []
    for key, symbol in KRAKEN_PAIRS.values():
        t = result.get(key)
        if not isinstance(t, dict):
            continue
        last = num((t.get("c") or [None])[0])
        vol = num((t.get("v") or [None, None])[1])
        vwap = num((t.get("p") or [None, None])[1])
        rows.append(_row(
            date, "kraken", symbol, f"{COIN_BY_SYMBOL[symbol].name} (Kraken {symbol.upper()}/USD)",
            price_usd=last,
            high_24h_usd=num((t.get("h") or [None, None])[1]),
            low_24h_usd=num((t.get("l") or [None, None])[1]),
            volume_24h_usd=round(vol * vwap, 2) if vol is not None and vwap is not None else None,
        ))
    return rows


CONVERTERS = {
    "coingecko": convert_coingecko,
    "kraken": convert_kraken,
}


def convert(source: str, raw: bytes, date: str) -> list[dict]:
    return CONVERTERS[source](raw, date)
