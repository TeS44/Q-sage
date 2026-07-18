const $ = (id) => document.getElementById(id);
const logEl = $("log");
let state = null;

function log(msg) {
  logEl.textContent = msg + "\n" + logEl.textContent;
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json();
}

async function loadList() {
  const data = await api("/api/problems");
  const sel = $("problem");
  sel.innerHTML = "";
  for (const p of data.problems) {
    const o = document.createElement("option");
    o.value = p.path;
    o.textContent = p.label;
    sel.appendChild(o);
  }
}

function render() {
  if (!state) return;
  $("status").textContent = state.finished
    ? state.winner
      ? `Game over — ${state.winner} wins`
      : "Game over"
    : "Playing";
  $("tomove").textContent = state.finished ? "—" : state.to_move;
  const table = $("board");
  table.innerHTML = "";
  // rectangular layout by parsing labels like a1, b2
  const cells = state.cells; // { pos: 'open'|'B'|'W' }
  const positions = Object.keys(cells);
  const cols = [...new Set(positions.map((p) => p[0]))].sort();
  const rows = [...new Set(positions.map((p) => parseInt(p.slice(1), 10)))].sort(
    (a, b) => a - b
  );
  for (const r of rows) {
    const tr = document.createElement("tr");
    for (const c of cols) {
      const pos = c + r;
      const td = document.createElement("td");
      if (!(pos in cells)) {
        td.style.border = "none";
        td.style.cursor = "default";
        tr.appendChild(td);
        continue;
      }
      const v = cells[pos];
      td.className = v === "B" ? "B" : v === "W" ? "W" : "open";
      if (state.hex) td.classList.add("hex");
      td.textContent = v === "open" ? "" : v;
      td.title = pos;
      if (v === "open" && !state.finished) {
        td.onclick = () => play(pos);
      }
      tr.appendChild(td);
    }
    table.appendChild(tr);
  }
}

async function loadGame() {
  const path = $("problem").value;
  state = await api("/api/new?" + new URLSearchParams({ path }));
  log(`Loaded ${path}`);
  render();
}

async function play(pos) {
  try {
    state = await api("/api/move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session: state.session,
        position: pos,
        auto_black: $("autoBlack").checked,
      }),
    });
    log(`Played ${pos}` + (state.last_black ? `; Black → ${state.last_black}` : ""));
    render();
  } catch (e) {
    log("Error: " + e.message);
  }
}

async function undo() {
  state = await api("/api/undo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session: state.session }),
  });
  log("Undo");
  render();
}

async function solve() {
  log("Running QuBi (may take a few seconds)…");
  try {
    const res = await api("/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session: state.session }),
    });
    log(`QuBi: ${res.status} (${res.seconds?.toFixed?.(2) ?? "?"}s) ${res.detail || ""}`);
  } catch (e) {
    log("Solve error: " + e.message);
  }
}

$("btnLoad").onclick = loadGame;
$("btnReset").onclick = loadGame;
$("btnUndo").onclick = undo;
$("btnSolve").onclick = solve;

loadList().then(loadGame).catch((e) => log(String(e)));
