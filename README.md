# Crypto Tracker

[![Tests](https://github.com/markotdylan-svg/data-tracker/actions/workflows/tests.yml/badge.svg)](https://github.com/markotdylan-svg/data-tracker/actions/workflows/tests.yml)
[![Daily run](https://github.com/markotdylan-svg/data-tracker/actions/workflows/daily.yml/badge.svg)](https://github.com/markotdylan-svg/data-tracker/actions/workflows/daily.yml)

A tool that tracks 23 cryptocurrencies every day. Once a day, GitHub Actions downloads the latest
prices, volumes and market caps from two public sources, adds them to a history with one row per
item per day, opens a GitHub Issue listing what moved, and publishes the result to a website.

**Live site:** https://markotdylan-svg.github.io/data-tracker/

## Build the history file from the raw files

```
uv run python -m tracker.build
```

This reads every `data/raw/<date>/<source>.<format>.gz` file and rewrites `data/history.csv`.
The history depends on the raw files alone: running the build again gives the same file byte for
byte, and a change to a conversion rule applies to every day of the history.

Other commands:

```
uv run python -m tracker.run --no-issue   # the full daily run, without opening the issue
uv run pytest                              # the test suite
```

## Sources

The tool requests only the coins it tracks, and the converters keep only those coins.

| Source | Format | Endpoint | What is kept |
|---|---|---|---|
| `coingecko` | JSON | `https://api.coingecko.com/api/v3/coins/markets` (no key) | The 23 coins in `tracker/sources.py`, requested by CoinGecko id. Of each coin's fields, the history keeps price, 24h change, 24h high and low, 24h volume, market cap and market cap rank. |
| `kraken` | JSON | `https://api.kraken.com/0/public/Ticker` (no key) | The 18 `<coin>/USD` trading pairs in `tracker/sources.py`. Of each ticker, the history keeps the last trade price, the 24-hour high and low, and the 24-hour volume. |

Each reply is saved exactly as it was returned, gzip-compressed, to
`data/raw/<date>/coingecko.json.gz` and `data/raw/<date>/kraken.json.gz`. A source that fails writes
no raw file that day. Failure means a network error, an HTTP error after retries, an error reply,
or a reply that holds none of the tracked items. One failing source does not stop the run. Every
source's result (ok, count, error, time) is recorded in `data/runs/<date>.json` and in
`data/status.json`.

## Items and keys

An item is one coin from one source. Its key, `item_id`, is defined in `tracker/sources.py` as
`<source>:<symbol>`, for example `coingecko:btc` or `kraken:btc`. The symbol is my own key for
the coin, not the symbol the source sends. Each CoinGecko id and each Kraken pair is mapped to it,
so an item lines up from day to day even if a source renames a coin. There are 41 items in all:
23 CoinGecko coins and 18 Kraken pairs.

## Data files

### `data/history.csv`

One row per item per day, sorted by `date` and then `item_id`. A value a source does not report
for an item on a day is left empty.

| Column | Meaning | Unit |
|---|---|---|
| `date` | UTC date of the run that collected the row | `YYYY-MM-DD` |
| `item_id` | The item's key, `<source>:<symbol>` | text |
| `item` | The item's name; Kraken items are named `<coin> (Kraken <SYM>/USD)` | text |
| `source` | The source the row comes from: `coingecko` or `kraken` | text |
| `symbol` | The coin's ticker symbol | text, upper case |
| `category` | My grouping of the coin: Currency, Smart contract platform, Stablecoin, Exchange token, Payments, DeFi, Meme | text |
| `price_usd` | Latest price. CoinGecko: `current_price`. Kraken: last trade price `c[0]` | US dollars |
| `change_24h_pct` | Price change over the last 24 hours, as reported by CoinGecko (`price_change_percentage_24h`). Empty for Kraken, which gives no price from 24 hours earlier | percent |
| `high_24h_usd` | Highest price in the last 24 hours. CoinGecko: `high_24h`. Kraken: `h[1]` | US dollars |
| `low_24h_usd` | Lowest price in the last 24 hours. CoinGecko: `low_24h`. Kraken: `l[1]` | US dollars |
| `volume_24h_usd` | Traded volume in the last 24 hours. CoinGecko: `total_volume` (all exchanges). Kraken: `v[1] × p[1]` (coins traded on Kraken × volume-weighted average price) | US dollars |
| `market_cap_usd` | Market capitalization (CoinGecko `market_cap`). Empty for Kraken | US dollars |
| `market_cap_rank` | Rank by market cap among all coins on CoinGecko. Empty for Kraken | rank, 1 = largest |

### `data/status.json`

Describes the latest run.

| Key | Meaning |
|---|---|
| `run_time` | When the latest run started, UTC, ISO 8601 |
| `first_run_date` | Date of the earliest raw file |
| `days_with_success` | Number of different dates that have a raw file |
| `items` | Number of items (history rows) in the latest run |
| `new_today` | `item_id`s that appeared since the previous run (on the first run, every item) |
| `gone_today` | `item_id`s that disappeared since the previous run |
| `sources` | One entry per source: `name`, `ok` (true or false), `count` (items converted) |

## Move rule

The **previous run** is the latest date before today that has rows in the history. For every item
with a `price_usd` on both dates:

```
move_pct = (price_usd today − price_usd on the previous run) / price_usd on the previous run × 100
```

Items are ranked by the size of the move, `|move_pct|`, largest first, with ties broken by
`item_id`. The daily issue and the Today page list the **10** largest moves, with the old and new
price. An item **appeared** if it has a row today but none on the previous run. It
**disappeared** if it had a row on the previous run but has none today. Both lists are given in
full. The rule is in `tracker/moves.py` and is repeated in the browser in `site/analysis.js`.

## Daily run

`tracker/run.py`, run by `.github/workflows/daily.yml` every day at 14:07 UTC (and on demand):

1. Call every source and save each reply to `data/raw/<date>/<source>.<format>.gz`. `<date>` is
   the UTC date at the moment the run starts.
2. Rebuild `data/history.csv` from all the raw files.
3. Write `data/status.json`.
4. Open a GitHub Issue titled with the date. It lists the 10 biggest moves, everything that
   appeared or disappeared, and the status of each source. The run then closes the previous
   day's issue. An issue is opened every day, even when nothing changed.
5. Commit the raw files, the history file, the status file and the run log.

A second run on the same day deletes and replaces that day's raw files, rebuilds the history and
edits that day's issue, so each day counts once.

## Site

Three pages share one navigation bar, one stylesheet and one set of fonts and colors. They load
`data/history.csv` and `data/status.json` in the browser and do every calculation there.

- **Today** (`index.html`): time of the last run, status of every source, the counts from the
  status file, the latest value of every item with its change since the previous run, and the
  biggest moves.
- **Browse** (`browse.html`): latest values for every item, with filters on source and category,
  a search box for item names, sorting by every numeric column in either direction, and a star
  on every item that adds it to a shortlist. The shortlist is saved in the browser's
  `localStorage` and is still there after a reload.
- **Trends** (`trends.html`): a chart of any numeric value over the days, optionally indexed to
  100, with a picker for which items to show. It has five findings. Each one has a heading that
  states the finding, a paragraph with the numbers and how they are computed from the history
  file, a chart, and a table of the numbers:
  1. which coin rose and which fell the most since the first run;
  2. the day with the biggest market-wide move;
  3. how far apart Kraken and CoinGecko prices are;
  4. Bitcoin's share of the tracked market cap over time;
  5. how close the stablecoins stayed to $1.

The site can be installed as an app. It has a web app manifest and a service worker. Online, every
request goes to the network and the reply is cached. Offline, the site still opens and shows
the last data it loaded.

## Files

| File | What it does |
|---|---|
| `README.md` | This file |
| `pyproject.toml`, `uv.lock`, `.python-version` | Python project: version 3.12, no runtime dependencies, pytest for development |
| `.gitignore`, `.gitattributes` | Files git ignores; LF line endings, and `.gz`/`.png` stored as binary |
| `tracker/__init__.py` | Marks `tracker` as a package |
| `tracker/sources.py` | The tracked coins, their keys and categories, the CoinGecko ids and Kraken pairs, and the two source URLs |
| `tracker/fetch.py` | Downloads a URL with retries; writes and reads the gzip raw files |
| `tracker/convert.py` | Converts each source's raw reply into rows with the common columns; defines the columns |
| `tracker/build.py` | Builds `data/history.csv` from all raw files (`python -m tracker.build`) |
| `tracker/moves.py` | The move rule: previous run, moves, appeared and disappeared items |
| `tracker/status.py` | Builds and writes `data/status.json` |
| `tracker/issue.py` | Opens or updates the dated GitHub Issue and closes the previous one |
| `tracker/run.py` | The daily pipeline (`python -m tracker.run`) |
| `tests/conftest.py` | Fake CoinGecko and Kraken replies and a fake downloader for the tests |
| `tests/test_convert.py` | Conversion of each source to the common columns |
| `tests/test_moves.py` | The move rule |
| `tests/test_history.py` | History logic: sorting, empty values, failed sources, a second run on the same day, rebuild from raw files, status file |
| `tests/test_issue.py` | The text of the daily issue |
| `.github/workflows/daily.yml` | Runs the pipeline every day and commits the data |
| `.github/workflows/tests.yml` | Runs the tests on every push |
| `.github/workflows/pages.yml` | Deploys `site/` plus the two data files to GitHub Pages after every push and every daily run |
| `data/raw/<date>/<source>.json.gz` | Each source's reply for that date, unchanged and compressed |
| `data/history.csv` | The history: one row per item per day |
| `data/status.json` | The latest run |
| `data/runs/<date>.json` | Log of each date's run: every source's result, item count, error and timing |
| `site/index.html` | Today page |
| `site/browse.html` | Browse page |
| `site/trends.html` | Trends page |
| `site/analysis.js` | CSV parsing, the move rule and the Trends calculations, as pure functions |
| `site/common.js` | Data loading, number formatting, SVG charts with tooltips, and service worker registration |
| `site/style.css` | Shared fonts, colors and layout, with light and dark modes |
| `site/manifest.webmanifest` | Web app manifest |
| `site/sw.js` | Service worker for offline use |
| `site/icons/*.png` | App icons (192, 512, maskable 512) |
