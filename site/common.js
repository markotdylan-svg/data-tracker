/* Shared by every page: loading the data files, formatting, charts, offline support. */

/* ---------- data ---------- */

function loadData() {
  // The service worker answers these from the network when online and from its
  // cache (the last data loaded) when offline.
  return Promise.all([
    fetch("data/history.csv", { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("history.csv: HTTP " + r.status); return r.text();
    }),
    fetch("data/status.json", { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("status.json: HTTP " + r.status); return r.json();
    }),
  ]).then(function (res) {
    var rows = parseCSV(res[0]);
    var status = res[1];
    showRunInNav(status);
    return { rows: rows, status: status };
  });
}

function showLoadError(err) {
  var main = document.querySelector("main");
  var div = document.createElement("div");
  div.className = "card";
  div.innerHTML = "<h2>Could not load the data</h2><p class='muted'></p>";
  div.querySelector("p").textContent = String(err && err.message || err) +
    (navigator.onLine ? "" : " — you are offline and this page has not loaded the data before.");
  main.prepend(div);
}

/* ---------- formatting ---------- */

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

function fmtUSD(v) {
  if (v === null || v === undefined || isNaN(v)) return "—";
  var a = Math.abs(v);
  if (a >= 1) return "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (a === 0) return "$0";
  return "$" + Number(v.toPrecision(4)).toString().replace(/^0/, "0");
}

function fmtCompactUSD(v) {
  if (v === null || v === undefined || isNaN(v)) return "—";
  var a = Math.abs(v);
  var units = [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "K"]];
  for (var i = 0; i < units.length; i++) {
    if (a >= units[i][0]) return "$" + (v / units[i][0]).toFixed(2) + units[i][1];
  }
  return fmtUSD(v);
}

function fmtPct(v, digits) {
  if (v === null || v === undefined || isNaN(v)) return "—";
  var d = digits === undefined ? 2 : digits;
  return (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(d) + "%";
}

function fmtPlainPct(v, digits) {
  if (v === null || v === undefined || isNaN(v)) return "—";
  return v.toFixed(digits === undefined ? 2 : digits) + "%";
}

function fmtValue(col, v) {
  if (v === null || v === undefined) return "—";
  if (col === "change_24h_pct") return fmtPct(v);
  if (col === "market_cap_rank") return String(v);
  if (col === "volume_24h_usd" || col === "market_cap_usd") return fmtCompactUSD(v);
  return fmtUSD(v);
}

function signClass(v) { return v > 0 ? "up" : v < 0 ? "down" : ""; }

function fmtTime(iso) {
  var d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) + " (" + iso.replace("T", " ").replace("Z", " UTC") + ")";
}

function showRunInNav(status) {
  var el = document.querySelector(".nav-status");
  if (el && status && status.run_time) el.textContent = "Last run " + status.run_time.replace("T", " ").replace(":00Z", "").replace("Z", "") + " UTC";
}

/* ---------- offline / install ---------- */

if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("sw.js").catch(function (e) { console.warn("service worker:", e); });
  });
}
function updateOnlineNote() {
  var n = document.querySelector(".offline-note");
  if (n) n.style.display = navigator.onLine ? "none" : "block";
}
window.addEventListener("online", updateOnlineNote);
window.addEventListener("offline", updateOnlineNote);
document.addEventListener("DOMContentLoaded", updateOnlineNote);

/* ---------- charts (plain SVG) ---------- */

var SVGNS = "http://www.w3.org/2000/svg";
var SERIES_VARS = ["--s1", "--s2", "--s3", "--s4", "--s5", "--s6", "--s7", "--s8"];

function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

function el(tag, attrs, parent) {
  var e = document.createElementNS(SVGNS, tag);
  for (var k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}

/* Draw at the container's real width so text stays at its true size. */
function chartWidth(container) { return Math.max(320, Math.round(container.clientWidth || 760)); }

function niceTicks(min, max, count) {
  if (min === max) { var pad = Math.abs(min) * 0.05 || 1; min -= pad; max += pad; }
  var span = max - min, step = Math.pow(10, Math.floor(Math.log10(span / count)));
  var err = span / count / step;
  if (err >= 7.5) step *= 10; else if (err >= 3.5) step *= 5; else if (err >= 1.5) step *= 2;
  var lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step, ticks = [];
  for (var v = lo; v <= hi + step / 2; v += step) ticks.push(Number(v.toPrecision(12)));
  return ticks;
}

function makeTooltip(container) {
  var t = document.createElement("div");
  t.className = "tooltip";
  container.appendChild(t);
  return {
    show: function (html, x, y) {
      t.innerHTML = html; t.style.display = "block";
      var w = t.offsetWidth, cw = container.clientWidth;
      t.style.left = Math.max(0, Math.min(cw - w, x + 12)) + "px";
      t.style.top = Math.max(0, y - t.offsetHeight - 8) + "px";
    },
    hide: function () { t.style.display = "none"; },
  };
}

/* Line chart. series: [{name, color, points: [{x: date, y: number|null}]}], xs: all dates. */
function lineChart(container, opts) {
  container.innerHTML = "";
  container.classList.add("chart");
  var xs = opts.xs, series = opts.series, fmt = opts.format || String;
  var vals = [];
  series.forEach(function (s) { s.points.forEach(function (p) { if (p.y !== null) vals.push(p.y); }); });
  if (!xs.length || !vals.length) { container.innerHTML = "<p class='empty'>No data to chart yet.</p>"; return; }
  var W = chartWidth(container), H = opts.height || 300, m = { l: 72, r: 16, t: 12, b: 28 };
  var ticks = niceTicks(Math.min.apply(null, vals), Math.max.apply(null, vals), 5);
  var y0 = ticks[0], y1 = ticks[ticks.length - 1];
  var X = function (i) { return xs.length === 1 ? (m.l + W - m.r) / 2 : m.l + i * (W - m.l - m.r) / (xs.length - 1); };
  var Y = function (v) { return m.t + (y1 - v) / (y1 - y0) * (H - m.t - m.b); };
  var svg = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": opts.label || "line chart" }, container);
  var g = el("g", { class: "grid" }, svg), ax = el("g", { class: "axis" }, svg);
  ticks.forEach(function (t) {
    el("line", { x1: m.l, x2: W - m.r, y1: Y(t), y2: Y(t) }, g);
    var tx = el("text", { x: m.l - 8, y: Y(t) + 4, "text-anchor": "end" }, ax); tx.textContent = (opts.tickFormat || fmt)(t);
  });
  var every = Math.max(1, Math.ceil(xs.length / 8));
  xs.forEach(function (d, i) {
    if (i % every && i !== xs.length - 1) return;
    var tx = el("text", { x: X(i), y: H - 8, "text-anchor": "middle" }, ax); tx.textContent = d.slice(5);
  });
  var surface = cssVar("--surface");
  series.forEach(function (s) {
    var segs = [], cur = [];
    s.points.forEach(function (p, i) {
      if (p.y === null) { if (cur.length) segs.push(cur); cur = []; } else cur.push([X(i), Y(p.y)]);
    });
    if (cur.length) segs.push(cur);
    segs.forEach(function (seg) {
      if (seg.length > 1) el("path", { d: "M" + seg.map(function (q) { return q[0].toFixed(1) + "," + q[1].toFixed(1); }).join("L"),
        fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
    });
    s.points.forEach(function (p, i) {
      if (p.y !== null) el("circle", { cx: X(i), cy: Y(p.y), r: 4, fill: s.color, stroke: surface, "stroke-width": 2 }, svg);
    });
  });
  // hover: crosshair + tooltip for the nearest date
  var tip = makeTooltip(container);
  var cross = el("line", { class: "crosshair", y1: m.t, y2: H - m.b, visibility: "hidden" }, svg);
  var hit = el("rect", { x: m.l - 10, y: 0, width: W - m.l - m.r + 20, height: H, fill: "transparent" }, svg);
  hit.addEventListener("mousemove", function (ev) {
    var r = svg.getBoundingClientRect(), sx = (ev.clientX - r.left) * W / r.width;
    var i = xs.length === 1 ? 0 : Math.round((sx - m.l) / ((W - m.l - m.r) / (xs.length - 1)));
    i = Math.max(0, Math.min(xs.length - 1, i));
    cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.setAttribute("visibility", "visible");
    var lines = series.map(function (s) { return { s: s, y: s.points[i].y }; })
      .filter(function (o) { return o.y !== null; })
      .sort(function (a, b) { return b.y - a.y; })
      .map(function (o) { return "<div><span class='sw' style='background:" + o.s.color + "'></span>" + esc(o.s.name) + ": <b>" + fmt(o.y) + "</b></div>"; });
    tip.show("<div class='t-head'>" + xs[i] + "</div>" + (lines.join("") || "<div class='muted'>no values</div>"),
             X(i) * r.width / W, ev.clientY - container.getBoundingClientRect().top);
  });
  hit.addEventListener("mouseleave", function () { tip.hide(); cross.setAttribute("visibility", "hidden"); });
}

/* Horizontal bar chart around zero. items: [{label, value, tip}], blue for >= 0, red for < 0. */
function barChart(container, opts) {
  container.innerHTML = "";
  container.classList.add("chart");
  var items = opts.items, fmt = opts.format || String;
  if (!items.length) { container.innerHTML = "<p class='empty'>No data to chart yet.</p>"; return; }
  var W = chartWidth(container), rowH = 22, m = { l: Math.min(170, W * 0.32), r: 78, t: 4, b: 24 }, H = m.t + m.b + rowH * items.length;
  var vals = items.map(function (d) { return d.value; });
  var lo = Math.min(0, Math.min.apply(null, vals)), hi = Math.max(0, Math.max.apply(null, vals));
  var ticks = niceTicks(lo, hi, 5); lo = ticks[0]; hi = ticks[ticks.length - 1];
  var X = function (v) { return m.l + (v - lo) / (hi - lo) * (W - m.l - m.r); };
  var svg = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": opts.label || "bar chart" }, container);
  var g = el("g", { class: "grid" }, svg), ax = el("g", { class: "axis" }, svg);
  ticks.forEach(function (t) {
    el("line", { x1: X(t), x2: X(t), y1: m.t, y2: H - m.b }, g);
    var tx = el("text", { x: X(t), y: H - 6, "text-anchor": "middle" }, ax); tx.textContent = (opts.tickFormat || fmt)(t);
  });
  el("line", { class: "zero", x1: X(0), x2: X(0), y1: m.t, y2: H - m.b }, svg);
  var tip = makeTooltip(container);
  var up = opts.color || cssVar("--bar-up"), down = opts.color || cssVar("--bar-down");
  items.forEach(function (d, i) {
    var y = m.t + i * rowH, x0 = X(0), x1 = X(d.value);
    var lbl = el("text", { class: "label", x: m.l - 8, y: y + rowH / 2 + 4, "text-anchor": "end" }, svg); lbl.textContent = d.label;
    var w = Math.abs(x1 - x0);
    el("rect", { x: Math.min(x0, x1), y: y + 4, width: Math.max(w, 1), height: rowH - 8, rx: Math.min(4, w / 2),
                 fill: d.value >= 0 ? up : down }, svg);
    // values sit in their own column at the right, so they never collide with bars or names
    var v = el("text", { class: "label-2", x: W - 4, y: y + rowH / 2 + 4, "text-anchor": "end" }, svg);
    v.textContent = fmt(d.value);
    var hit = el("rect", { x: 0, y: y, width: W, height: rowH, fill: "transparent" }, svg);
    hit.addEventListener("mousemove", function (ev) {
      var r = svg.getBoundingClientRect();
      tip.show(d.tip || ("<div class='t-head'>" + esc(d.label) + "</div>" + fmt(d.value)),
               ev.clientX - r.left, ev.clientY - container.getBoundingClientRect().top);
    });
    hit.addEventListener("mouseleave", tip.hide);
  });
}

/* Vertical column chart, one series. items: [{label, value, tip}] */
function columnChart(container, opts) {
  container.innerHTML = "";
  container.classList.add("chart");
  var items = opts.items, fmt = opts.format || String;
  if (!items.length) { container.innerHTML = "<p class='empty'>No data to chart yet.</p>"; return; }
  var W = chartWidth(container), H = opts.height || 260, m = { l: 60, r: 12, t: 16, b: 28 };
  var vals = items.map(function (d) { return d.value; });
  var ticks = niceTicks(Math.min(0, Math.min.apply(null, vals)), Math.max(0, Math.max.apply(null, vals)), 5);
  var y0 = ticks[0], y1 = ticks[ticks.length - 1];
  var Y = function (v) { return m.t + (y1 - v) / (y1 - y0) * (H - m.t - m.b); };
  var band = (W - m.l - m.r) / items.length, bw = Math.min(48, band * 0.7);
  var svg = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": opts.label || "column chart" }, container);
  var g = el("g", { class: "grid" }, svg), ax = el("g", { class: "axis" }, svg);
  ticks.forEach(function (t) {
    el("line", { x1: m.l, x2: W - m.r, y1: Y(t), y2: Y(t) }, g);
    var tx = el("text", { x: m.l - 8, y: Y(t) + 4, "text-anchor": "end" }, ax); tx.textContent = (opts.tickFormat || fmt)(t);
  });
  var tip = makeTooltip(container), color = opts.color || cssVar("--s1");
  var every = Math.max(1, Math.ceil(items.length / 10));
  items.forEach(function (d, i) {
    var cx = m.l + band * i + band / 2, ya = Y(Math.max(0, d.value)), yb = Y(Math.min(0, d.value));
    el("rect", { x: cx - bw / 2, y: ya, width: bw, height: Math.max(1, yb - ya), rx: Math.min(4, bw / 2), fill: color }, svg);
    if (i % every === 0 || i === items.length - 1) {
      var tx = el("text", { x: cx, y: H - 8, "text-anchor": "middle" }, ax); tx.textContent = d.label;
    }
    var hit = el("rect", { x: cx - band / 2, y: 0, width: band, height: H, fill: "transparent" }, svg);
    hit.addEventListener("mousemove", function (ev) {
      var r = svg.getBoundingClientRect();
      tip.show(d.tip || ("<div class='t-head'>" + esc(d.label) + "</div>" + fmt(d.value)),
               ev.clientX - r.left, ev.clientY - container.getBoundingClientRect().top);
    });
    hit.addEventListener("mouseleave", tip.hide);
  });
}

function seriesColor(slot) { return cssVar(SERIES_VARS[slot % SERIES_VARS.length]); }
