"""Download a source and save its reply, unchanged, as a gzip file."""

import gzip
import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "data-tracker/1.0 (+https://github.com; daily crypto price tracker)"
TIMEOUT = 30
RETRY_CODES = {429, 500, 502, 503, 504}


def http_get(url: str, retries: int = 5, base_delay: float = 5.0) -> bytes:
    """GET a URL and return the body bytes exactly as received.

    Rate-limit and server errors are retried with backoff (honoring
    Retry-After); any other HTTP error is raised at once.
    """
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code not in RETRY_CODES:
                raise
            wait = e.headers.get("Retry-After", "") if e.headers else ""
            delay = min(60.0, float(wait)) if wait.isdigit() else base_delay * 2 ** attempt
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            delay = base_delay * 2 ** attempt
        if attempt < retries - 1:
            time.sleep(delay)
    raise RuntimeError(f"gave up after {retries} attempts: {last_err}")


def write_raw(raw: bytes, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0 keeps the gzip header free of a timestamp
    with open(path, "wb") as f, gzip.GzipFile(fileobj=f, mode="wb", mtime=0) as gz:
        gz.write(raw)


def read_raw(path: Path) -> bytes:
    with gzip.open(path, "rb") as f:
        return f.read()
