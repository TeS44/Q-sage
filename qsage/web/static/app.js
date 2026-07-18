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

/** Flat-top hex corners (E, SE, SW, W, NW, NE). */
function hexCorners(cx, cy, size) {
  const pts = [];
  for (let i = 0; i < 6; i++) {
    const a = (Math.PI / 180) * (60 * i);
    pts.push([cx + size * Math.cos(a), cy + size * Math.sin(a)]);
  }
  return pts;
}

function hexPoints(cx, cy, size) {
  return hexCorners(cx, cy, size)
    .map((p) => p.join(","))
    .join(" ");
}

/**
 * Clean Hex board (Little-Golem inspired).
 *
 * Honeycomb of wood hexes; four thin goal rails on the outer rim
 * (black opposite sides, red opposite sides). No floating captions,
 * no glow bands, no labels on empty cells.
 */
function renderHexSvg(cells) {
  const table = $("board");
  const svg = $("hexSvg");
  const legend = $("hexLegend");
  if (table) table.style.display = "none";
  const gridSvgHide = $("gridSvg");
  if (gridSvgHide) {
    gridSvgHide.style.display = "none";
    while (gridSvgHide.firstChild) gridSvgHide.removeChild(gridSvgHide.firstChild);
  }
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
  const size = n <= 3 ? 34 : n <= 5 ? 28 : n <= 7 ? 22 : 18;
  const h = Math.sqrt(3) * size;
  const margin = size * 1.85;

  function center(col, row) {
    return [
      size * (1.5 * col) + margin,
      h * (row + col * 0.5) + margin,
    ];
  }

  const centers = {};
  let maxX = 0,
    maxY = 0;
  for (const p of positions) {
    const { col, row } = coords[p];
    const [x, y] = center(col, row);
    centers[p] = [x, y];
    maxX = Math.max(maxX, x + size);
    maxY = Math.max(maxY, y + size);
  }

  const NS = "http://www.w3.org/2000/svg";
  while (svg.firstChild) svg.removeChild(svg.firstChild);

  const vbW = maxX + margin * 0.7;
  const vbH = maxY + margin * 0.7;
  svg.setAttribute("viewBox", `0 0 ${vbW} ${vbH}`);
  svg.setAttribute("width", String(Math.min(640, vbW)));
  svg.setAttribute("height", String(Math.min(560, vbH)));

  // Warm board surface (not dark navy)
  const page = document.createElementNS(NS, "rect");
  page.setAttribute("x", 0);
  page.setAttribute("y", 0);
  page.setAttribute("width", vbW);
  page.setAttribute("height", vbH);
  page.setAttribute("rx", "12");
  page.setAttribute("class", "hex-page");
  svg.appendChild(page);

  // Centroid for outward normals
  let bx = 0,
    by = 0,
    bn = 0;
  for (const [x, y] of Object.values(centers)) {
    bx += x;
    by += y;
    bn++;
  }
  bx /= bn || 1;
  by /= bn || 1;

  function outward(labs, dist) {
    const pts = labs.map((lab) => centers[lab]).filter(Boolean);
    if (!pts.length) return null;
    const mid = pts[Math.floor(pts.length / 2)];
    let ox = mid[0] - bx;
    let oy = mid[1] - by;
    const L = Math.hypot(ox, oy) || 1;
    ox = (ox / L) * dist;
    oy = (oy / L) * dist;
    return pts.map(([x, y]) => [x + ox, y + oy]);
  }

  function polyline(pts, cls) {
    if (!pts || pts.length < 2) return;
    // Extend ends slightly so corners meet
    const p = pts.map((q) => q.slice());
    const dx0 = p[1][0] - p[0][0];
    const dy0 = p[1][1] - p[0][1];
    const l0 = Math.hypot(dx0, dy0) || 1;
    p[0][0] -= (dx0 / l0) * size * 0.35;
    p[0][1] -= (dy0 / l0) * size * 0.35;
    const i = p.length - 1;
    const dx1 = p[i][0] - p[i - 1][0];
    const dy1 = p[i][1] - p[i - 1][1];
    const l1 = Math.hypot(dx1, dy1) || 1;
    p[i][0] += (dx1 / l1) * size * 0.35;
    p[i][1] += (dy1 / l1) * size * 0.35;
    const el = document.createElementNS(NS, "polyline");
    el.setAttribute("points", p.map(([x, y]) => `${x},${y}`).join(" "));
    el.setAttribute("class", cls);
    svg.appendChild(el);
  }

  const sortByCol = (labs) =>
    labs
      .filter((p) => centers[p])
      .sort(
        (a, b) =>
          coords[a].col - coords[b].col || coords[a].row - coords[b].row
      );
  const sortByRow = (labs) =>
    labs
      .filter((p) => centers[p])
      .sort(
        (a, b) =>
          coords[a].row - coords[b].row || coords[a].col - coords[b].col
      );

  const startEdge = sortByCol([...(state.start_border || [])]);
  const endEdge = sortByCol([...(state.end_border || [])]);
  const leftEdge = sortByRow(
    positions.filter((p) => coords[p] && coords[p].col === 0)
  );
  const rightEdge = sortByRow(
    positions.filter((p) => coords[p] && coords[p].col === maxC)
  );

  // Soft wood mat under the honeycomb
  {
    const corners = [
      center(0, 0),
      center(maxC, 0),
      center(maxC, maxR),
      center(0, maxR),
    ].map(([x, y]) => {
      const ox = x - bx;
      const oy = y - by;
      const L = Math.hypot(ox, oy) || 1;
      const d = size * 0.72;
      return [x + (ox / L) * d, y + (oy / L) * d];
    });
    const mat = document.createElementNS(NS, "polygon");
    mat.setAttribute(
      "points",
      corners.map(([x, y]) => `${x},${y}`).join(" ")
    );
    mat.setAttribute("class", "hex-mat");
    svg.appendChild(mat);
  }

  // Goal rails — thin, clean (under cells)
  const railDist = size * 0.88;
  polyline(outward(startEdge, railDist), "hex-rail-B");
  polyline(outward(endEdge, railDist), "hex-rail-B");
  polyline(outward(leftEdge, railDist), "hex-rail-W");
  polyline(outward(rightEdge, railDist), "hex-rail-W");

  // Win path prep
  const pathSet = new Set(state.winning_path || []);
  let pathColor =
    state.winner_color ||
    ((state.winner || "").startsWith("Black")
      ? "B"
      : (state.winner || "").startsWith("White")
        ? "W"
        : null);
  // Only Black connection paths are win paths mid-game (QBF Hex).
  if (!pathSet.size) {
    const bp = findBlackPath(cells, state);
    if (bp.length) {
      bp.forEach((p) => pathSet.add(p));
      pathColor = pathColor || "B";
    }
  }

  // Honeycomb cells (tight pack)
  for (const p of positions) {
    const [cx, cy] = centers[p];
    const v = cells[p];
    const poly = document.createElementNS(NS, "polygon");
    poly.setAttribute("points", hexPoints(cx, cy, size * 0.97));
    let cls = "hex-cell open";
    if (v === "B" || v === "black") cls = "hex-cell filled";
    else if (v === "W" || v === "white") cls = "hex-cell filled";
    if (pathSet.has(p)) {
      cls += pathColor === "W" ? " on-path-W" : " on-path";
    }
    poly.setAttribute("class", cls);
    poly.dataset.pos = p;
    poly.setAttribute("title", p);

    const canClick =
      (v === "open" || v === "-") &&
      !state.finished &&
      !busy &&
      state.your_turn !== false;
    if (canClick) {
      poly.style.cursor = "pointer";
      poly.addEventListener("click", () => onCell(p));
    } else if (busy && (v === "open" || v === "-")) {
      poly.style.cursor = "wait";
    } else if ((v === "open" || v === "-") && state.your_turn === false) {
      poly.style.cursor = "not-allowed";
    }
    svg.appendChild(poly);

    const isB = v === "B" || v === "black";
    const isW = v === "W" || v === "white";
    if (isB || isW) {
      const circ = document.createElementNS(NS, "circle");
      circ.setAttribute("cx", cx);
      circ.setAttribute("cy", cy);
      circ.setAttribute("r", size * 0.48);
      circ.setAttribute("class", isB ? "hex-stone-B" : "hex-stone-W");
      circ.style.pointerEvents = "none";
      svg.appendChild(circ);
    }
  }

  // Win path (subtle)
  if (pathSet.size >= 2) {
    const order =
      state.winning_path && state.winning_path.length
        ? state.winning_path
        : [...pathSet];
    const pts = order
      .map((p) => centers[p])
      .filter(Boolean)
      .map(([x, y]) => `${x},${y}`)
      .join(" ");
    if (pts) {
      const pl = document.createElementNS(NS, "polyline");
      pl.setAttribute("points", pts);
      pl.setAttribute("class", pathColor === "W" ? "win-path-W" : "win-path");
      svg.appendChild(pl);
    }
  }

  // Outside coords only (a,b,c… and 1,2,3…)
  for (let c = 0; c <= maxC; c++) {
    const any = positions.find(
      (p) => coords[p] && coords[p].col === c && coords[p].row === 0
    );
    if (!any) continue;
    const [x, y] = centers[any];
    const t = document.createElementNS(NS, "text");
    t.setAttribute("x", x);
    t.setAttribute("y", y - size * 1.35);
    t.setAttribute("class", "hex-coord");
    t.textContent = String.fromCharCode(97 + c);
    svg.appendChild(t);
  }
  for (let r = 0; r <= maxR; r++) {
    const any = positions.find(
      (p) => coords[p] && coords[p].col === 0 && coords[p].row === r
    );
    if (!any) continue;
    const [x, y] = centers[any];
    const t = document.createElementNS(NS, "text");
    t.setAttribute("x", x - size * 1.35);
    t.setAttribute("y", y);
    t.setAttribute("class", "hex-coord");
    t.textContent = String(r + 1);
    svg.appendChild(t);
  }
}

function _bfsOwnedPath(owned, starts, ends, neigh) {
  const parent = {};
  const q = [];
  for (const s of starts) {
    if (!owned.has(s)) continue;
    parent[s] = null;
    q.push(s);
  }
  if (!q.length) return [];
  let found = null;
  while (q.length) {
    const u = q.shift();
    if (ends.has(u)) {
      found = u;
      break;
    }
    for (const v of neigh[u] || []) {
      if (owned.has(v) && !(v in parent)) {
        parent[v] = u;
        q.push(v);
      }
    }
  }
  if (!found) return [];
  const path = [];
  let cur = found;
  while (cur != null) {
    path.push(cur);
    cur = parent[cur];
  }
  path.reverse();
  return path;
}

/** BFS Black path start_border → end_border using state.neighbours */
function findBlackPath(cells, st) {
  const owned = new Set(
    Object.keys(cells).filter((p) => cells[p] === "B" || cells[p] === "black")
  );
  const starts = (st.start_border || []).filter((p) => owned.has(p));
  const ends = new Set((st.end_border || []).filter((p) => owned.has(p)));
  if (!starts.length || !ends.size) return [];
  return _bfsOwnedPath(owned, starts, ends, st.neighbours || {});
}

/** BFS White path left column (col 0) → right column (maxC) */
function findWhitePath(cells, st, maxC) {
  const owned = new Set(
    Object.keys(cells).filter((p) => cells[p] === "W" || cells[p] === "white")
  );
  const left =
    (st.white_borders && st.white_borders.left) ||
    Object.keys(cells).filter((p) => {
      const pr = parsePos(p);
      return pr && pr.col === 0;
    });
  const right =
    (st.white_borders && st.white_borders.right) ||
    Object.keys(cells).filter((p) => {
      const pr = parsePos(p);
      return pr && pr.col === maxC;
    });
  const starts = left.filter((p) => owned.has(p));
  const ends = new Set(right.filter((p) => owned.has(p)));
  if (!starts.length || !ends.size) return [];
  return _bfsOwnedPath(owned, starts, ends, st.neighbours || {});
}

/**
 * Little-Golem-style square grid: wooden board, grid lines, stones on cells.
 */
function renderGridSvg(cells) {
  const table = $("board");
  const hexSvg = $("hexSvg");
  const gridSvg = $("gridSvg");
  const legend = $("hexLegend");
  if (table) table.style.display = "none";
  if (hexSvg) {
    hexSvg.style.display = "none";
    while (hexSvg.firstChild) hexSvg.removeChild(hexSvg.firstChild);
  }
  if (legend) legend.style.display = "none";
  if (!gridSvg) return;
  gridSvg.style.display = "block";
  while (gridSvg.firstChild) gridSvg.removeChild(gridSvg.firstChild);

  const w = state.board_w || state.width || 3;
  const h = state.board_h || state.height || 3;
  const cell = w <= 4 ? 48 : w <= 6 ? 40 : 32;
  const pad = 28;
  const boardW = w * cell;
  const boardH = h * cell;
  const NS = "http://www.w3.org/2000/svg";

  gridSvg.setAttribute(
    "viewBox",
    `0 0 ${boardW + pad * 2} ${boardH + pad * 2}`
  );
  gridSvg.setAttribute("width", String(Math.min(420, boardW + pad * 2)));
  gridSvg.setAttribute("height", String(Math.min(420, boardH + pad * 2)));

  // wood panel
  const wood = document.createElementNS(NS, "rect");
  wood.setAttribute("x", pad - 6);
  wood.setAttribute("y", pad - 6);
  wood.setAttribute("width", boardW + 12);
  wood.setAttribute("height", boardH + 12);
  wood.setAttribute("rx", "8");
  wood.setAttribute("class", "wood");
  gridSvg.appendChild(wood);

  // grid lines (cell boundaries)
  for (let i = 0; i <= w; i++) {
    const line = document.createElementNS(NS, "line");
    line.setAttribute("x1", pad + i * cell);
    line.setAttribute("y1", pad);
    line.setAttribute("x2", pad + i * cell);
    line.setAttribute("y2", pad + boardH);
    line.setAttribute("class", "grid-line");
    gridSvg.appendChild(line);
  }
  for (let j = 0; j <= h; j++) {
    const line = document.createElementNS(NS, "line");
    line.setAttribute("x1", pad);
    line.setAttribute("y1", pad + j * cell);
    line.setAttribute("x2", pad + boardW);
    line.setAttribute("y2", pad + j * cell);
    line.setAttribute("class", "grid-line");
    gridSvg.appendChild(line);
  }

  const winCells = new Set(state.winning_cells || []);
  const winColor =
    state.winner_color ||
    ((state.winner || "").startsWith("Black")
      ? "B"
      : (state.winner || "").startsWith("White")
        ? "W"
        : null);

  // cells: x=1..w left→right, y=1..h bottom→top (chess-like)
  for (let x = 1; x <= w; x++) {
    for (let y = 1; y <= h; y++) {
      const lab = String.fromCharCode(96 + x) + y;
      const v = cells[lab] || "open";
      // SVG y grows down; put y=1 at bottom
      const cx = pad + (x - 0.5) * cell;
      const cy = pad + (h - y + 0.5) * cell;

      // hit target
      const hit = document.createElementNS(NS, "rect");
      hit.setAttribute("x", pad + (x - 1) * cell);
      hit.setAttribute("y", pad + (h - y) * cell);
      hit.setAttribute("width", cell);
      hit.setAttribute("height", cell);
      let hitCls = "cell-hit";
      if (winCells.has(lab)) {
        hitCls += winColor === "W" ? " win-cell-W" : " win-cell-B";
      }
      hit.setAttribute("class", hitCls);
      hit.dataset.pos = lab;
      hit.setAttribute("title", lab);
      // Legal anchors for hover pair-highlight (domineering)
      const yourActs = state.your_legal_actions || [];
      const actByAnchor = Object.fromEntries(
        yourActs.map((a) => [a.anchor, a])
      );
      const isAnchor = lab in actByAnchor;
      const canClick =
        isAnchor &&
        !state.finished &&
        !busy &&
        state.your_turn !== false;
      if (canClick) {
        hit.style.cursor = "pointer";
        hit.addEventListener("click", () => onCell(lab));
        hit.addEventListener("mouseenter", () => {
          const a = actByAnchor[lab];
          setPreview(a.cells || [lab], lab);
        });
        hit.addEventListener("mouseleave", () => clearPreview());
      } else if (busy) {
        hit.style.cursor = "wait";
      } else {
        hit.style.cursor = "default";
        // still allow hover if this cell is part of some legal action's pair
        const partOf = yourActs.find((a) => (a.cells || []).includes(lab));
        if (partOf && state.your_turn) {
          hit.style.pointerEvents = "auto";
          hit.addEventListener("mouseenter", () =>
            setPreview(partOf.cells, partOf.anchor)
          );
          hit.addEventListener("mouseleave", () => clearPreview());
        } else {
          hit.style.pointerEvents = "none";
        }
      }
      gridSvg.appendChild(hit);

      if (v === "B" || v === "black" || v === "W" || v === "white") {
        const isB = v === "B" || v === "black";
        const circ = document.createElementNS(NS, "circle");
        circ.setAttribute("cx", cx);
        circ.setAttribute("cy", cy);
        circ.setAttribute("r", cell * 0.36);
        let scls = isB ? "stone-B" : "stone-W";
        if (winCells.has(lab)) {
          scls += winColor === "W" ? " stone-win-W" : " stone-win-B";
        }
        circ.setAttribute("class", scls);
        circ.style.pointerEvents = "none";
        gridSvg.appendChild(circ);
        const mark = document.createElementNS(NS, "text");
        mark.setAttribute("x", cx);
        mark.setAttribute("y", cy);
        mark.setAttribute("class", "stone-label " + (isB ? "onB" : "onW"));
        mark.textContent = isB ? "B" : "W";
        gridSvg.appendChild(mark);
      }
    }
  }

  // Win line through goal cells (connect-k)
  if (winCells.size >= 2 && state.winning_cells && state.winning_cells.length) {
    const pts = state.winning_cells
      .map((lab) => {
        const m = /^([a-zA-Z]+)(\d+)$/.exec(lab);
        if (!m) return null;
        let xi = 0;
        for (const ch of m[1].toLowerCase()) {
          xi = xi * 26 + (ch.charCodeAt(0) - 96);
        }
        const yi = parseInt(m[2], 10);
        const cx = pad + (xi - 0.5) * cell;
        const cy = pad + (h - yi + 0.5) * cell;
        return `${cx},${cy}`;
      })
      .filter(Boolean)
      .join(" ");
    if (pts) {
      const pl = document.createElementNS(NS, "polyline");
      pl.setAttribute("points", pts);
      pl.setAttribute(
        "class",
        winColor === "W" ? "grid-win-path-W" : "grid-win-path-B"
      );
      gridSvg.appendChild(pl);
    }
  }

  // coordinates
  for (let x = 1; x <= w; x++) {
    const t = document.createElementNS(NS, "text");
    t.setAttribute("x", pad + (x - 0.5) * cell);
    t.setAttribute("y", pad + boardH + 16);
    t.setAttribute("class", "coord");
    t.textContent = String.fromCharCode(96 + x);
    gridSvg.appendChild(t);
  }
  for (let y = 1; y <= h; y++) {
    const t = document.createElementNS(NS, "text");
    t.setAttribute("x", pad - 12);
    t.setAttribute("y", pad + (h - y + 0.5) * cell);
    t.setAttribute("class", "coord");
    t.textContent = String(y);
    gridSvg.appendChild(t);
  }
}

function renderSquareBoard(cells) {
  // Prefer Little-Golem SVG grid when we have board dimensions
  if (state && (state.board_w || state.width) && Object.keys(cells).length) {
    renderGridSvg(cells);
    return;
  }
  const table = $("board");
  const hexSvg = $("hexSvg");
  const gridSvg = $("gridSvg");
  const legend = $("hexLegend");
  if (table) table.style.display = "table";
  if (hexSvg) {
    hexSvg.style.display = "none";
    while (hexSvg.firstChild) hexSvg.removeChild(hexSvg.firstChild);
  }
  if (gridSvg) {
    gridSvg.style.display = "none";
    while (gridSvg.firstChild) gridSvg.removeChild(gridSvg.firstChild);
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
    td.textContent = "No board cells";
    tr.appendChild(td);
    table.appendChild(tr);
    return;
  }
  let cols, rows;
  if (state.board_w && state.board_h) {
    cols = [];
    for (let i = 0; i < state.board_w; i++) cols.push(String.fromCharCode(97 + i));
    rows = [];
    for (let j = 1; j <= state.board_h; j++) rows.push(j);
  } else {
    cols = [...new Set(positions.map((p) => p[0]))].sort();
    rows = [
      ...new Set(positions.map((p) => parseInt(p.slice(1), 10))),
    ].sort((a, b) => a - b);
  }
  const rowOrder = [...rows].reverse();
  for (const r of rowOrder) {
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
      td.textContent =
        v === "open" || v === "-"
          ? ""
          : v === "B" || v === "black"
            ? "B"
            : "W";
      td.title = pos;
      if (
        (v === "open" || v === "-") &&
        !state.finished &&
        !busy &&
        state.your_turn !== false
      ) {
        td.onclick = () => onCell(pos);
      }
      tr.appendChild(td);
    }
    table.appendChild(tr);
  }
}

/** Highlight domineering pair / hex cell on hover from legal-move list or board */
let previewCells = [];

function clearPreview() {
  previewCells = [];
  document.querySelectorAll("#gridSvg .cell-hit.preview, #gridSvg .cell-hit.preview-pair")
    .forEach((el) => {
      el.classList.remove("preview", "preview-pair");
    });
  document.querySelectorAll("#hexSvg .hex-cell.preview").forEach((el) => {
    el.classList.remove("preview");
    el.style.filter = "";
  });
  document.querySelectorAll("#legalMoves .act.hot").forEach((el) => {
    el.classList.remove("hot");
  });
}

function setPreview(cells, anchor) {
  clearPreview();
  previewCells = cells || [];
  if (!previewCells.length) return;
  // grid SVG rects
  for (const lab of previewCells) {
    const el = document.querySelector(`#gridSvg .cell-hit[data-pos="${lab}"]`);
    if (el) {
      el.classList.add(lab === anchor ? "preview" : "preview-pair");
    }
  }
  // hex polygons
  for (const lab of previewCells) {
    const el = document.querySelector(`#hexSvg .hex-cell[data-pos="${lab}"]`);
    if (el) {
      el.classList.add("preview");
      el.style.filter = "brightness(1.25)";
      el.style.stroke = "#f5a524";
      el.style.strokeWidth = "3";
    }
  }
  document.querySelectorAll("#legalMoves .act").forEach((btn) => {
    if (btn.dataset.anchor === anchor) btn.classList.add("hot");
  });
}

function renderLegalMoves() {
  const box = $("legalMoves");
  const help = $("actionHelp");
  if (!box) return;
  if (!state) {
    box.innerHTML = '<span class="hint">—</span>';
    if (help) help.textContent = "Load a game to see possible actions.";
    return;
  }
  if (help) {
    help.textContent =
      state.action_help ||
      (state.your_turn
        ? "Click a listed action or a highlighted cell."
        : "Wait for the opponent.");
  }
  const acts = state.your_legal_actions || state.legal_actions || [];
  if (!state.your_turn) {
    box.innerHTML =
      '<span class="hint">Not your turn — no actions for you right now.</span>';
    return;
  }
  if (!acts.length) {
    box.innerHTML = '<span class="hint">No legal moves (game may be over).</span>';
    return;
  }
  box.innerHTML = "";
  for (const a of acts) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "act";
    b.dataset.anchor = a.anchor;
    b.innerHTML = `${a.label}<div class="cells">${(a.cells || []).join(" · ")}</div>`;
    b.title = a.description || a.label;
    b.onmouseenter = () => setPreview(a.cells || [a.anchor], a.anchor);
    b.onmouseleave = () => clearPreview();
    b.onclick = () => {
      if (!busy) onCell(a.anchor);
    };
    box.appendChild(b);
  }
}

function updateColorBanner() {
  const you = $("pillYou");
  const opp = $("pillOpp");
  const turn = $("turnLine");
  if (!you || !opp || !turn) return;
  if (!state) {
    you.textContent = "You: —";
    opp.textContent = "Opponent: —";
    turn.textContent = "Load an instance to play";
    turn.className = "turn-line";
    return;
  }
  const youAre = state.you_are || (state.human_color === "B" ? "Black" : "White");
  const oppAre = state.opponent_is || (state.ai_color === "W" ? "White" : "Black");
  const eng = state.opponent_engine || state.play_mode || "engine";
  you.className = "pill " + (youAre === "Black" ? "you-B" : "you-W");
  opp.className = "pill " + (oppAre === "Black" ? "opp-B" : "opp-W");
  you.textContent = `You: ${youAre}`;
  opp.textContent = `Opponent: ${oppAre} (${eng})`;

  if (busy) {
    turn.className = "turn-line theirs";
    turn.textContent = `Wait — ${oppAre} (${eng}) is moving…`;
  } else if (state.finished) {
    turn.className = "turn-line over";
    turn.textContent = state.winner
      ? `Game over — ${state.winner}`
      : "Game over";
  } else if (state.your_turn) {
    turn.className = "turn-line yours";
    // Prefer server turn_hint (includes “QBF played Black at …”)
    turn.textContent =
      state.turn_hint ||
      `Your turn — click an empty cell to play as ${youAre}`;
  } else {
    turn.className = "turn-line theirs";
    turn.textContent =
      state.turn_hint ||
      `Opponent’s turn — ${oppAre}. Use “AI / strategy move” if needed.`;
  }
}

function render() {
  if (!state) {
    updateColorBanner();
    return;
  }
  $("stMode").textContent = state.play_mode || playMode;
  $("status").textContent = busy
    ? "Waiting for solver…"
    : state.finished
      ? state.winner
        ? `Over — ${state.winner}`
        : "Game over"
      : "Playing";
  const toMoveLabel =
    state.to_move === "B" ? "Black" : state.to_move === "W" ? "White" : state.to_move;
  $("tomove").textContent = busy
    ? "—"
    : state.finished
      ? "—"
      : toMoveLabel + (state.your_turn ? " (you)" : " (opponent)");
  $("depth").textContent = state.depth_plies ?? state.depth_bound ?? "—";
  $("moves").textContent =
    (state.moves_played ?? "—") +
    " / " +
    (state.depth_plies ?? state.depth_bound ?? "—");
  $("msg").textContent = state.message || "";
  // Remaining moves
  const yl = $("yourLeft");
  const yt = $("yourTotal");
  const ol = $("oppLeft");
  const ot = $("oppTotal");
  const pl = $("pliesLeft");
  const de = $("depthExplain");
  if (yl) yl.textContent = state.your_moves_left ?? "—";
  if (yt) yt.textContent = state.your_moves_total ?? "—";
  if (ol) ol.textContent = state.opponent_moves_left ?? state.black_moves_left ?? "—";
  if (ot)
    ot.textContent = state.opponent_moves_total ?? state.black_moves_total ?? "—";
  if (pl) pl.textContent = state.plies_left ?? "—";
  if (de) {
    de.textContent =
      state.depth_explain ||
      "Depth = total half-moves (plies). Example: depth 5, Black first → Black 3 moves, you (White) 2.";
  }
  updateColorBanner();
  renderLegalMoves();

  const cells = state.cells || {};
  if (state.kind === "hex" && Object.keys(cells).length) {
    renderHexSvg(cells);
  } else if (Object.keys(cells).length) {
    renderSquareBoard(cells);
  } else {
    renderSquareBoard({});
  }
  // re-apply hover if any
  if (previewCells.length) {
    const a = previewCells[0];
    setPreview(previewCells, a);
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
  const needsOpeningAi =
    kind === "hex" && (mode === "qbf" || mode === "hybrid" || mode === "random");
  setBusy(
    true,
    needsOpeningAi ? "QuBi running — Black opens" : "Loading…"
  );
  try {
    // Server places Black's opening move before returning (vs AI modes)
    state = await api("/api/new?" + q);
    log(`Loaded [${mode}] ${p.label}`);
    if (state.opening_note) log(state.opening_note);
    log(
      `You are ${state.you_are || "White"} · opponent ${state.opponent_is || "Black"} (${state.opponent_engine || mode})`
    );
    if (state.last_ai && state.last_ai.color === "B") {
      log(
        `QBF/AI played Black first at ${state.last_ai.position} (${state.last_ai.mode})`
      );
      log("→ Your turn now as White — click an empty hex");
    } else if (state.needs_ai_move && kind === "hex") {
      // Fallback if server could not open
      setBusy(true, "QuBi running — Black opens");
      state = await api("/api/ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session: state.session,
          mode: mode === "hybrid" ? "hybrid" : mode === "random" ? "random" : "qbf",
          timeout: 3,
        }),
      });
      if (state.last_ai) {
        log(
          `QBF/AI played Black first at ${state.last_ai.position}`
        );
        log("→ Your turn now as White — click an empty hex");
      }
    } else if (state.your_turn && state.first_color === "W") {
      log("This instance: White moves first — your turn");
    } else if (state.your_turn) {
      log("→ Your turn as White — click an empty hex");
    }
    if (mode === "certificate") {
      log("Certificate: AI / strategy for Black, then you play White.");
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
  if (state.your_turn === false) {
    log(
      state.turn_hint ||
        `Not your turn — you are ${state.you_are || "White"}; wait for Black`
    );
    return;
  }
  if (state.to_move === "B") {
    log("Black to move (opponent). Wait for AI.");
    return;
  }
  const opp =
    state.kind === "certificate"
      ? null
      : playMode === "hybrid" && state.kind === "hex"
        ? "hybrid"
        : playMode === "qbf"
          ? "qbf"
          : playMode === "random"
            ? "random"
            : "none";

  setBusy(true, "Processing move — Black may reply…");
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
          opponent: opp || "qbf",
          timeout: 3,
        }),
      });
      if (state.you_just_played) {
        const y = state.you_just_played;
        log(`You played White at ${y.position}`);
      } else {
        log(`You → ${pos} (White)`);
      }
      if (state.opponent_just_played) {
        const o = state.opponent_just_played;
        log(
          `Black (AI) at ${o.position}` + (o.mode ? ` (${o.mode})` : "")
        );
      } else if (state.last_ai && state.last_ai.color === "B") {
        log(`Black (AI) at ${state.last_ai.position} (${state.last_ai.mode})`);
      }
      if (state.your_turn) log("→ Your turn (White)");
      if (state.finished) log(`Game over: ${state.winner || "done"}`);
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
