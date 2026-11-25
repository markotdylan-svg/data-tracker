"""History logic: building from raw files, failed sources, and a second run on the same day."""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from tracker.build import build_history, read_history, write_history
from tracker.convert import COLUMNS
from tracker.fetch import read_raw, write_raw
from tracker.run import run

from .conftest import coingecko_reply, kraken_reply

D1 = datetime(2026, 11, 25, 14, 7, tzinfo=timezone.utc)
D1_LATER = datetime(2026, 11, 25, 22, 30, tzinfo=timezone.utc)
D2 = datetime(2026, 11, 26, 14, 7, tzinfo=timezone.utc)


def read_csv(path: Path) -> list[list[str]]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def test_raw_file_keeps_the_reply_unchanged(tmp_path):
    raw = coingecko_reply({"bitcoin": 1.0})
    write_raw(raw, tmp_path / "x.json.gz")
    assert read_raw(tmp_path / "x.json.gz") == raw


def test_history_columns_order_and_sorting(tmp_path, make_getter):
    getter = make_getter({"coingecko": coingecko_reply({"solana": 70.0, "bitcoin": 60000.0}),
                          "kraken": kraken_reply({"XXBTZUSD": 60010.0})})
    run(tmp_path, D2, getter=getter, issue=False)
    run(tmp_path, D1, getter=getter, issue=False)  # an older date added later still sorts first
    rows = read_csv(tmp_path / "history.csv")
    assert rows[0] == COLUMNS
    assert rows[0][:4] == ["date", "item_id", "item", "source"]
    keys = [(r[0], r[1]) for r in rows[1:]]
    assert keys == sorted(keys)
    assert keys == [
        ("2026-11-25", "coingecko:btc"), ("2026-11-25", "coingecko:sol"), ("2026-11-25", "kraken:btc"),
        ("2026-11-26", "coingecko:btc"), ("2026-11-26", "coingecko:sol"), ("2026-11-26", "kraken:btc"),
    ]


def test_missing_values_are_empty_cells(tmp_path, make_getter):
    run(tmp_path, D1, getter=make_getter({"coingecko": coingecko_reply({"bitcoin": 1.0}),
                                          "kraken": kraken_reply({"XXBTZUSD": 1.0})}), issue=False)
    kraken = [r for r in read_csv(tmp_path / "history.csv")[1:] if r[3] == "kraken"][0]
    row = dict(zip(COLUMNS, kraken))
    assert row["market_cap_usd"] == "" and row["market_cap_rank"] == "" and row["change_24h_pct"] == ""


def test_failed_source_writes_no_raw_file_and_run_goes_on(tmp_path, make_getter):
    getter = make_getter({"coingecko": RuntimeError("HTTP 429"), "kraken": kraken_reply({"XXBTZUSD": 1.0})})
    status = run(tmp_path, D1, getter=getter, issue=False)
    assert sorted(p.name for p in (tmp_path / "raw" / "2026-11-25").iterdir()) == ["kraken.json.gz"]
    assert status["sources"] == [{"name": "coingecko", "ok": False, "count": 0},
                                 {"name": "kraken", "ok": True, "count": 1}]
    assert {r["source"] for r in read_history(tmp_path / "history.csv")} == {"kraken"}
    log = json.loads((tmp_path / "runs" / "2026-11-25.json").read_text())
    assert "HTTP 429" in log["sources"][0]["error"]


def test_reply_without_tracked_items_counts_as_failed(tmp_path, make_getter):
    getter = make_getter({"coingecko": b"[]", "kraken": kraken_reply({"XXBTZUSD": 1.0})})
    status = run(tmp_path, D1, getter=getter, issue=False)
    assert status["sources"][0] == {"name": "coingecko", "ok": False, "count": 0}
    assert not (tmp_path / "raw" / "2026-11-25" / "coingecko.json.gz").exists()


def test_day_with_no_raw_file_for_a_source_has_no_rows_from_it(tmp_path, make_getter):
    run(tmp_path, D1, getter=make_getter({"coingecko": coingecko_reply({"bitcoin": 1.0}),
                                          "kraken": kraken_reply({"XXBTZUSD": 1.0})}), issue=False)
    status = run(tmp_path, D2, getter=make_getter({"coingecko": coingecko_reply({"bitcoin": 2.0}),
                                                   "kraken": RuntimeError("down")}), issue=False)
    h = read_history(tmp_path / "history.csv")
    assert [(r["date"], r["item_id"]) for r in h] == [
        ("2026-11-25", "coingecko:btc"), ("2026-11-25", "kraken:btc"), ("2026-11-26", "coingecko:btc")]
    assert status["gone_today"] == ["kraken:btc"]
    assert status["new_today"] == []


def test_second_run_same_day_replaces_that_days_raw_files_and_rows(tmp_path, make_getter):
    run(tmp_path, D1, getter=make_getter({"coingecko": coingecko_reply({"bitcoin": 1.0, "solana": 1.0}),
                                          "kraken": kraken_reply({"XXBTZUSD": 1.0})}), issue=False)
    # later the same UTC day: Kraken fails and CoinGecko returns a new price
    status = run(tmp_path, D1_LATER, getter=make_getter({"coingecko": coingecko_reply({"bitcoin": 5.0}),
                                                         "kraken": RuntimeError("down")}), issue=False)
    assert sorted(p.name for p in (tmp_path / "raw" / "2026-11-25").iterdir()) == ["coingecko.json.gz"]
    h = read_history(tmp_path / "history.csv")
    assert [(r["date"], r["item_id"], r["price_usd"]) for r in h] == [("2026-11-25", "coingecko:btc", 5.0)]
    assert status["days_with_success"] == 1  # the day counts once
    assert status["run_time"] == "2026-11-25T22:30:00Z"
    assert status["items"] == 1


def test_second_run_same_day_compares_with_the_previous_day(tmp_path, make_getter):
    g1 = make_getter({"coingecko": coingecko_reply({"bitcoin": 100.0}), "kraken": kraken_reply({})})
    run(tmp_path, D1, getter=g1, issue=False)
    run(tmp_path, D2, getter=make_getter({"coingecko": coingecko_reply({"bitcoin": 110.0}),
                                          "kraken": kraken_reply({})}), issue=False)
    status = run(tmp_path, datetime(2026, 11, 26, 20, 0, tzinfo=timezone.utc),
                 getter=make_getter({"coingecko": coingecko_reply({"bitcoin": 120.0}), "kraken": kraken_reply({})}),
                 issue=False)
    from tracker.moves import compare
    c = compare(read_history(tmp_path / "history.csv"), "2026-11-26")
    assert c["previous_date"] == "2026-11-25"
    assert c["moves"][0]["old"] == 100.0 and c["moves"][0]["new"] == 120.0
    assert status["days_with_success"] == 2


def test_rebuild_from_raw_files_reproduces_history(tmp_path, make_getter):
    run(tmp_path, D1, getter=make_getter({"coingecko": coingecko_reply({"bitcoin": 1.5, "shiba-inu": 3.59e-06}),
                                          "kraken": kraken_reply({"XXBTZUSD": 1.0})}), issue=False)
    run(tmp_path, D2, getter=make_getter({"coingecko": coingecko_reply({"bitcoin": 2.25}),
                                          "kraken": kraken_reply({"XDGUSD": 0.05})}), issue=False)
    first = (tmp_path / "history.csv").read_bytes()
    write_history(build_history(tmp_path / "raw"), tmp_path / "history.csv")
    assert (tmp_path / "history.csv").read_bytes() == first


def test_status_file_keys(tmp_path, make_getter):
    run(tmp_path, D1, getter=make_getter({"coingecko": coingecko_reply({"bitcoin": 1.0}),
                                          "kraken": kraken_reply({"XXBTZUSD": 1.0})}), issue=False)
    status = run(tmp_path, D2, getter=make_getter({"coingecko": coingecko_reply({"bitcoin": 1.0, "solana": 1.0}),
                                                   "kraken": kraken_reply({"XXBTZUSD": 1.0})}), issue=False)
    saved = json.loads((tmp_path / "status.json").read_text())
    assert saved == status
    assert list(saved) == ["run_time", "first_run_date", "days_with_success", "items",
                           "new_today", "gone_today", "sources"]
    assert saved["first_run_date"] == "2026-11-25"
    assert saved["days_with_success"] == 2
    assert saved["items"] == 3
    assert saved["new_today"] == ["coingecko:sol"]
    assert saved["gone_today"] == []
    assert all(set(s) == {"name", "ok", "count"} for s in saved["sources"])
