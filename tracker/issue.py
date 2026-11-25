"""Open (or update) the daily GitHub Issue and close the previous day's issue.

The issue is titled with the run date (YYYY-MM-DD). It lists the TOP_N items
whose price moved the most since the previous run (see moves.py) with the old
and new price, every item that appeared or disappeared, and the status of each
source. It is opened every day, even when nothing changed. A second run on the
same day edits that day's issue instead of opening a new one.
"""

import json
import os
import re
import urllib.request

from .moves import TOP_N

API = "https://api.github.com"
DATE_TITLE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def money(v: float) -> str:
    if v >= 1:
        return f"${v:,.2f}"
    return f"${v:.8g}"


def issue_body(changes: dict, status: dict, site_url: str = "") -> str:
    prev = changes["previous_date"]
    lines = [f"Run at {status['run_time']}. Compared with the previous run on {prev}." if prev
             else f"Run at {status['run_time']}. This is the first run, so there is nothing to compare with yet.", ""]
    lines += ["## Sources", "", "| Source | OK | Items |", "|---|---|---|"]
    lines += [f"| {s['name']} | {'yes' if s['ok'] else 'no'} | {s['count']} |" for s in status["sources"]]
    lines += ["", f"Items today: {status['items']} · days with a successful run: {status['days_with_success']}", ""]

    top = changes["moves"][:TOP_N]
    lines += [f"## Biggest moves (top {TOP_N} by |% change in price_usd| since the previous run)", ""]
    if top:
        lines += ["| # | Item | Old price | New price | Change |", "|---|---|---|---|---|"]
        lines += [f"| {i} | {m['item']} (`{m['item_id']}`) | {money(m['old'])} | {money(m['new'])} | {m['move_pct']:+.2f}% |"
                  for i, m in enumerate(top, 1)]
    else:
        lines.append("No moves: no item has a price on both this run and a previous run.")
    lines.append("")

    for heading, key in (("Appeared", "appeared"), ("Disappeared", "disappeared")):
        rows = changes[key]
        lines += [f"## {heading} ({len(rows)})", ""]
        lines += [f"- {r['item']} (`{r['item_id']}`)" for r in rows] or ["None."]
        lines.append("")
    if site_url:
        lines.append(f"Site: {site_url}")
    return "\n".join(lines)


class GitHub:
    def __init__(self, repo: str, token: str):
        self.repo, self.token = repo, token

    def call(self, method: str, path: str, body: dict | None = None):
        req = urllib.request.Request(
            f"{API}/repos/{self.repo}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "data-tracker",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read()
            return json.loads(text) if text else None

    def date_issues(self, state: str) -> list[dict]:
        out, page = [], 1
        while True:
            items = self.call("GET", f"/issues?state={state}&per_page=100&page={page}")
            out += [i for i in items if "pull_request" not in i and DATE_TITLE.match(i["title"])]
            if len(items) < 100:
                return out
            page += 1


def publish_issue(changes: dict, status: dict, repo: str, token: str, site_url: str = "") -> int:
    gh = GitHub(repo, token)
    date = changes["date"]
    body = issue_body(changes, status, site_url)
    existing = [i for i in gh.date_issues("all") if i["title"] == date]
    if existing:
        number = existing[0]["number"]
        gh.call("PATCH", f"/issues/{number}", {"body": body, "state": "open"})
    else:
        number = gh.call("POST", "/issues", {"title": date, "body": body})["number"]
    for i in gh.date_issues("open"):
        if i["number"] != number and i["title"] < date:
            gh.call("PATCH", f"/issues/{i['number']}", {"state": "closed", "state_reason": "completed"})
    return number


def publish_from_env(changes: dict, status: dict) -> int | None:
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        print("GITHUB_REPOSITORY/GITHUB_TOKEN not set; skipping the issue")
        return None
    owner, name = repo.split("/")
    return publish_issue(changes, status, repo, token, f"https://{owner.lower()}.github.io/{name}/")
