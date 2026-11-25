import json

import pytest

from tracker.convert import COLUMNS, convert_coingecko, convert_kraken
from tracker.sources import COINGECKO_IDS, KRAKEN_PAIRS

from .conftest import coingecko_reply, kraken_reply


def test_coingecko_rows_have_common_columns_and_values():
    rows = convert_coingecko(coingecko_reply({"bitcoin": 60000.0, "ethereum": 1700.0}), "2026-11-25")
    assert len(rows) == 2  # the untracked coin is dropped
    btc = next(r for r in rows if r["item_id"] == "coingecko:btc")
    assert list(btc) == COLUMNS
    assert btc["date"] == "2026-11-25"
    assert btc["item"] == "Bitcoin"
    assert btc["source"] == "coingecko"
    assert btc["symbol"] == "BTC"
    assert btc["category"] == "Currency"
    assert btc["price_usd"] == 60000.0
    assert btc["change_24h_pct"] == 1.5
    assert btc["high_24h_usd"] == pytest.approx(66000.0)
    assert btc["low_24h_usd"] == pytest.approx(54000.0)
    assert btc["volume_24h_usd"] == 600000.0
    assert btc["market_cap_usd"] == 60000000.0
    assert btc["market_cap_rank"] == 1


def test_coingecko_missing_values_are_none():
    raw = json.dumps([{"id": "bitcoin", "current_price": None, "total_volume": "n/a"}]).encode()
    (row,) = convert_coingecko(raw, "2026-11-25")
    assert row["price_usd"] is None
    assert row["volume_24h_usd"] is None
    assert row["market_cap_rank"] is None


def test_coingecko_error_reply_raises():
    with pytest.raises(ValueError):
        convert_coingecko(json.dumps({"status": {"error_code": 429}}).encode(), "2026-11-25")


def test_every_tracked_coingecko_id_converts():
    rows = convert_coingecko(coingecko_reply({cid: 1.0 for cid in COINGECKO_IDS}), "2026-11-25")
    assert sorted(r["item_id"] for r in rows) == sorted(f"coingecko:{s}" for s in COINGECKO_IDS.values())


def test_kraken_rows_have_common_columns_and_values():
    rows = convert_kraken(kraken_reply({"XXBTZUSD": 60000.0, "SOLUSD": 70.0, "OTHERUSD": 1.0}), "2026-11-25")
    assert len(rows) == 2  # the untracked pair is dropped
    btc = next(r for r in rows if r["item_id"] == "kraken:btc")
    assert list(btc) == COLUMNS
    assert btc["item"] == "Bitcoin (Kraken BTC/USD)"
    assert btc["source"] == "kraken"
    assert btc["symbol"] == "BTC"
    assert btc["price_usd"] == 60000.0
    assert btc["high_24h_usd"] == pytest.approx(66000.0)   # h[1], the 24-hour high
    assert btc["low_24h_usd"] == pytest.approx(54000.0)    # l[1], the 24-hour low
    assert btc["volume_24h_usd"] == round(20.0 * 60000.0 * 0.99, 2)  # v[1] * p[1]
    # Kraken reports no 24-hour change, market cap or rank
    assert btc["change_24h_pct"] is None
    assert btc["market_cap_usd"] is None
    assert btc["market_cap_rank"] is None


def test_every_tracked_kraken_pair_converts():
    rows = convert_kraken(kraken_reply({key: 1.0 for key, _ in KRAKEN_PAIRS.values()}), "2026-11-25")
    assert sorted(r["item_id"] for r in rows) == sorted(f"kraken:{s}" for _, s in KRAKEN_PAIRS.values())


def test_kraken_error_reply_raises():
    with pytest.raises(ValueError):
        convert_kraken(json.dumps({"error": ["EGeneral:Too many requests"]}).encode(), "2026-11-25")
