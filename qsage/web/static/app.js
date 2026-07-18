const $ = (id) => document.getElementById(id);

let domains = [];
let instances = [];
let selectedDomain = null;
let selectedInstance = null;
let playMode = "qbf"; // qbf | hybrid | certificate
let state = null;
/** True while a move/AI/solve request is in flight — blocks further clicks. */
let busy = false;

function log(msg) {
  const el = $("log");
  el.textContent = `[${new Date().toLocaleTimeString()}] ${msg}\n` + el.textContent;
}

function setBusy(on, why) {
  busy = !!on;
  const wrap = $("board-wrap");
  const ban = $("busyBanner");
  if (wrap) wrap.classList.toggle("busy", busy);
  if (ban) {
    ban.classList.toggle("on", busy);
    if (why) ban.textContent = why;
    else if (busy) ban.textContent = "Waiting for QBF / AI… board locked";
  }
  // disable primary action buttons while busy
  for (const id of [
    "btnLoad",
    "btnReset",
    "btnUndo",
    "btnAi",
    "btnSolveInit",
    "btnSolveMid",
  ]) {
    const el = $(id);
    if (el) el.disabled = busy;
  }
  // re-render so cell handlers respect busy
  if (state) render();
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

const MODE_HINT = {
  qbf: "QBF solver: after your move the board locks until QuBi replies.",
  hybrid:
    "Hybrid: partial cert openings then QBF. Board locks until the reply.",
  certificate:
    "Certificate: play against a precomputed strategy. Use Certificates domain.",
};

function setMode(mode) {
  if (busy) return;
  playMode = mode;
  document.querySelectorAll("#modes .chip").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === mode);
  });
  $("modeHint").textContent = MODE_HINT[mode] || "";
  $("stMode").textContent = mode;
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
    b.onclick = () => {
      if (!busy) selectDomain(d.id);
    };
    box.appendChild(b);
  }
  if (!selectedDomain && domains.length) {
    const hex = domains.find((d) => d.kind === "hex") || domains[0];
    await selectDomain(hex.id);
  }
}

async function selectDomain(id) {
  if (busy) return;
  selectedDomain = id;
  selectedInstance = null;
  const box = $("domains");
  box.innerHTML = "";
  for (const d of domains) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip" + (d.id === id ? " active" : "");
    b.innerHTML = `${d.label} <span class="n">(${d.count})</span>`;
    b.onclick = () => {
      if (!busy) selectDomain(d.id);
    };
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
    if (p.qbf_status) {
      const cls = p.qbf_status === "SAT" ? "sat" : "";
      badges += `<span class="badge ${cls}">${p.qbf_status}${
        p.qbf_seconds != null ? " " + p.qbf_seconds + "s" : ""
      }</span>`;
    }
    b.innerHTML = `${p.label}${badges}`;
    b.onclick = () => {
      if (busy) return;
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
  $("status").textContent = busy
    ? "Waiting for solver…"
    : state.finished
      ? state.winner
        ? `Over — ${state.winner}`
        : "Game over"
      : "Playing";
  $("tomove").textContent = busy
    ? "—"
    : state.finished
      ? "—"
      : state.to_move;
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
      // Only accept clicks when not busy, game open, and cell open
      if ((v === "open" || v === "-") && !state.finished && !busy) {
        td.onclick = () => onCell(pos);
      } else if (busy && (v === "open" || v === "-")) {
        td.style.cursor = "wait";
      }
      tr.appendChild(td);
    }
    table.appendChild(tr);
  }
}

async function loadGame() {
  if (busy) return;
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
  const q = new URLSearchParams({ path: p.path, kind, mode });
  if (p.domain) q.set("domain_file", p.domain);
  setBusy(true, "Loading…");
  try {
    state = await api("/api/new?" + q);
    log(`Loaded [${mode}] ${p.label}`);
    if (mode === "certificate") {
      log("Click “AI / strategy move” for Black, then click a cell for White.");
    }
  } catch (e) {
    log("Load: " + e.message);
  } finally {
    setBusy(false);
  }
  render();
}

async function onCell(pos) {
  if (!state || busy) return;
  // Prefer opponent that needs a solver reply
  const opp =
    state.kind === "certificate"
      ? null
      : playMode === "hybrid"
        ? "hybrid"
        : playMode === "qbf"
          ? "qbf"
          : "random";

  const waitingForSolver = opp === "qbf" || opp === "hybrid";
  setBusy(
    true,
    waitingForSolver
      ? "Your move sent — waiting for QBF…"
      : "Processing move…"
  );
  try {
    if (state.kind === "certificate") {
      state = await api("/api/move", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session: state.session, position: pos }),
      });
      log(`White → ${pos}`);
    } else {
      state = await api("/api/move", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session: state.session,
          position: pos,
          opponent: opp,
          timeout: 3,
        }),
      });
      let msg = `You → ${pos}`;
      if (state.last_ai) {
        msg += ` · AI ${state.last_ai.color}→${state.last_ai.position} (${state.last_ai.mode})`;
      } else if (waitingForSolver && !state.finished) {
        msg += " · (no AI move — maybe not Black’s turn or game over)";
      }
      log(msg);
    }
  } catch (e) {
    log("Error: " + e.message);
  } finally {
    setBusy(false);
  }
  render();
}

async function aiMove() {
  if (!state || busy) return;
  const mode =
    state.kind === "certificate"
      ? "strategy"
      : playMode === "hybrid"
        ? "hybrid"
        : playMode === "qbf"
          ? "qbf"
          : "random";
  setBusy(true, mode === "qbf" || mode === "hybrid" ? "QBF thinking…" : "AI…");
  try {
    log(`AI (${mode})…`);
    state = await api("/api/ai", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session: state.session, mode, timeout: 3 }),
    });
    if (state.last_ai) {
      log(
        `AI ${state.last_ai.color} → ${state.last_ai.position} (${state.last_ai.mode})`
      );
    } else log("AI done");
  } catch (e) {
    log("AI: " + e.message);
  } finally {
    setBusy(false);
  }
  render();
}

async function undo() {
  if (!state || busy) return;
  setBusy(true, "Undo…");
  try {
    state = await api("/api/undo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session: state.session, undo_ai: true }),
    });
    log("Undo");
  } catch (e) {
    log("Undo: " + e.message);
  } finally {
    setBusy(false);
  }
  render();
}

async function solve(mid) {
  if (!state || busy) return;
  setBusy(true, mid ? "QuBi mid-game…" : "QuBi from start…");
  log(mid ? "QuBi mid-game…" : "QuBi from start…");
  try {
    const res = await api("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session: state.session,
        midgame: !!mid,
        encoding: "pg",
        timeout: 3,
      }),
    });
    log(
      `QBF ${res.status} (${Number(res.seconds || 0).toFixed(2)}s) — ${res.meaning || res.detail || ""}`
    );
  } catch (e) {
    log("Solve: " + e.message);
  } finally {
    setBusy(false);
  }
  render();
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

setMode("qbf");
loadDomains().catch((e) => log(String(e)));
