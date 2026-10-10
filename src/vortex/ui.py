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
main { padding: 16px 20px 40px; max-width: 1200px; margin: 0 auto; }
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
  white-space: nowrap;
}
tbody td.model { white-space: normal; min-width: 260px; }
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
.badge.extra { border-color: var(--accent); color: var(--accent); }
.badge:first-child { margin-left: 0; }
.model-id { display: block; color: var(--dim); font-size: 11px; }
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
button.port {
  font-size: 12px;
  padding: 2px 8px;
  border-color: var(--accent);
  color: var(--accent);
}
button.port:hover:not(:disabled) { background: rgba(88, 166, 255, 0.1); }
.dim { color: var(--dim); }
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
  <button id="stopvortex" title="Stop Vortex" style="margin-left:auto">✕ Stop Vortex</button>
  <button id="restartvortex" title="Restart Vortex">↻ Restart Vortex</button>
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
      <span id="ramdetail"></span>
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
        <th>Quant</th>
        <th>Runtime</th>
        <th>Extras</th>
        <th>Size</th>
        <th>Endpoint</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody id="rows">
      <tr class="empty"><td colspan="8">loading…</td></tr>
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
  <section id="discoveredmodels">
    <h2>Discovered models</h2>
    <table>
      <thead>
        <tr>
          <th>Model</th>
          <th>Publisher</th>
          <th>Quant</th>
          <th>Size</th>
          <th>Params</th>
          <th>Context</th>
          <th>Loaded</th>
          <th>Catalog</th>
        </tr>
      </thead>
      <tbody id="modelrows">
        <tr class="empty"><td colspan="8">loading…</td></tr>
      </tbody>
    </table>
    <div style="margin-top: 10px; display: flex; align-items: center; gap: 10px;">
      <span id="modelstatus"></span>
      <button data-act="scan-models">Scan</button>
      <button id="addnewmodels">Add all new</button>
    </div>
    <div id="addresult"></div>
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

  function setRamDetail(loadable, loaded) {
    var el = document.getElementById("ramdetail");
    var parts = [];
    for (var i = 0; i < loaded.length; i++) {
      var lm = loaded[i];
      parts.push(esc(lm.id) + " " + (lm.rss_gb || 0) + " GB");
    }
    parts.push("~" + loadable + " GB loadable");
    el.textContent = " · " + parts.join(" · ");
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
      rows.innerHTML = '<tr class="empty"><td colspan="8">no models in catalog</td></tr>';
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
      // The id line is what clients send as "model"; the name above it is display-only.
      html += '<td class="model">' + esc(m.display_name || m.public_id)
        + '<span class="model-id">' + esc(m.public_id) + "</span></td>";
      html += "<td>" + (m.quant ? esc(m.quant) : '<span class="dim">—</span>') + "</td>";
      html += '<td><span class="badge" title="engine: ' + esc(m.engine) + '">' + esc(m.runtime) + "</span></td>";
      var extras = m.extras || [];
      var extraCell = "";
      for (var j = 0; j < extras.length; j++) {
        extraCell += '<span class="badge extra">' + esc(extras[j]) + "</span>";
      }
      html += "<td>" + (extraCell || '<span class="dim">—</span>') + "</td>";
      html += "<td>" + esc(m.ram_estimate_gb) + " GiB</td>";
      var endpoint = m.chat_endpoint || ("http://localhost:" + m.port + "/v1/chat/completions");
      var portCell = (loaded && m.port)
        ? '<button type="button" class="port" data-copy="' + esc(endpoint) + '" '
          + 'title="Copy endpoint: ' + esc(endpoint) + '">localhost:' + esc(m.port) + '</button>'
        : '<span class="dim">—</span>';
      html += "<td>" + portCell + "</td>";
      var rmBtn = (m.origin === "local")
        ? '<button data-act="remove-model" data-id="' + esc(m.public_id) + '">Remove</button>'
        : "";
      html += "<td>" + actBtn + rmBtn + "</td>";
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
        setRamDetail(s.loadable_gb || 0, s.loaded || []);
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

  function fmtSize(bytes) {
    if (!bytes) return "";
    return (bytes / 1e9).toFixed(1) + " GB";
  }

  function renderModels(models) {
    var rows = document.getElementById("modelrows");
    if (!models || !models.length) {
      rows.innerHTML = '<tr class="empty"><td colspan="8">no discovered models</td></tr>';
      return;
    }
    var html = "";
    for (var i = 0; i < models.length; i++) {
      var m = models[i];
      html += "<tr>";
      html += "<td>" + esc(m.key) + "</td>";
      html += "<td>" + esc(m.publisher) + "</td>";
      html += "<td>" + esc(m.quantization) + "</td>";
      html += "<td>" + esc(fmtSize(m.size_bytes)) + "</td>";
      html += "<td>" + esc(m.params) + "</td>";
      html += "<td>" + esc(m.max_context) + "</td>";
      html += "<td>" + (m.loaded ? "yes" : "no") + "</td>";
      var catalogCell = (m.in_catalog ? "yes" : "no")
        + (!m.in_catalog
          ? ' <button data-act="add-model" data-key="' + esc(m.key) + '">Add</button>'
          : "");
      html += "<td>" + catalogCell + "</td>";
      html += "</tr>";
    }
    rows.innerHTML = html;
  }

  function pollModels() {
    fetch("/api/discovered-models")
      .then(function (r) {
        if (!r.ok) throw new Error("models " + r.status);
        return r.json();
      })
      .then(function (data) {
        renderModels(data.models);
      })
      .catch(function (e) {
        setError("Could not refresh discovered models: " + e.message);
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
            } else {
              setError(null);
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

  document.getElementById("stopvortex").addEventListener("click", function () {
    if (!confirm("Stop Vortex? This unloads all loaded models, freeing their RAM, and shuts down the server.")) return;
    fetch("/api/shutdown", { method: "POST" })
      .then(function (r) {
        if (!r.ok) throw new Error("shutdown " + r.status);
        document.getElementById("down").style.display = "block";
      })
      .catch(function (e) { setError("Shutdown failed: " + e.message); });
  });

  document.getElementById("rows").addEventListener("click", function (e) {
    var copyBtn = e.target.closest("button[data-copy]");
    if (copyBtn) {
      var endpoint = copyBtn.getAttribute("data-copy");
      var done = function () {
        var prev = copyBtn.textContent;
        copyBtn.textContent = "copied ✓";
        setTimeout(function () { copyBtn.textContent = prev; }, 1200);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(endpoint).then(done, function () { setError("Copy failed: " + endpoint); });
      } else {
        setError("Endpoint: " + endpoint);
      }
      return;
    }
    var btn = e.target.closest("button[data-act]");
    if (!btn) return;
    var act = btn.getAttribute("data-act");
    var id = btn.getAttribute("data-id");
    if (act === "remove-model") {
      if (!confirm("Remove " + id + " from Vortex? The model files are not deleted.")) return;
      fetch("/api/catalog/" + encodeURIComponent(id), { method: "DELETE" })
        .then(function (r) {
          if (!r.ok) {
            return r.json().then(function (b) {
              throw new Error((b && b.detail && b.detail.message) || ("remove " + r.status));
            });
          }
          return r.json();
        })
        .then(function () {
          setError(null);
          pollCatalog();
          pollModels();
        })
        .catch(function (e) {
          setError("Remove failed: " + e.message);
        });
      return;
    }
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

  document.getElementById("discoveredmodels").addEventListener("click", function (e) {
    var btn = e.target.closest("button[data-act]");
    if (!btn) return;
    var act = btn.getAttribute("data-act");
    if (act === "add-model") {
      var akey = btn.getAttribute("data-key");
      fetch("/api/discovered-models/" + encodeURIComponent(akey) + "/add", { method: "POST" })
        .then(function (r) {
          if (!r.ok) {
            return r.json().then(function (b) {
              throw new Error((b && b.detail && b.detail.message) || ("add " + r.status));
            });
          }
          return r.json();
        })
        .then(function () {
          setError(null);
          pollCatalog();
          pollModels();
        })
        .catch(function (e) {
          setError("Add failed: " + e.message);
        });
      return;
    }
    if (act !== "scan-models") return;
    fetch("/api/discovered-models/discover", { method: "POST" })
      .then(function (r) {
        if (!r.ok) throw new Error("scan " + r.status);
        return r.json();
      })
      .then(function (res) {
        setError(null);
        pollModels();
        var newly = res.newly_found || [];
        if (newly.length) {
          var rows = document.getElementById("modelrows").querySelectorAll("tr");
          for (var i = 0; i < rows.length; i++) {
            var keyCell = rows[i].cells[0];
            if (keyCell && newly.indexOf(keyCell.textContent) !== -1) {
              rows[i].classList.add("newly-found");
            }
          }
        }
      })
      .catch(function (e) {
        setError("Model discovery failed: " + e.message);
      });
  });

  document.getElementById("addnewmodels").addEventListener("click", function () {
    if (!confirm("Add every discovered model not yet in Vortex to the loadable list?")) return;
    fetch("/api/discovered-models/add-new", { method: "POST" })
      .then(function (r) {
        if (!r.ok) {
          return r.json().then(function (b) {
            throw new Error((b && b.detail && b.detail.message) || ("add-new " + r.status));
          });
        }
        return r.json();
      })
      .then(function (body) {
        setError(null);
        var out = "Added " + (body.added || []).length;
        var skipped = body.skipped || [];
        for (var i = 0; i < skipped.length; i++) {
          var sk = skipped[i];
          out += " · " + sk.key + " (" + sk.reason + ")";
        }
        document.getElementById("addresult").textContent = out;
        pollCatalog();
        pollModels();
      })
      .catch(function (e) {
        setError("Add failed: " + e.message);
      });
  });

  document.getElementById("restartvortex").addEventListener("click", function () {
    var btn = this;
    if (!confirm("Restart Vortex? This unloads all loaded models, freeing their RAM, then starts a clean server.")) return;
    btn.disabled = true;
    fetch("/api/restart", { method: "POST" })
      .then(function (r) {
        if (r.status === 409) throw new Error("a load or unload is in progress");
        if (!r.ok) throw new Error("restart " + r.status);
        waitForRestart(btn, 0, false);
      })
      .catch(function (e) { btn.disabled = false; setError("Restart failed: " + e.message); });
  });
  function waitForRestart(btn, tries, wentDown) {
    if (tries > 90) { btn.disabled = false; setError("Restart failed: Vortex did not come back; see ~/Library/Logs/Vortex.log"); return; }
    setTimeout(function () {
      fetch("/api/status")
        .then(function (r) {
          if (r.ok && (wentDown || tries >= 10)) { location.reload(); return; }
          waitForRestart(btn, tries + 1, wentDown);
        })
        .catch(function () { waitForRestart(btn, tries + 1, true); });
    }, 500);
  }

  pollStatus();
  pollCatalog();
  pollWrappers();
  pollModels();
  setInterval(pollStatus, POLL_MS);
  setInterval(pollCatalog, POLL_MS);
  setInterval(pollWrappers, POLL_MS);
  setInterval(pollModels, POLL_MS);
})();
</script>
</body>
</html>
"""
