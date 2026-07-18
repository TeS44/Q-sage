"""
Minimal BDDL-ish reader for occupy-style grid games (HTTT, etc.).

Domain::

    #blackactions
    :action occupy
    :parameters (?x, ?y)
    :precondition (open(?x,?y))
    :effect (black(?x,?y))
    #whiteactions
    ...

Problem::

    #boardsize
    3 3
    #init
    black(1,1)
    #depth
    9
    #blackgoal
    black(?x,?y) black(?x,?y+1) black(?x,?y+2)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Atom:
    pred: str  # open | black | white
    x: str  # e.g. "?x", "?x+1", "2"
    y: str
    negated: bool = False


@dataclass
class GridProblem:
    width: int
    height: int
    depth: int
    black_init: list[tuple[int, int]] = field(default_factory=list)
    white_init: list[tuple[int, int]] = field(default_factory=list)
    black_goals: list[list[Atom]] = field(default_factory=list)
    black_turn: str = "first"  # or "second"
    path: str | None = None


_ATOM = re.compile(
    r"(NOT\()?(open|black|white)\(([^,]+),([^)]+)\)\)?",
    re.I,
)


def _parse_atom(tok: str) -> Atom:
    tok = tok.strip()
    m = _ATOM.match(tok.replace(" ", ""))
    if not m:
        raise ValueError(f"bad atom {tok!r}")
    neg = bool(m.group(1))
    return Atom(m.group(2).lower(), m.group(3).strip(), m.group(4).strip(), neg)


def _parse_coord_expr(s: str, ax: int, ay: int, W: int, H: int) -> int | None:
    s = s.strip().replace(" ", "")
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        return int(s)
    bounds = {"xmin": 1, "ymin": 1, "xmax": W, "ymax": H}
    if s in bounds:
        return bounds[s]
    # ?x ?y ?x+k ?y-k
    m = re.fullmatch(r"\?([xy])([+-]\d+)?", s)
    if not m:
        return None
    base = ax if m.group(1) == "x" else ay
    off = int(m.group(2) or 0)
    return base + off


def load_grid_problem(path: str | Path) -> GridProblem:
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    sections: dict[str, list[str]] = {}
    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        if line.startswith("#"):
            cur = line.split()[0].lower()
            sections.setdefault(cur, [])
            rest = line[len(line.split()[0]) :].strip()
            if rest:
                sections[cur].append(rest)
            continue
        if cur:
            sections[cur].append(line)

    def lines(key: str) -> list[str]:
        for k, v in sections.items():
            if key in k:
                return v
        return []

    bs = (lines("boardsize") or ["3 3"])[0].split()
    W, H = int(bs[0]), int(bs[1])
    depth = int((lines("depth") or ["1"])[0].split()[0])

    binit: list[tuple[int, int]] = []
    winit: list[tuple[int, int]] = []
    for tok in " ".join(lines("init")).replace(",", " ").split():
        tok = tok.strip()
        m = re.match(r"(black|white)\((\d+),(\d+)\)", tok)
        if m:
            xy = (int(m.group(2)), int(m.group(3)))
            if m.group(1) == "black":
                binit.append(xy)
            else:
                winit.append(xy)

    goals: list[list[Atom]] = []
    for line in lines("blackgoal"):
        if line.strip().lower() == "false":
            continue
        atoms = [_parse_atom(t) for t in line.split() if "black" in t.lower() or "open" in t.lower() or "white" in t.lower() or t.upper().startswith("NOT")]
        # simpler split on spaces preserving atoms
        atoms = []
        for t in re.findall(r"NOT\([^)]+\)|black\([^)]+\)|white\([^)]+\)|open\([^)]+\)", line, flags=re.I):
            atoms.append(_parse_atom(t))
        if atoms:
            goals.append(atoms)

    turn = "first"
    for line in lines("blackturn"):
        turn = line.strip().split()[0].lower()

    return GridProblem(
        width=W,
        height=H,
        depth=depth,
        black_init=binit,
        white_init=winit,
        black_goals=goals,
        black_turn=turn,
        path=str(path),
    )


def eval_goal_shape(
    shape: list[Atom], ax: int, ay: int, W: int, H: int
) -> list[tuple[int, int, bool]] | None:
    """
    Instantiate a black-goal shape at anchor (ax,ay).
    Returns list of (x,y,negated) cells that must be black, or None if OOB.
    """
    cells: list[tuple[int, int, bool]] = []
    for atom in shape:
        if atom.pred != "black":
            return None
        x = _parse_coord_expr(atom.x, ax, ay, W, H)
        y = _parse_coord_expr(atom.y, ax, ay, W, H)
        if x is None or y is None or not (1 <= x <= W and 1 <= y <= H):
            return None
        cells.append((x, y, atom.negated))
    return cells
