const $ = (id) => document.getElementById(id);

let domains = [];
let instances = [];
let selectedDomain = null;
let selectedInstance = null;
let playMode = "qbf"; // qbf | hybrid | certificate
let state = null;

function log(msg) {
  const el = $("log");
  el.textContent = `[${new Date().toLocaleTimeString()}] ${msg}\n` + el.textContent;
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

const MODE_HINT = {
  qbf: "QBF solver: QuBi checks / can guide Black. Best when QuBi is fast.",
  hybrid:
    "Hybrid: first moves from partial certificate (opening book), then QBF. Fast interactive play.",
  certificate:
    "Certificate: play against a precomputed winning strategy (CNF). Use Certificates domain.",
};

function setMode(mode) {
  playMode = mode;
  document.querySelectorAll("#modes .chip").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === mode);
  });
  $("modeHint").textContent = MODE_HINT[mode] || "";
  $("stMode").textContent = mode;
  // auto-pick domain when switching to certificate
  if (mode === "certificate") {
    const cert = domains.find((d) => d.kind === "certificate");
    if (cert) selectDomain(cert.id);
  }
}

async function loadDomains() {
  const data = await api("/api/domains");
  domains = data.domains || [];
  const box = $("domains");
  box.innerHTML = "";
  for (const d of domains) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip" + (selectedDomain === d.id ? " active" : "");
    b.innerHTML = `${d.label} <span class="n">(${d.count})</span>`;
    b.onclick = () => selectDomain(d.id);
    box.appendChild(b);
  }
  if (!selectedDomain && domains.length) {
    // default first hex domain
    const hex = domains.find((d) => d.kind === "hex") || domains[0];
    await selectDomain(hex.id);
  }
}

async function selectDomain(id) {
  selectedDomain = id;
  selectedInstance = null;
  document.querySelectorAll("#domains .chip").forEach((b, i) => {
    b.classList.toggle("active", domains[i] && domains[i].id === id);
  });
  // re-render chips properly
  const box = $("domains");
  box.innerHTML = "";
  for (const d of domains) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip" + (d.id === id ? " active" : "");
    b.innerHTML = `${d.label} <span class="n">(${d.count})</span>`;
    b.onclick = () => selectDomain(d.id);
    box.appendChild(b);
  }

  const data = await api("/api/problems?" + new URLSearchParams({ domain: id }));
  instances = data.problems || [];
  const list = $("instances");
  list.innerHTML = "";
  if (!instances.length) {
    list.innerHTML = '<span class="hint">No instances</span>';
    return;
  }
  for (const p of instances) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "inst";
    b.dataset.path = p.path;
    let badges = "";
    if (p.has_partial) {
      badges += `<span class="badge book">book×${p.partial_layers || 0}</span>`;
      if (p.partial_status === "SAT")
        badges += `<span class="badge sat">SAT</span>`;
      else if (p.partial_status)
        badges += `<span class="badge">${p.partial_status}</span>`;
    }
    if (p.qbf_status) {
      const cls = p.qbf_status === "SAT" ? "sat" : "";
      badges += `<span class="badge ${cls}">${p.qbf_status}${
        p.qbf_seconds != null ? " " + p.qbf_seconds + "s" : ""
      }</span>`;
    }
    b.innerHTML = `${p.label}${badges}`;
    b.onclick = () => {
      selectedInstance = p;
      document.querySelectorAll(".inst").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      log(
        `Selected ${p.label} (${p.kind}` +
          (p.qbf_status ? `, QuBi ${p.qbf_status} in ${p.qbf_seconds}s` : "") +
          ")"
      );
    };
    list.appendChild(b);
  }
  // auto-select first or hein_04_3x3-05
  const prefer =
    instances.find((p) => p.label.includes("hein_04_3x3-05")) || instances[0];
  const btn = [...list.querySelectorAll(".inst")].find(
    (x) => x.dataset.path === prefer.path
  );
  if (btn) btn.click();
}

function render() {
  if (!state) return;
  $("stMode").textContent = state.play_mode || playMode;
  $("status").textContent = state.finished
    ? state.winner
      ? `Over — ${state.winner}`
      : "Game over"
    : "Playing";
  $("tomove").textContent = state.finished ? "—" : state.to_move;
  $("depth").textContent = state.depth_bound ?? "—";
  $("moves").textContent = state.moves_played ?? "—";
  $("msg").textContent = state.message || "";

  const table = $("board");
  table.innerHTML = "";
  const cells = state.cells || {};
  const positions = Object.keys(cells);
  if (!positions.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 4;
    td.style.border = "none";
    td.style.color = "var(--muted)";
    td.textContent =
      state.kind === "grid"
        ? "Grid instance — use “QBF: win from start?”"
        : "No board";
    tr.appendChild(td);
    table.appendChild(tr);
    return;
  }
  const cols = [...new Set(positions.map((p) => p[0]))].sort();
  const rows = [
    ...new Set(positions.map((p) => parseInt(p.slice(1), 10))),
  ].sort((a, b) => a - b);
  const start = new Set(state.start_border || []);
  const end = new Set(state.end_border || []);

  for (const r of rows) {
    const tr = document.createElement("tr");
    for (const c of cols) {
      const pos = c + r;
      const td = document.createElement("td");
      if (!(pos in cells)) {
        td.style.border = "none";
        td.style.background = "transparent";
        tr.appendChild(td);
        continue;
      }
      const v = cells[pos];
      td.className =
        v === "B" || v === "black" ? "B" : v === "W" || v === "white" ? "W" : "open";
      if (state.kind === "hex") td.classList.add("hex");
      if (start.has(pos)) td.classList.add("start");
      if (end.has(pos)) td.classList.add("end");
      td.textContent = v === "open" || v === "-" ? "" : String(v)[0].toUpperCase();
      td.title = pos;
      if ((v === "open" || v === "-") && !state.finished) {
        td.onclick = () => onCell(pos);
      }
      tr.appendChild(td);
    }
    table.appendChild(tr);
  }
}

async function loadGame() {
  if (!selectedInstance) {
    log("Pick an instance first");
    return;
  }
  const p = selectedInstance;
  let mode = playMode;
  let kind = p.kind;
  if (mode === "certificate" && p.kind !== "certificate") {
    log("Certificate mode needs a Certificates domain instance");
    return;
  }
  if (p.kind === "certificate") {
    mode = "certificate";
    kind = "certificate";
  }
  if (mode === "hybrid" && p.kind !== "hex") {
    log("Hybrid mode is for Hex boards");
    mode = "qbf";
  }
  const q = new URLSearchParams({
    path: p.path,
    kind,
    mode,
  });
  if (p.domain) q.set("domain_file", p.domain);
  state = await api("/api/new?" + q);
  log(`Loaded [${mode}] ${p.label}`);
  if (mode === "certificate") {
    log("Click “AI / strategy move” for Black, then click a cell for White.");
  }
  if (mode === "hybrid" && !p.has_partial) {
    log("No partial cert yet — hybrid will use short QBF. Generate with scripts/generate_partial_certs.py");
  }
  render();
}

async function onCell(pos) {
  if (!state) return;
  try {
    if (state.kind === "certificate") {
      state = await api("/api/move", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session: state.session, position: pos }),
      });
      log(`White → ${pos}`);
    } else {
      const opp =
        playMode === "hybrid"
          ? "hybrid"
          : playMode === "qbf"
            ? "qbf"
            : "random";
      state = await api("/api/move", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session: state.session,
          position: pos,
          opponent: opp,
        }),
      });
      let msg = `You → ${pos}`;
      if (state.last_ai) {
        msg += ` · AI ${state.last_ai.color}→${state.last_ai.position} (${state.last_ai.mode})`;
      }
      log(msg);
    }
    render();
  } catch (e) {
    log("Error: " + e.message);
  }
}

async function aiMove() {
  if (!state) return;
  const mode =
    state.kind === "certificate"
      ? "strategy"
      : playMode === "hybrid"
        ? "hybrid"
        : playMode === "qbf"
          ? "qbf"
          : "random";
  try {
    log(`AI (${mode})…`);
    state = await api("/api/ai", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session: state.session, mode }),
    });
    if (state.last_ai) {
      log(
        `AI ${state.last_ai.color} → ${state.last_ai.position} (${state.last_ai.mode})`
      );
    } else log("AI done");
    render();
  } catch (e) {
    log("AI: " + e.message);
  }
}

async function undo() {
  if (!state) return;
  try {
    state = await api("/api/undo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session: state.session, undo_ai: true }),
    });
    log("Undo");
    render();
  } catch (e) {
    log("Undo: " + e.message);
  }
}

async function solve(mid) {
  if (!state) return;
  log(mid ? "QuBi mid-game…" : "QuBi from start…");
  try {
    const res = await api("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session: state.session,
        midgame: !!mid,
        encoding: "pg",
        timeout: 90,
      }),
    });
    log(
      `QBF ${res.status} (${Number(res.seconds || 0).toFixed(2)}s) — ${res.meaning || res.detail || ""}`
    );
  } catch (e) {
    log("Solve: " + e.message);
  }
}

// wire UI
document.querySelectorAll("#modes .chip").forEach((b) => {
  b.onclick = () => setMode(b.dataset.mode);
});
$("btnLoad").onclick = () => loadGame().catch((e) => log(String(e)));
$("btnReset").onclick = () => loadGame().catch((e) => log(String(e)));
$("btnUndo").onclick = () => undo();
$("btnAi").onclick = () => aiMove();
$("btnSolveInit").onclick = () => solve(false);
$("btnSolveMid").onclick = () => solve(true);

setMode("hybrid");
loadDomains().catch((e) => log(String(e)));
