/* All the numbers the site shows, computed in the browser from the two data files.
   Pure functions only (no DOM), so the same code can be checked outside a browser. */

var NUMERIC = ["price_usd", "change_24h_pct", "high_24h_usd", "low_24h_usd",
               "volume_24h_usd", "market_cap_usd", "market_cap_rank"];
var COLUMN_LABELS = {
  price_usd: "Price (USD)",
  change_24h_pct: "24h change (%)",
  high_24h_usd: "24h high (USD)",
  low_24h_usd: "24h low (USD)",
  volume_24h_usd: "24h volume (USD)",
  market_cap_usd: "Market cap (USD)",
  market_cap_rank: "Market cap rank",
};
var TOP_N = 10;
var STABLECOINS = ["usdt", "usdc"];

/* ---------- CSV ---------- */

function parseCSV(text) {
  var rows = [], row = [], field = "", i = 0, q = false;
  while (i < text.length) {
    var c = text[i];
    if (q) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; } else { q = false; }
      } else { field += c; }
    } else if (c === '"') { q = true; }
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); rows.push(row); row = []; field = "";
    } else { field += c; }
    i++;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  var head = rows.shift() || [];
  return rows.filter(function (r) { return r.length === head.length; }).map(function (r) {
    var o = {};
    head.forEach(function (h, j) {
      var v = r[j];
      o[h] = NUMERIC.indexOf(h) >= 0 ? (v === "" ? null : Number(v)) : v;
    });
    return o;
  });
}

/* ---------- basics ---------- */

function uniqueDates(rows) {
  var s = {};
  rows.forEach(function (r) { s[r.date] = true; });
  return Object.keys(s).sort();
}

function rowsOn(rows, date) {
  return rows.filter(function (r) { return r.date === date; });
}

function indexBy(rows) {
  var m = {};
  rows.forEach(function (r) { m[r.item_id] = r; });
  return m;
}

function cmp(a, b) { return a < b ? -1 : a > b ? 1 : 0; }

function previousDate(rows, date) {
  var prev = null;
  rows.forEach(function (r) { if (r.date < date && (prev === null || r.date > prev)) prev = r.date; });
  return prev;
}

function pctChange(oldV, newV) {
  if (oldV === null || newV === null || oldV === 0) return null;
  return (newV - oldV) / oldV * 100;
}

/* The move rule (same as tracker/moves.py): percent change of price_usd since the
   previous run, ranked by its absolute size, ties broken by item_id. */
function compare(rows, date) {
  var prev = previousDate(rows, date);
  var today = indexBy(rowsOn(rows, date));
  var before = prev ? indexBy(rowsOn(rows, prev)) : {};
  var moves = [];
  Object.keys(today).sort().forEach(function (id) {
    if (!before[id]) return;
    var oldV = before[id].price_usd, newV = today[id].price_usd;
    var m = pctChange(oldV, newV);
    if (m === null) return;
    moves.push({ item_id: id, item: today[id].item, old: oldV, new: newV, move_pct: m });
  });
  moves.sort(function (a, b) { return (Math.abs(b.move_pct) - Math.abs(a.move_pct)) || cmp(a.item_id, b.item_id); });
  var appeared = Object.keys(today).filter(function (id) { return !before[id]; }).sort();
  var disappeared = Object.keys(before).filter(function (id) { return !today[id]; }).sort();
  return { date: date, previous_date: prev, moves: moves, appeared: appeared, disappeared: disappeared,
           today: today, before: before };
}

function mean(xs) { return xs.length ? xs.reduce(function (a, b) { return a + b; }, 0) / xs.length : null; }

/* ---------- Trends findings ---------- */

/* 1. Change in price_usd from each CoinGecko coin's first day to the latest day. */
function sinceFirstRun(rows) {
  var dates = uniqueDates(rows);
  var first = dates[0], last = dates[dates.length - 1];
  var cg = rows.filter(function (r) { return r.source === "coingecko"; });
  var ids = {};
  cg.forEach(function (r) { ids[r.item_id] = true; });
  var out = [];
  Object.keys(ids).sort().forEach(function (id) {
    var series = cg.filter(function (r) { return r.item_id === id && r.price_usd !== null; });
    if (series.length < 2) return;
    var a = series[0], b = series[series.length - 1];
    if (a.date === b.date) return;
    out.push({ item_id: id, item: b.item, symbol: b.symbol, first_date: a.date, last_date: b.date,
               first: a.price_usd, last: b.price_usd, change_pct: pctChange(a.price_usd, b.price_usd) });
  });
  out.sort(function (x, y) { return (y.change_pct - x.change_pct) || cmp(x.item_id, y.item_id); });
  return { first_date: first, last_date: last, days: dates.length, coins: out };
}

/* 2. For each run after the first: the mean absolute move of CoinGecko coins (the
   move rule applied to every coin), and the coin that moved the most that day. */
function dailyMoves(rows) {
  var dates = uniqueDates(rows);
  var cg = rows.filter(function (r) { return r.source === "coingecko"; });
  var out = [];
  dates.slice(1).forEach(function (d) {
    var c = compare(cg, d);
    if (!c.moves.length) return;
    out.push({ date: d, previous_date: c.previous_date, coins: c.moves.length,
               mean_abs_move_pct: mean(c.moves.map(function (m) { return Math.abs(m.move_pct); })),
               up: c.moves.filter(function (m) { return m.move_pct > 0; }).length,
               down: c.moves.filter(function (m) { return m.move_pct < 0; }).length,
               top: c.moves[0] });
  });
  return out;
}

/* 3. On the latest day with both sources, Kraken's price vs CoinGecko's for the same coin:
   gap_pct = (kraken price - CoinGecko price) / CoinGecko price * 100. */
function sourceGap(rows) {
  var dates = uniqueDates(rows);
  for (var i = dates.length - 1; i >= 0; i--) {
    var day = rowsOn(rows, dates[i]);
    var cg = {}, out = [];
    day.forEach(function (r) { if (r.source === "coingecko") cg[r.symbol] = r; });
    day.forEach(function (r) {
      if (r.source !== "kraken" || !cg[r.symbol]) return;
      var g = pctChange(cg[r.symbol].price_usd, r.price_usd);
      if (g === null) return;
      out.push({ symbol: r.symbol, item: cg[r.symbol].item, coingecko: cg[r.symbol].price_usd,
                 kraken: r.price_usd, gap_pct: g });
    });
    if (out.length) {
      out.sort(function (a, b) { return (Math.abs(b.gap_pct) - Math.abs(a.gap_pct)) || cmp(a.symbol, b.symbol); });
      return { date: dates[i], pairs: out, mean_abs_gap_pct: mean(out.map(function (p) { return Math.abs(p.gap_pct); })) };
    }
  }
  return { date: null, pairs: [], mean_abs_gap_pct: null };
}

/* 4. Bitcoin's share of the summed market cap of the tracked CoinGecko coins, per day:
   share = BTC market_cap_usd / sum of market_cap_usd of CoinGecko rows that day * 100. */
function btcDominance(rows) {
  return uniqueDates(rows).map(function (d) {
    var cg = rowsOn(rows, d).filter(function (r) { return r.source === "coingecko" && r.market_cap_usd !== null; });
    var total = cg.reduce(function (a, r) { return a + r.market_cap_usd; }, 0);
    var btc = cg.filter(function (r) { return r.item_id === "coingecko:btc"; })[0];
    if (!btc || !total) return null;
    return { date: d, btc: btc.market_cap_usd, total: total, coins: cg.length, share_pct: btc.market_cap_usd / total * 100 };
  }).filter(function (x) { return x; });
}

/* 5. Stablecoins: distance of price_usd from $1, |price - 1| * 100 percent, for every
   stablecoin row in the history (both sources). */
function stablecoinPeg(rows) {
  var st = rows.filter(function (r) {
    return STABLECOINS.indexOf(r.symbol.toLowerCase()) >= 0 && r.price_usd !== null;
  }).map(function (r) {
    return { date: r.date, item_id: r.item_id, item: r.item, price: r.price_usd, dev_pct: Math.abs(r.price_usd - 1) * 100 };
  });
  var worst = null;
  st.forEach(function (r) {
    if (!worst || r.dev_pct > worst.dev_pct || (r.dev_pct === worst.dev_pct && (r.date + r.item_id) < (worst.date + worst.item_id))) worst = r;
  });
  return { rows: st, worst: worst, mean_dev_pct: mean(st.map(function (r) { return r.dev_pct; })) };
}

if (typeof module !== "undefined") {
  module.exports = { parseCSV: parseCSV, compare: compare, sinceFirstRun: sinceFirstRun, dailyMoves: dailyMoves,
                     sourceGap: sourceGap, btcDominance: btcDominance, stablecoinPeg: stablecoinPeg };
}
