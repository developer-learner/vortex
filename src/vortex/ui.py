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
#uierror {
  display: none;
  margin-bottom: 14px;
  padding: 10px 14px;
  border: 1px solid var(--danger);
  border-radius: 6px;
  color: var(--danger);
  background: rgba(210, 60, 60, 0.08);
  font-size: 13px;
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
.badge {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid var(--line);
  font-size: 10px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--dim);
  vertical-align: middle;
}
.badge.dflash { border-color: var(--accent); color: var(--accent); }
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
.open-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  background: var(--dim);
}
.open-dot.open { background: var(--ok); }
tr.newly-found td { background: rgba(88, 166, 255, 0.12); }
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
  <div id="uierror"></div>
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
  <section id="enginewrappers">
    <h2>Engine wrappers</h2>
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Kind</th>
          <th>Binary</th>
          <th>Version</th>
          <th>Port</th>
          <th>Live</th>
          <th>Catalog</th>
        </tr>
      </thead>
      <tbody id="wrapperrows">
        <tr class="empty"><td colspan="7">loading…</td></tr>
      </tbody>
    </table>
    <div style="margin-top: 10px; display: flex; align-items: center; gap: 10px;">
      <span id="wrapperstatus"></span>
      <button data-act="discover">Discover</button>
    </div>
  </section>
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

  function setError(msg) {
    var box = document.getElementById("uierror");
    if (msg) {
      box.textContent = msg;
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
      var loaded = m.state === "ready";
      var loading = m.state === "loading";
      var dotCls = loaded ? "loaded" : loading ? "loading" : "";
      var dot = '<span class="status-dot ' + dotCls + '"></span>';
      var actBtn = "";
      if (loaded) {
        actBtn = '<button data-act="unload" data-id="' + esc(m.public_id) + '">unload</button>';
      } else if (!loading) {
        actBtn = '<button data-act="load" data-id="' + esc(m.public_id) + '">load</button>';
      }
      html += "<tr>";
      html += "<td>" + dot + (loading ? "loading…" : loaded ? "loaded" : "idle") + "</td>";
      var isDflash = m.engine === "mlx-dflash2";
      var engBadge = isDflash
        ? '<span class="badge dflash" title="oMLX speculative decoding via ' + esc(m.upstream_alias || "DFlash2 draft") + '">DFlash2</span>'
        : '<span class="badge" title="engine: ' + esc(m.engine) + '">' + esc(m.engine) + '</span>';
      html += "<td>" + esc(m.public_id) + engBadge + "</td>";
      html += "<td>" + esc(m.ram_estimate_gb) + " GiB</td>";
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
        var used = s.ram_used_gb || 0;
        var total = s.ram_total_gb || 0;
        var pct = total > 0 ? (used / total) * 100 : 0;
        setRam(pct, used, total);
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
      .then(function (data) {
        setError(null);
        renderRows(data.entries);
      })
      .catch(function (e) {
        setError("Could not refresh the model list: " + e.message);
      });
  }

  function renderWrappers(wrappers) {
    var rows = document.getElementById("wrapperrows");
    if (!wrappers || !wrappers.length) {
      rows.innerHTML = '<tr class="empty"><td colspan="7">no engine wrappers found</td></tr>';
      return;
    }
    var html = "";
    for (var i = 0; i < wrappers.length; i++) {
      var w = wrappers[i];
      var dotCls = w.port_open ? "open" : "";
      var dot = '<span class="open-dot ' + dotCls + '"></span>';
      html += "<tr>";
      html += "<td>" + esc(w.name) + "</td>";
      html += "<td>" + esc(w.kind) + "</td>";
      html += "<td>" + esc(w.binary_path) + "</td>";
      html += "<td>" + esc(w.version) + "</td>";
      html += "<td>" + esc(w.port) + "</td>";
      html += "<td>" + dot + (w.port_open ? "open" : "closed") + "</td>";
      html += "<td>" + (w.in_catalog ? "yes" : "no") + "</td>";
      html += "</tr>";
    }
    rows.innerHTML = html;
  }

  function pollWrappers() {
    fetch("/api/engine-wrappers")
      .then(function (r) {
        if (!r.ok) throw new Error("wrappers " + r.status);
        return r.json();
      })
      .then(function (data) {
        renderWrappers(data.wrappers);
      })
      .catch(function (e) {
        setError("Could not refresh engine wrappers: " + e.message);
      });
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
          if (op.state === "ready" || op.state === "unloaded" || op.state === "error") {
            if (opTimer) {
              clearInterval(opTimer);
              opTimer = null;
            }
            if (op.state === "error") {
              setError(op.message || "operation failed");
            }
            pollCatalog();
            pollStatus();
          }
        })
        .catch(function (e) {
          if (opTimer) {
            clearInterval(opTimer);
            opTimer = null;
          }
          setError("Lost track of the operation: " + e.message);
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
        return r.json().then(function (body) {
          if (r.status === 409) {
            var d = body.detail;
            if (d.busy) {
              setConflict(d.message);
              return null;
            }
            var candidates = (d.eviction_candidates && d.eviction_candidates.length) ? d.eviction_candidates.join(", ") : "none";
            setConflict(d.message + " — requires " + d.required_gb + " GiB; candidates: " + candidates);
            return null;
          }
          if (!r.ok) throw new Error(act + " " + r.status);
          return body;
        });
      })
      .then(function (op) {
        if (!op) return;
        setConflict(null);
        setError(null);
        pollOperation(op.operation);
      })
      .catch(function (e) {
        setError(act + " failed: " + e.message);
      });
  });

  document.getElementById("enginewrappers").addEventListener("click", function (e) {
    var btn = e.target.closest("button[data-act]");
    if (!btn) return;
    var act = btn.getAttribute("data-act");
    if (act !== "discover") return;
    fetch("/api/engine-wrappers/discover", { method: "POST" })
      .then(function (r) {
        if (!r.ok) throw new Error("discover " + r.status);
        return r.json();
      })
      .then(function (res) {
        setError(null);
        pollWrappers();
        var newly = res.newly_found || [];
        if (newly.length) {
          var rows = document.getElementById("wrapperrows").querySelectorAll("tr");
          for (var i = 0; i < rows.length; i++) {
            var nameCell = rows[i].cells[0];
            if (nameCell && newly.indexOf(nameCell.textContent) !== -1) {
              rows[i].classList.add("newly-found");
            }
          }
        }
      })
      .catch(function (e) {
        setError("Engine-wrapper discovery failed: " + e.message);
      });
  });

  pollStatus();
  pollCatalog();
  pollWrappers();
  setInterval(pollStatus, POLL_MS);
  setInterval(pollCatalog, POLL_MS);
  setInterval(pollWrappers, POLL_MS);
})();
</script>
</body>
</html>
"""
