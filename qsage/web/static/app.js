const $ = (id) => document.getElementById(id);
let state = null;
let catalog = [];

function log(msg) {
  const el = $("log");
  const t = new Date().toLocaleTimeString();
  el.textContent = `[${t}] ${msg}\n` + el.textContent;
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

async function loadList() {
  const data = await api("/api/problems");
  catalog = data.problems || [];
  const sel = $("problem");
  sel.innerHTML = "";
  let lastGroup = null;
  for (const p of catalog) {
    if (p.group !== lastGroup) {
      const og = document.createElement("optgroup");
      og.label = p.group;
      og.id = "g-" + p.group.replace(/\W+/g, "_");
      sel.appendChild(og);
      lastGroup = p.group;
    }
    const o = document.createElement("option");
    o.value = JSON.stringify({ path: p.path, kind: p.kind, domain: p.domain });
    o.textContent = p.label;
    sel.lastChild.appendChild(o);
  }
  log(`Loaded ${catalog.length} benchmarks`);
}

function selected() {
  try {
    return JSON.parse($("problem").value);
  } catch {
    return null;
  }
}

function render() {
  if (!state) return;
  $("kind").textContent = state.kind || "—";
  $("depth").textContent = state.depth_bound ?? "—";
  $("moves").textContent = state.moves_played ?? "—";
  $("tomove").textContent = state.finished ? "—" : state.to_move;
  $("status").textContent = state.finished
    ? state.winner
      ? `Over — ${state.winner}`
      : "Game over"
    : "Playing";
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
        ? "No board UI for this grid encoding — use QBF buttons."
        : "No cells";
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
      td.className = v === "B" || v === "black" ? "B" : v === "W" || v === "white" ? "W" : "open";
      if (state.kind === "hex") td.classList.add("hex");
      if (start.has(pos)) td.classList.add("start");
      if (end.has(pos)) td.classList.add("end");
      td.textContent = v === "open" ? "" : v[0].toUpperCase();
      td.title = pos;
      if ((v === "open" || v === "-") && !state.finished) {
        td.onclick = () => play(pos);
      }
      tr.appendChild(td);
    }
    table.appendChild(tr);
  }
}

async function loadGame() {
  const s = selected();
  if (!s) return;
  const q = new URLSearchParams({ path: s.path, kind: s.kind || "hex" });
  if (s.domain) q.set("domain", s.domain);
  state = await api("/api/new?" + q);
  log(`Loaded ${s.kind}: ${s.path}`);
  if (s.kind === "certificate") {
    $("opponent").value = "strategy";
    log("Certificate game: click “AI move” for Black strategy, then click a cell for White.");
  }
  render();
}

async function play(pos) {
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
      const opp = $("opponent").value;
      state = await api("/api/move", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session: state.session,
          position: pos,
          opponent: opp === "strategy" ? "none" : opp,
        }),
      });
      let msg = `Move → ${pos}`;
      if (state.last_ai) {
        msg += `; AI ${state.last_ai.color} → ${state.last_ai.position} (${state.last_ai.mode})`;
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
      : $("opponent").value === "qbf"
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
      log(`AI ${state.last_ai.color} → ${state.last_ai.position} (${state.last_ai.mode})`);
    } else {
      log("AI move done");
    }
    render();
  } catch (e) {
    log("AI error: " + e.message);
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

async function solve(midgame) {
  if (!state) return;
  log(midgame ? "QuBi mid-game…" : "QuBi from start…");
  try {
    const res = await api("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session: state.session,
        midgame: !!midgame,
        encoding: "pg",
      }),
    });
    log(
      `QBF ${res.status} (${(res.seconds || 0).toFixed?.(2) ?? res.seconds}s) — ${res.meaning || res.detail || ""}`
    );
  } catch (e) {
    log("Solve error: " + e.message);
  }
}

$("btnLoad").onclick = () => loadGame().catch((e) => log(String(e)));
$("btnReset").onclick = () => loadGame().catch((e) => log(String(e)));
$("btnUndo").onclick = () => undo();
$("btnAi").onclick = () => aiMove();
$("btnSolveInit").onclick = () => solve(false);
$("btnSolveMid").onclick = () => solve(true);

loadList()
  .then(() => {
    // prefer a small hex default
    const sel = $("problem");
    for (const o of sel.options) {
      if (o.value.includes("hein_04_3x3-05")) {
        o.selected = true;
        break;
      }
    }
    return loadGame();
  })
  .catch((e) => log(String(e)));
