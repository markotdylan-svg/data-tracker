"""The move rule: what moved since the previous run.

The previous run is the latest date before the run date that has rows in the
history. For every item that has a price_usd on both dates, the move is the
percent change of price_usd:

    move_pct = (price today - price on previous run) / price on previous run * 100

Items are ranked by the size of the move, |move_pct|, largest first (ties by
item_id). The issue and the Today page list the TOP_N largest.

An item appeared if it has a row on the run date but not on the previous run;
it disappeared if it had a row on the previous run but not on the run date. On
the very first run there is no previous run, so every item appeared.
"""

TOP_N = 10


def previous_date(history: list[dict], date: str) -> str | None:
    earlier = [r["date"] for r in history if r["date"] < date]
    return max(earlier) if earlier else None


def compare(history: list[dict], date: str) -> dict:
    prev = previous_date(history, date)
    today = {r["item_id"]: r for r in history if r["date"] == date}
    before = {r["item_id"]: r for r in history if r["date"] == prev} if prev else {}

    moves = []
    for item_id in sorted(today.keys() & before.keys()):
        old, new = before[item_id]["price_usd"], today[item_id]["price_usd"]
        if old is None or new is None or old == 0:
            continue
        moves.append({
            "item_id": item_id,
            "item": today[item_id]["item"],
            "old": old,
            "new": new,
            "move_pct": (new - old) / old * 100,
        })
    moves.sort(key=lambda m: (-abs(m["move_pct"]), m["item_id"]))

    return {
        "date": date,
        "previous_date": prev,
        "moves": moves,
        "appeared": [{"item_id": i, "item": today[i]["item"]} for i in sorted(today.keys() - before.keys())],
        "disappeared": [{"item_id": i, "item": before[i]["item"]} for i in sorted(before.keys() - today.keys())],
    }
