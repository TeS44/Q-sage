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
  const title = $("busyTitle");
  const detail = $("busyDetail");
  if (wrap) wrap.classList.toggle("busy", busy);
  if (ban) ban.classList.toggle("on", busy);
  if (busy) {
    const msg = why || "Waiting for QBF / AI… board locked";
    // Split "Title — detail" or use whole as title
    const parts = msg.split(/\s+[—–-]\s+/);
    if (title) title.textContent = parts[0] || "Solver running";
    if (detail) detail.textContent = parts.slice(1).join(" — ") || "Board locked until the reply finishes";
  }
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

/** Parse "a1" → {col:0, row:0} */
function parsePos(label) {
  const m = /^([a-zA-Z]+)(\d+)$/.exec(label);
  if (!m) return null;
  let col = 0;
  const letters = m[1].toLowerCase();
  for (let i = 0; i < letters.length; i++) {
    col = col * 26 + (letters.charCodeAt(i) - 96);
  }
  col -= 1;
  const row = parseInt(m[2], 10) - 1;
  return { col, row };
}

/** Flat-top hex corners around (cx,cy), radius size. */
function hexPoints(cx, cy, size) {
  const pts = [];
  for (let i = 0; i < 6; i++) {
    const a = (Math.PI / 180) * (60 * i);
    pts.push([cx + size * Math.cos(a), cy + size * Math.sin(a)]);
  }
  return pts.map((p) => p.join(",")).join(" ");
}

/**
 * Little-Golem-style Hex: flat-top hexes in a rhombus.
 * col = letter (a…), row = number (1…).
 * Black borders ≈ top/bottom of rhombus edges (start/endboarder in files).
 */
function renderHexSvg(cells) {
  const table = $("board");
  const svg = $("hexSvg");
  const legend = $("hexLegend");
  if (table) table.style.display = "none";
  if (svg) svg.style.display = "block";
  if (legend) legend.style.display = "block";

  const positions = Object.keys(cells);
  const coords = {};
  let maxC = 0,
    maxR = 0;
  for (const p of positions) {
    const pr = parsePos(p);
    if (!pr) continue;
    coords[p] = pr;
    maxC = Math.max(maxC, pr.col);
    maxR = Math.max(maxR, pr.row);
  }
  const n = Math.max(maxC, maxR) + 1;
  // size scales with board
  const size = n <= 3 ? 32 : n <= 5 ? 26 : n <= 7 ? 22 : 18;
  const w = size * 2;
  const h = Math.sqrt(3) * size;

  // Pixel center for (col,row) — classic Hex rhombus (flat-top)
  function center(col, row) {
    const x = size * (1.5 * col) + size * 1.2;
    const y = h * (row + col * 0.5) + size * 1.2;
    return [x, y];
  }

  let maxX = 0,
    maxY = 0;
  const centers = {};
  for (const p of positions) {
    const { col, row } = coords[p];
    const [x, y] = center(col, row);
    centers[p] = [x, y];
    maxX = Math.max(maxX, x + size * 1.3);
    maxY = Math.max(maxY, y + size * 1.3);
  }

  // Edge markers: Black connects start↔end (usually opposite sides of rhombus)
  // Draw thick border strips along min-row / max-row edges of the rhombus
  // for visual Little Golem cues (dark = Black NW/SE, light = White NE/SW)
  const start = new Set(state.start_border || []);
  const end = new Set(state.end_border || []);

  const NS = "http://www.w3.org/2000/svg";
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  svg.setAttribute("viewBox", `0 0 ${maxX + size} ${maxY + size}`);
  svg.setAttribute("width", String(Math.min(560, maxX + size)));
  svg.setAttribute("height", String(Math.min(480, maxY + size)));

  // Background diamond (board felt)
  const bg = document.createElementNS(NS, "polygon");
  const corners = [
    center(0, 0),
    center(maxC, 0),
    center(maxC, maxR),
    center(0, maxR),
  ];
  // expand slightly
  bg.setAttribute(
    "points",
    corners
      .map(([x, y], i) => {
        const pad = size * 0.85;
        // rough outward nudge
        return `${x},${y}`;
      })
      .join(" ")
  );
  bg.setAttribute("fill", "#8b7355");
  bg.setAttribute("opacity", "0.35");
  svg.appendChild(bg);

  // Edge highlight lines for start/end borders (Black's goal sides)
  function edgePolyline(labels, cls) {
    const pts = labels
      .map((lab) => centers[lab])
      .filter(Boolean)
      .map(([x, y]) => `${x},${y}`);
    if (pts.length < 2) return;
    const pl = document.createElementNS(NS, "polyline");
    pl.setAttribute("points", pts.join(" "));
    pl.setAttribute("class", cls);
    svg.appendChild(pl);
  }
  // Order start/end by col for a clean edge
  const sortByCol = (labs) =>
    labs
      .filter((p) => centers[p])
      .sort((a, b) => coords[a].col - coords[b].col || coords[a].row - coords[b].row);
  edgePolyline(sortByCol([...start]), "edge-black");
  edgePolyline(sortByCol([...end]), "edge-black");

  // White borders ≈ left (col=0) and right (col=maxC) sides of rhombus
  const leftEdge = positions
    .filter((p) => coords[p] && coords[p].col === 0)
    .sort((a, b) => coords[a].row - coords[b].row);
  const rightEdge = positions
    .filter((p) => coords[p] && coords[p].col === maxC)
    .sort((a, b) => coords[a].row - coords[b].row);
  edgePolyline(leftEdge, "edge-white");
  edgePolyline(rightEdge, "edge-white");

  // Cells
  for (const p of positions) {
    const [cx, cy] = centers[p];
    const v = cells[p];
    const poly = document.createElementNS(NS, "polygon");
    poly.setAttribute("points", hexPoints(cx, cy, size * 0.95));
    let cls = "hex-cell open";
    if (v === "B" || v === "black") cls = "hex-cell B";
    else if (v === "W" || v === "white") cls = "hex-cell W";
    poly.setAttribute("class", cls);
    poly.dataset.pos = p;
    poly.setAttribute("title", p);

    if ((v === "open" || v === "-") && !state.finished && !busy) {
      poly.style.cursor = "pointer";
      poly.addEventListener("click", () => onCell(p));
    } else if (busy && (v === "open" || v === "-")) {
      poly.style.cursor = "wait";
    }
    svg.appendChild(poly);

    // stone circle for occupied (Little Golem look)
    if (v === "B" || v === "black" || v === "W" || v === "white") {
      const circ = document.createElementNS(NS, "circle");
      circ.setAttribute("cx", cx);
      circ.setAttribute("cy", cy);
      circ.setAttribute("r", size * 0.42);
      circ.setAttribute(
        "fill",
        v === "B" || v === "black" ? "#0d0d0d" : "#faf8f5"
      );
      circ.setAttribute(
        "stroke",
        v === "B" || v === "black" ? "#555" : "#ccc"
      );
      circ.setAttribute("stroke-width", "1.5");
      circ.style.pointerEvents = "none";
      svg.appendChild(circ);
    }

    const lab = document.createElementNS(NS, "text");
    lab.setAttribute("x", cx);
    lab.setAttribute("y", cy);
    lab.setAttribute(
      "class",
      "hex-label" +
        (v === "B" || v === "black"
          ? " onB"
          : v === "W" || v === "white"
            ? " onW"
            : "")
    );
    lab.textContent = p;
    svg.appendChild(lab);
  }

  // Column letters along top (row 0)
  for (let c = 0; c <= maxC; c++) {
    const lab = String.fromCharCode(97 + c) + "1";
    if (!centers[lab] && c === 0) {
      /* skip if no a1 */
    }
    const topLab = String.fromCharCode(97 + c) + "1";
    // place letter above first row cell of this col if exists
    const any = positions.find(
      (p) => coords[p] && coords[p].col === c && coords[p].row === 0
    );
    if (!any) continue;
    const [x, y] = centers[any];
    const t = document.createElementNS(NS, "text");
    t.setAttribute("x", x);
    t.setAttribute("y", y - size * 1.15);
    t.setAttribute("class", "coord");
    t.textContent = String.fromCharCode(97 + c);
    svg.appendChild(t);
  }
  // Row numbers along left (col 0)
  for (let r = 0; r <= maxR; r++) {
    const any = positions.find(
      (p) => coords[p] && coords[p].col === 0 && coords[p].row === r
    );
    if (!any) continue;
    const [x, y] = centers[any];
    const t = document.createElementNS(NS, "text");
    t.setAttribute("x", x - size * 1.25);
    t.setAttribute("y", y);
    t.setAttribute("class", "coord");
    t.textContent = String(r + 1);
    svg.appendChild(t);
  }
}

function renderSquareBoard(cells) {
  const table = $("board");
  const svg = $("hexSvg");
  const legend = $("hexLegend");
  if (table) table.style.display = "table";
  if (svg) {
    svg.style.display = "none";
    while (svg.firstChild) svg.removeChild(svg.firstChild);
  }
  if (legend) legend.style.display = "none";

  table.innerHTML = "";
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
      td.textContent = v === "open" || v === "-" ? "" : String(v)[0].toUpperCase();
      td.title = pos;
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

  const cells = state.cells || {};
  if (state.kind === "hex" && Object.keys(cells).length) {
    renderHexSvg(cells);
  } else {
    renderSquareBoard(cells);
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
      ? "QuBi running — computing Black’s reply"
      : "Processing move"
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
  setBusy(
    true,
    mode === "qbf" || mode === "hybrid"
      ? "QuBi running — AI move"
      : "AI thinking"
  );
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
  setBusy(
    true,
    mid ? "QuBi running — mid-game check" : "QuBi running — full puzzle"
  );
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
