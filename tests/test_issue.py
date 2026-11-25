from tracker.issue import issue_body
from tracker.moves import TOP_N, compare


def row(date, item_id, price):
    return {"date": date, "item_id": item_id, "item": item_id.upper(), "price_usd": price}


STATUS = {"run_time": "2026-11-26T14:07:00Z", "items": 3, "days_with_success": 2,
          "sources": [{"name": "coingecko", "ok": True, "count": 2}, {"name": "kraken", "ok": False, "count": 0}]}


def test_issue_lists_top_moves_with_old_and_new_values_and_changes():
    history = [row("2026-11-25", f"i{n:02}", 100.0) for n in range(15)] + [row("2026-11-25", "gone", 1.0)]
    history += [row("2026-11-26", f"i{n:02}", 100.0 + n) for n in range(15)] + [row("2026-11-26", "new", 1.0)]
    body = issue_body(compare(history, "2026-11-26"), STATUS)
    assert "previous run on 2026-11-25" in body
    assert "| 1 | I14 (`i14`) | $100.00 | $114.00 | +14.00% |" in body
    assert body.count("| $100.00 |") == TOP_N  # only the top N moves are listed
    assert "`i04`" not in body
    assert "## Appeared (1)" in body and "- NEW (`new`)" in body
    assert "## Disappeared (1)" in body and "- GONE (`gone`)" in body
    assert "| kraken | no | 0 |" in body


def test_issue_on_first_run_and_on_a_day_without_changes():
    first = issue_body(compare([row("2026-11-25", "a", 1.0)], "2026-11-25"), STATUS)
    assert "first run" in first
    same = issue_body(compare([row("2026-11-25", "a", 1.0), row("2026-11-26", "a", 1.0)], "2026-11-26"), STATUS)
    assert "| 1 | A (`a`) | $1.00 | $1.00 | +0.00% |" in same
    assert "## Appeared (0)" in same and "## Disappeared (0)" in same
