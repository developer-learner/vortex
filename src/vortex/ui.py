"""Operator dashboard shell (router phase 2). Served at "/" by app.py;
JS polls /api/* client-side."""

UI_PAGE: str = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>vortex · model menu</title>
<style>
:root {
  --bg: #0e1116;
  --panel: #161b22;
  --line: #2b323d;
  --fg: #d6dde6;
  --dim: #8b97a6;
  --accent: #58a6ff;
  --ok: #3fb950;
  --warn: #d29922;
  --danger: #f85149;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font: 14px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
header {
  padding: 14px 20px;
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: center;
  gap: 12px;
}
header h1 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.02em;
}
header .sub { color: var(--dim); font-size: 12px; }
main { padding: 16px 20px 40px; max-width: 960px; margin: 0 auto; }
#down {
  display: none;
  margin-bottom: 14px;
  padding: 10px 14px;
  border: 1px solid var(--danger);
  border-radius: 6px;
  color: var(--danger);
  background: rgba(248, 81, 73, 0.08);
  font-size: 13px;
}
#down code {
  display: block;
  margin-top: 6px;
  color: var(--fg);
  background: var(--panel);
  padding: 6px 10px;
  border-radius: 4px;
  overflow-x: auto;
}
.ram {
  margin-bottom: 16px;
}
.ram .label {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--dim);
  margin-bottom: 6px;
}
.ram .track {
  height: 10px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 5px;
  overflow: hidden;
}
.ram .fill {
  height: 100%;
  width: 0%;
  background: var(--accent);
  transition: width 0.25s ease, background 0.25s ease;
}
.ram .fill.warn { background: var(--warn); }
.ram .fill.danger { background: var(--danger); }
#conflict {
  display: none;
  margin-bottom: 14px;
  padding: 10px 14px;
  border: 1px solid var(--warn);
  border-radius: 6px;
  color: var(--warn);
  background: rgba(210, 153, 34, 0.08);
  font-size: 13px;
}
#conflictbody {
  margin-top: 6px;
  color: var(--fg);
  white-space: pre-wrap;
}
table {
  width: 100%;
  border-collapse: collapse;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 6px;
  overflow: hidden;
}
thead th {
  text-align: left;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--dim);
  padding: 8px 12px;
  border-bottom: 1px solid var(--line);
}
tbody td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  vertical-align: middle;
}
tbody tr:last-child td { border-bottom: none; }
tbody tr.loaded td:first-child { color: var(--ok); }
tbody tr.empty td {
  color: var(--dim);
  text-align: center;
  padding: 24px;
}
.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 8px;
  background: var(--dim);
}
.status-dot.loaded { background: var(--ok); }
.status-dot.loading { background: var(--warn); }
button {
  font: inherit;
  font-size: 12px;
  padding: 4px 10px;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: transparent;
  color: var(--fg);
  cursor: pointer;
}
button:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
button:disabled { opacity: 0.4; cursor: not-allowed; }
button[data-act="load"] { border-color: var(--ok); color: var(--ok); }
button[data-act="load"]:hover:not(:disabled) { border-color: var(--ok); color: var(--ok); background: rgba(63, 185, 80, 0.1); }
button[data-act="unload"] { border-color: var(--danger); color: var(--danger); }
button[data-act="unload"]:hover:not(:disabled) { border-color: var(--danger); color: var(--danger); background: rgba(248, 81, 73, 0.1); }
footer {
  padding: 12px 20px;
  border-top: 1px solid var(--line);
  color: var(--dim);
  font-size: 11px;
  text-align: center;
}
</style>
</head>
<body>
<header>
  <h1>vortex</h1>
  <span class="sub">model menu</span>
</header>
<main>
  <div id="down">
    Daemon unreachable at :9000.
    Start it with:
    <code>.venv/bin/uvicorn vortex.app:build_app --factory --port 9000</code>
  </div>
  <div class="ram">
    <div class="label">
      <span>RAM</span>
      <span id="ramlabel">—</span>
    </div>
    <div class="track">
      <div class="fill" id="ramfill"></div>
    </div>
  </div>
  <div id="conflict">
    <strong>Conflict detected</strong>
    <div id="conflictbody"></div>
  </div>
  <table>
    <thead>
      <tr>
        <th>Status</th>
        <th>Model</th>
        <th>Size</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody id="rows">
      <tr class="empty"><td colspan="4">loading…</td></tr>
    </tbody>
  </table>
</main>
<footer>served at :9000/ by the daemon · polls /api/* every 2s</footer>
<script>
(function () {
  "use strict";

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  var POLL_MS = 2000;
  var OP_POLL_MS = 500;
  var opTimer = null;

  function setRam(pct, used, total) {
    var label = document.getElementById("ramlabel");
    var fill = document.getElementById("ramfill");
    var p = Math.max(0, Math.min(100, pct));
    label.textContent = used + " / " + total + " GiB (" + p.toFixed(1) + "%)";
    fill.style.width = p + "%";
    fill.className = "fill" + (p > 85 ? " danger" : p > 70 ? " warn" : "");
  }

  function setConflict(msg) {
    var box = document.getElementById("conflict");
    var body = document.getElementById("conflictbody");
    if (msg) {
      body.textContent = msg;
      box.style.display = "block";
    } else {
      box.style.display = "none";
    }
  }

  function renderRows(models) {
    var rows = document.getElementById("rows");
    if (!models || !models.length) {
      rows.innerHTML = '<tr class="empty"><td colspan="4">no models in catalog</td></tr>';
      return;
    }
    var html = "";
    for (var i = 0; i < models.length; i++) {
      var m = models[i];
      var loaded = m.state === "loaded";
      var loading = m.state === "loading";
      var dotCls = loaded ? "loaded" : loading ? "loading" : "";
      var dot = '<span class="status-dot ' + dotCls + '"></span>';
      var actBtn = "";
      if (loaded) {
        actBtn = '<button data-act="unload" data-id="' + esc(m.id) + '">unload</button>';
      } else if (!loading) {
        actBtn = '<button data-act="load" data-id="' + esc(m.id) + '">load</button>';
      }
      html += "<tr>";
      html += "<td>" + dot + (loading ? "loading…" : loaded ? "loaded" : "idle") + "</td>";
      html += "<td>" + esc(m.name) + "</td>";
      html += "<td>" + esc(m.size_gib) + " GiB</td>";
      html += "<td>" + actBtn + "</td>";
      html += "</tr>";
    }
    rows.innerHTML = html;
  }

  function pollStatus() {
    fetch("/api/status")
      .then(function (r) {
        if (!r.ok) throw new Error("status " + r.status);
        return r.json();
      })
      .then(function (s) {
        document.getElementById("down").style.display = "none";
        setRam(s.ram_pct || 0, s.ram_used_gib || 0, s.ram_total_gib || 0);
        setConflict(s.conflict || null);
      })
      .catch(function () {
        document.getElementById("down").style.display = "block";
      });
  }

  function pollCatalog() {
    fetch("/api/catalog")
      .then(function (r) {
        if (!r.ok) throw new Error("catalog " + r.status);
        return r.json();
      })
      .then(function (models) {
        renderRows(models);
      })
      .catch(function () {});
  }

  function pollOperation(opId) {
    if (opTimer) {
      clearInterval(opTimer);
      opTimer = null;
    }
    opTimer = setInterval(function () {
      fetch("/api/operations/" + encodeURIComponent(opId))
        .then(function (r) {
          if (!r.ok) throw new Error("op " + r.status);
          return r.json();
        })
        .then(function (op) {
          if (op.state === "done" || op.state === "error") {
            if (opTimer) {
              clearInterval(opTimer);
              opTimer = null;
            }
            pollCatalog();
            pollStatus();
          }
        })
        .catch(function () {
          if (opTimer) {
            clearInterval(opTimer);
            opTimer = null;
          }
        });
    }, OP_POLL_MS);
  }

  document.getElementById("rows").addEventListener("click", function (e) {
    var btn = e.target.closest("button[data-act]");
    if (!btn) return;
    var act = btn.getAttribute("data-act");
    var id = btn.getAttribute("data-id");
    var path = "/api/models/" + encodeURIComponent(id) + "/" + act;
    fetch(path, { method: "POST" })
      .then(function (r) {
        if (!r.ok) throw new Error(act + " " + r.status);
        return r.json();
      })
      .then(function (op) {
        pollOperation(op.id);
      })
      .catch(function () {});
  });

  pollStatus();
  pollCatalog();
  setInterval(pollStatus, POLL_MS);
  setInterval(pollCatalog, POLL_MS);
})();
</script>
</body>
</html>
"""