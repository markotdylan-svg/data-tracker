"""The daily pipeline. GitHub Actions runs it once a day:

    uv run python -m tracker.run

1. Call every source and save its reply, unchanged and gzip-compressed, to
   data/raw/<date>/<source>.<format>.gz. A source that fails (no reply, an
   error, or a reply with none of the tracked items) writes no raw file, and
   the run goes on. The result of every source is recorded in
   data/runs/<date>.json and in data/status.json.
2. Rebuild data/history.csv from all raw files.
3. Write data/status.json.
4. Open or update the issue for the date and close the previous one.
(5. The workflow commits the data files.)

The date is the UTC date at the moment the run starts. A second run on the same
date replaces that date's raw files, rebuilds the history and updates the issue.
"""

import argparse
import json
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .build import build_history, write_history
from .convert import convert
from .fetch import http_get, write_raw
from .issue import publish_from_env
from .moves import compare
from .sources import SOURCES, Source
from .status import make_status, write_status


def fetch_source(src: Source, date: str, getter=http_get) -> tuple[bytes | None, dict]:
    """Download one source and check that it converts. Never raises."""
    t0 = time.monotonic()
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        raw = getter(src.url)
        count = len(convert(src.name, raw, date))
        if count == 0:
            raise ValueError("reply holds none of the tracked items")
        result = {"ok": True, "count": count, "error": ""}
    except Exception as e:  # one source failing must not stop the run
        raw = None
        result = {"ok": False, "count": 0, "error": f"{type(e).__name__}: {e}"[:300]}
    result.update(name=src.name, format=src.fmt, url=src.url, fetched_at=fetched_at,
                  seconds=round(time.monotonic() - t0, 1))
    return raw, result


def fetch_all(sources: list[Source], data: Path, date: str, getter=http_get) -> list[dict]:
    day_dir = data / "raw" / date
    if day_dir.exists():
        shutil.rmtree(day_dir)  # a second run the same day replaces that day's raw files
    results = []
    for src in sources:
        raw, result = fetch_source(src, date, getter)
        if raw is not None:
            write_raw(raw, day_dir / f"{src.name}.{src.fmt}.gz")
        print(f"{'ok  ' if result['ok'] else 'FAIL'} {src.name:10} {result['count']:4} items "
              f"{result['seconds']:6.1f}s {result['error']}", flush=True)
        results.append(result)
    return results


def run(data: Path, now: datetime, sources: list[Source] = SOURCES, getter=http_get, issue: bool = True) -> dict:
    run_date, run_time = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%dT%H:%M:%SZ")
    results = fetch_all(sources, data, run_date, getter)

    runs_dir = data / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    with open(runs_dir / f"{run_date}.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({"run_time": run_time, "sources": results}, f, indent=2)
        f.write("\n")

    history = build_history(data / "raw")
    write_history(history, data / "history.csv")
    changes = compare(history, run_date)
    status = make_status(history, data / "raw", run_time, changes, results)
    write_status(status, data / "status.json")
    print(f"{run_date}: {sum(r['ok'] for r in results)}/{len(results)} sources ok, {status['items']} items, "
          f"{len(status['new_today'])} new, {len(status['gone_today'])} gone, previous run {changes['previous_date']}")

    if issue:
        try:
            number = publish_from_env(changes, status)
            if number:
                print(f"issue #{number} updated for {run_date}")
        except Exception:
            traceback.print_exc()  # the data is still committed; flag the problem in the log
            print("::warning::could not open the daily issue")
    return status


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the daily data tracker pipeline")
    ap.add_argument("--data", default="data")
    ap.add_argument("--no-issue", action="store_true", help="do not open the GitHub issue")
    args = ap.parse_args(argv)
    run(Path(args.data), datetime.now(timezone.utc), issue=not args.no_issue)
    return 0


if __name__ == "__main__":
    sys.exit(main())
