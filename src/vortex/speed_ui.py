"""The Speed page: one self-contained dark-theme HTML document, served at /speed.

Polls /api/speed every 2 s; the operator ticks up to 3 models and starts one
run. No external resources — everything is inline.
"""

SPEED_PAGE: str = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>vortex · speed</title>
<style>
:root {
  --bg: #0e1116; --panel: #161b22; --line: #2b323d; --fg: #d6dde6;
  --dim: #8b97a6; --accent: #58a6ff; --ok: #3fb950; --warn: #d29922; --danger: #f85149;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 14px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
header { padding: 14px 20px; border-bottom: 1px solid var(--line);
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
header h1 { margin: 0; font-size: 16px; font-weight: 600; letter-spacing: 0.02em; }
header .sub { color: var(--dim); font-size: 12px; }
nav { display: flex; gap: 4px; margin-left: 18px; }
nav a { color: var(--dim); text-decoration: none; padding: 4px 10px; border-radius: 4px; font-size: 13px; }
nav a.on { color: var(--fg); background: var(--panel); border: 1px solid var(--line); }
main { padding: 16px 20px 40px; max-width: 1280px; margin: 0 auto; }
.banner { display: none; margin-bottom: 14px; padding: 8px 14px; border: 1px solid var(--warn);
  border-radius: 6px; color: var(--warn); background: rgba(210, 153, 34, 0.08); font-size: 13px; }
.error { display: none; margin-bottom: 14px; padding: 8px 14px; border: 1px solid var(--danger);
  border-radius: 6px; color: var(--danger); background: rgba(248, 81, 73, 0.08); font-size: 13px; }
h2 { font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--dim); margin: 22px 0 10px; }
.picks { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }
.pick { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 12px 14px; }
.pick .what { font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--dim); }
.pick .num { font-size: 26px; font-weight: 600; margin: 4px 0 0; color: var(--ok); }
.pick .num small { font-size: 12px; color: var(--dim); font-weight: 400; }
.pick .why { color: var(--dim); font-size: 12px; margin-top: 6px; }
.toolbar { display: flex; align-items: center; gap: 12px; margin: 22px 0 10px; flex-wrap: wrap; }
.toolbar h2 { margin: 0; }
.count { color: var(--dim); font-size: 12px; margin-left: auto; }
.count.full { color: var(--warn); }
table { width: 100%; border-collapse: collapse; background: var(--panel);
  border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }
thead th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--dim); padding: 8px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }
thead th.sortable { cursor: pointer; }
thead th.sortable:hover { color: var(--fg); }
tbody td { padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: middle; white-space: nowrap; }
tbody tr:last-child td { border-bottom: none; }
tbody tr.picked td { background: rgba(88, 166, 255, 0.07); }
td.model { white-space: normal; min-width: 230px; }
.model-id { display: block; color: var(--dim); font-size: 11px; }
.bar { display: flex; align-items: center; gap: 8px; min-width: 140px; }
.bar .track { flex: 1; height: 8px; background: var(--bg); border: 1px solid var(--line); border-radius: 4px; overflow: hidden; }
.bar .fill { height: 100%; background: var(--accent); }
.bar .val { width: 44px; text-align: right; }
.badge { display: inline-block; margin-left: 6px; padding: 1px 6px; border-radius: 4px;
  border: 1px solid var(--ok); color: var(--ok); font-size: 10px; letter-spacing: 0.04em;
  text-transform: uppercase; vertical-align: middle; }
.dash { color: var(--dim); }
.st { font-size: 12px; }
.st.queued { color: var(--dim); }
.st.loading, .st.testing, .st.unloading { color: var(--warn); }
.st.done { color: var(--ok); }
.st.skipped, .st.failed { color: var(--danger); }
td.status { white-space: normal; width: 190px; max-width: 190px; font-size: 12px; }
input[type=checkbox] { width: 15px; height: 15px; accent-color: var(--accent); cursor: pointer; }
input[type=checkbox]:disabled { cursor: not-allowed; opacity: 0.35; }
button { font: inherit; font-size: 12px; padding: 4px 10px; border: 1px solid var(--line);
  border-radius: 4px; background: transparent; color: var(--fg); cursor: pointer; }
button:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
button:disabled { opacity: 0.4; cursor: not-allowed; }
button.primary { border-color: var(--ok); color: var(--ok); padding: 5px 14px; }
.method { margin-top: 12px; color: var(--dim); font-size: 12px; }
.method b { color: var(--warn); font-weight: 400; }
footer { padding: 12px 20px; border-top: 1px solid var(--line); color: var(--dim);
  font-size: 11px; text-align: center; }
</style>
</head>
<body>
<header>
  <h1>vortex</h1>
  <span class="sub">speed</span>
  <nav><a href="/">Models</a><a class="on">Speed</a></nav>
  <span class="sub" style="margin-left:auto">:9000</span>
</header>
<main>
  <div class="banner" id="runbanner">Speed test running — loading and unloading are paused until it finishes.</div>
  <div class="error" id="error"></div>

  <h2>Best picks</h2>
  <div class="picks" id="picks"></div>

  <div class="toolbar">
    <h2>All models</h2>
    <span class="count" id="count">0 of 3 selected</span>
    <button class="primary" id="testsel" disabled>▶ Test selected</button>
  </div>

  <table>
    <thead>
      <tr>
        <th></th>
        <th class="sortable" data-col="catalog">Model</th>
        <th>Quant · runtime</th>
        <th>RAM</th>
        <th class="sortable" data-col="single">One at a time</th>
        <th class="sortable" data-col="multi">Four at once</th>
        <th class="sortable" data-col="first">First word</th>
        <th>Tested</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody id="rows"></tbody>
  </table>

  <div class="method">
    Tick up to 3 models, then start the test. Each model is tested in turn: a model that isn't
    loaded is loaded first and unloaded afterwards; a model that won't fit next to what's loaded
    is skipped — nothing else is ever unloaded to make room.<br>
    Measured with the same fixed prompt, up to 256 tokens, temperature 0. "One at a time" = one
    request (what a coding run feels like); "Four at once" = four requests together, total tokens
    ÷ time; "First word" = time for a 1-token reply. Speed only, not answer quality.<br>
    <b>Don't run a speed test during a pipeline milestone — both use the GPU, so the numbers come
    out wrong and the coder slows down.</b>
  </div>
</main>
<footer>served by the daemon · results kept across restarts · click a speed column to sort</footer>
<script>
var picked = [];
var sortKey = "catalog";
var maxModels = 3;
var running = false;
var models = [];

function dash() { return '<span class="dash">—</span>'; }

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "\u0026amp;").replace(/</g, "\u0026lt;").replace(/>/g, "\u0026gt;");
}

function speedOf(row, key) {
  return row.result == null ? null : row.result[key];
}

function bar(v, max) {
  if (v == null) return dash();
  var pct = max > 0 ? Math.max(3, Math.round(100 * v / max)) : 3;
  return '<div class="bar"><div class="track"><div class="fill" style="width:' + pct +
    '%"></div></div><span class="val">' + v + "</span></div>";
}

function bestPick(key, low) {
  var best = null;
  models.forEach(function (row) {
    if (row.result == null) return;
    if (best == null) { best = row; return; }
    var bv = low ? best.result[key] : -best.result[key];
    var rv = low ? row.result[key] : -row.result[key];
    if (rv < bv) best = row;
  });
  return best;
}

function renderPicks() {
  var s = bestPick("single_tps", false);
  var m = bestPick("multi_tps", false);
  var f = bestPick("first_token_s", true);
  function card(what, pick, val, unit, why) {
    if (pick == null) {
      return '<div class="pick"><div class="what">' + what + '</div>' +
        '<div class="num">—</div><div class="why">no model tested yet</div></div>';
    }
    return '<div class="pick"><div class="what">' + what + '</div><div class="num">' + val +
      ' <small>' + unit + '</small></div><div>' + esc(pick.display_name || pick.public_id) +
      ' <span class="dash">· ' + esc(pick.quant || "—") + " · " + esc(pick.runtime) +
      '</span></div><div class="why">' + why + "</div></div>";
  }
  document.getElementById("picks").innerHTML =
    card("Fastest one at a time", s, s ? s.result.single_tps : null, "tok/s",
      "One request at a time — what a coding run feels like.") +
    card("Fastest four at once", m, m ? m.result.multi_tps : null, "tok/s total",
      "Four requests together, total tokens ÷ time.") +
    card("Quickest first word", f, f ? f.result.first_token_s : null, "s",
      "Wall time to a 1-token reply.");
}

function statusCell(row) {
  var parts = [];
  if (row.state === "ready") parts.push('<span class="badge">loaded</span>');
  if (row.run_status) parts.push('<span class="st ' + esc(row.run_status) + '">' +
    esc(row.run_message || row.run_status) + "</span>");
  return parts.join(" ");
}

function render() {
  var order = {};
  models.forEach(function (row, i) { order[row.public_id] = i; });
  var sorted = models.slice().sort(function (a, b) {
    if (sortKey === "catalog") return order[a.public_id] - order[b.public_id];
    var av = speedOf(a, sortKey), bv = speedOf(b, sortKey);
    if (av == null && bv == null) return order[a.public_id] - order[b.public_id];
    if (av == null) return 1;
    if (bv == null) return -1;
    return sortKey === "first" ? av - bv : bv - av;
  });
  var maxS = 0, maxM = 0;
  models.forEach(function (row) {
    if (row.result != null) {
      maxS = Math.max(maxS, row.result.single_tps);
      maxM = Math.max(maxM, row.result.multi_tps);
    }
  });
  var full = picked.length >= maxModels;
  var html = "";
  sorted.forEach(function (row) {
    var res = row.result;
    var on = picked.indexOf(row.public_id) !== -1;
    var dis = running || (full && !on);
    html += '<tr class="' + (on ? "picked" : "") + '">';
    html += '<td><input type="checkbox" data-id="' + esc(row.public_id) + '"' +
      (on ? " checked" : "") + (dis ? " disabled" : "") + "></td>";
    html += '<td class="model">' + esc(row.display_name || row.public_id) +
      '<span class="model-id">' + esc(row.public_id) + "</span></td>";
    html += "<td>" + esc(row.quant || "—") +
      ' <span class="dash">· ' + esc(row.runtime) + "</span></td>";
    html += "<td>" + (row.ram_estimate_gb == null ? dash() : row.ram_estimate_gb + " GB") + "</td>";
    html += "<td>" + (res == null ? dash() : bar(res.single_tps, maxS)) + "</td>";
    html += "<td>" + (res == null ? dash() : bar(res.multi_tps, maxM)) + "</td>";
    html += "<td>" + (res == null ? dash() : res.first_token_s + " s") + "</td>";
    html += "<td>" + (res == null ? dash() : esc(res.tested_at)) + "</td>";
    html += '<td class="status">' + statusCell(row) + "</td></tr>";
  });
  document.getElementById("rows").innerHTML = html;
  var c = document.getElementById("count");
  c.textContent = picked.length + " of " + maxModels + " selected";
  c.classList.toggle("full", full);
  document.getElementById("testsel").disabled = running || picked.length === 0;
  document.getElementById("runbanner").style.display = running ? "block" : "none";
  renderPicks();
}

function poll() {
  fetch("/api/speed").then(function (r) { return r.json(); }).then(function (body) {
    var err = document.getElementById("error");
    err.textContent = "";
    err.style.display = "none";
    maxModels = body.max_models;
    running = body.running;
    models = body.models;
    render();
  }).catch(function () {
    var err = document.getElementById("error");
    err.textContent = "Speed test failed: the daemon is unreachable";
    err.style.display = "block";
  });
}
setInterval(poll, 2000);
poll();

document.getElementById("rows").addEventListener("change", function (e) {
  var id = e.target.getAttribute("data-id");
  if (!id) return;
  if (e.target.checked && picked.length < maxModels) picked.push(id);
  if (!e.target.checked) picked = picked.filter(function (p) { return p !== id; });
  render();
});

document.querySelector("thead").addEventListener("click", function (e) {
  var k = e.target.getAttribute("data-col");
  if (!k) return;
  sortKey = k;
  render();
});

document.getElementById("testsel").addEventListener("click", function () {
  if (!picked.length || running) return;
  fetch("/api/speed/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ models: picked })
  }).then(function (r) {
    if (r.ok) return null;
    return r.json().then(function (d) {
      throw new Error((d.detail && d.detail.message) || String(r.status));
    });
  }).catch(function (err) {
    var el = document.getElementById("error");
    el.textContent = "Speed test failed: " + err.message;
    el.style.display = "block";
  });
});
</script>
</body>
</html>
"""