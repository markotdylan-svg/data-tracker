import pytest

from tracker.moves import compare, previous_date


def row(date, item_id, price):
    return {"date": date, "item_id": item_id, "item": item_id.upper(), "price_usd": price}


def test_first_run_has_no_previous_and_everything_appeared():
    history = [row("2026-11-25", "a", 1.0), row("2026-11-25", "b", 2.0)]
    c = compare(history, "2026-11-25")
    assert c["previous_date"] is None
    assert c["moves"] == []
    assert [a["item_id"] for a in c["appeared"]] == ["a", "b"]
    assert c["disappeared"] == []


def test_move_is_percent_change_since_previous_run_ranked_by_size():
    history = [
        row("2026-11-25", "a", 100.0), row("2026-11-25", "b", 10.0), row("2026-11-25", "c", 50.0),
        row("2026-11-26", "a", 103.0), row("2026-11-26", "b", 8.0), row("2026-11-26", "c", 50.0),
    ]
    c = compare(history, "2026-11-26")
    assert c["previous_date"] == "2026-11-25"
    assert [m["item_id"] for m in c["moves"]] == ["b", "a", "c"]  # |-20%| > |+3%| > 0%
    b = c["moves"][0]
    assert (b["old"], b["new"]) == (10.0, 8.0)
    assert b["move_pct"] == pytest.approx(-20.0)
    assert c["moves"][1]["move_pct"] == pytest.approx(3.0)


def test_previous_run_skips_days_without_rows():
    history = [row("2026-11-25", "a", 100.0), row("2026-11-28", "a", 110.0)]
    assert previous_date(history, "2026-11-28") == "2026-11-25"
    assert compare(history, "2026-11-28")["moves"][0]["move_pct"] == pytest.approx(10.0)


def test_appeared_and_disappeared_items():
    history = [
        row("2026-11-25", "a", 1.0), row("2026-11-25", "gone", 1.0),
        row("2026-11-26", "a", 1.0), row("2026-11-26", "new", 1.0),
    ]
    c = compare(history, "2026-11-26")
    assert [a["item_id"] for a in c["appeared"]] == ["new"]
    assert [d["item_id"] for d in c["disappeared"]] == ["gone"]
    assert [m["item_id"] for m in c["moves"]] == ["a"]


def test_missing_or_zero_prices_are_not_moves():
    history = [
        row("2026-11-25", "a", None), row("2026-11-25", "b", 0.0), row("2026-11-25", "c", 1.0),
        row("2026-11-26", "a", 5.0), row("2026-11-26", "b", 5.0), row("2026-11-26", "c", None),
    ]
    assert compare(history, "2026-11-26")["moves"] == []


def test_ties_are_broken_by_item_id():
    history = [row("2026-11-25", "b", 10.0), row("2026-11-25", "a", 10.0),
               row("2026-11-26", "b", 11.0), row("2026-11-26", "a", 9.0)]
    assert [m["item_id"] for m in compare(history, "2026-11-26")["moves"]] == ["a", "b"]
