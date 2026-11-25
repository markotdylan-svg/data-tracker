"""Write data/status.json, which describes the latest run."""

import json
from pathlib import Path

from .build import raw_days


def make_status(history: list[dict], raw_dir: Path, run_time: str, changes: dict, results: list[dict]) -> dict:
    days = raw_days(raw_dir)
    return {
        "run_time": run_time,                                  # UTC, ISO 8601
        "first_run_date": days[0][0] if days else None,         # date of the earliest raw file
        "days_with_success": len(days),                         # different dates with a raw file
        "items": sum(r["date"] == changes["date"] for r in history),  # items in the latest run
        "new_today": [a["item_id"] for a in changes["appeared"]],
        "gone_today": [d["item_id"] for d in changes["disappeared"]],
        "sources": [{"name": r["name"], "ok": r["ok"], "count": r["count"]} for r in results],
    }


def write_status(status: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(status, f, indent=2)
        f.write("\n")
