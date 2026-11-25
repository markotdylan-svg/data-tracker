"""Build data/history.csv from the raw files alone.

    uv run python -m tracker.build

For each date folder in data/raw/ (oldest first), each raw file
<source>.<format>.gz is converted to one row per item with the common columns.
A date with no raw file for a source has no rows from that source. Rows are
sorted by date, then item_id. The same raw files always give the same file.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

from .convert import COLUMNS, CONVERTERS, convert
from .fetch import read_raw

DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def raw_days(raw_dir: Path) -> list[tuple[str, list[Path]]]:
    """(date, raw files) for every date folder holding at least one raw file of a known source."""
    days = []
    if not raw_dir.is_dir():
        return days
    for d in sorted(p for p in raw_dir.iterdir() if p.is_dir() and DATE_DIR.match(p.name)):
        files = sorted(f for f in d.glob("*.gz") if f.name.split(".")[0] in CONVERTERS)
        if files:
            days.append((d.name, files))
    return days


def build_history(raw_dir: Path) -> list[dict]:
    rows = []
    for date, files in raw_days(raw_dir):
        for f in files:
            rows += convert(f.name.split(".")[0], read_raw(f), date)
    rows.sort(key=lambda r: (r["date"], r["item_id"]))
    return rows


def fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() and abs(v) < 1e15 else repr(v)
    return str(v)


def write_history(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([fmt(r[c]) for c in COLUMNS])


def read_history(path: Path) -> list[dict]:
    """Read history.csv back; numeric cells become floats, empty cells None."""
    from .convert import NUMERIC

    out = []
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            for c in NUMERIC:
                r[c] = float(r[c]) if r[c] != "" else None
            out.append(r)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build data/history.csv from data/raw/")
    ap.add_argument("--data", default="data")
    args = ap.parse_args(argv)
    data = Path(args.data)
    rows = build_history(data / "raw")
    write_history(rows, data / "history.csv")
    print(f"wrote {len(rows)} rows for {len({r['date'] for r in rows})} days to {data / 'history.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
