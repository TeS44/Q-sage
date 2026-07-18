"""
Standalone BDDL reader for scratch grid encodings.

Parses domain actions + problem init/goals/depth. Stdlib only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Atom:
    pred: str  # open | black | white
    x: str
    y: str
    negated: bool = False


@dataclass(frozen=True)
class Action:
    name: str
    color: str  # "B" | "W"
    precondition: tuple[Atom, ...]
    effect: tuple[Atom, ...]


@dataclass
class GridDomain:
    black_actions: list[Action] = field(default_factory=list)
    white_actions: list[Action] = field(default_factory=list)
    path: str | None = None


@dataclass
class GridProblem:
    width: int
    height: int
    depth: int
    black_init: list[tuple[int, int]] = field(default_factory=list)
    white_init: list[tuple[int, int]] = field(default_factory=list)
    black_goals: list[list[Atom]] = field(default_factory=list)
    white_goals: list[list[Atom]] = field(default_factory=list)
    black_turn: str = "first"
    path: str | None = None


_ATOM = re.compile(
    r"(NOT\()?(open|black|white)\(([^,]+),([^)]+)\)\)?",
    re.I,
)


def _parse_atom(tok: str) -> Atom:
    tok = tok.strip().replace(" ", "")
    m = _ATOM.match(tok)
    if not m:
        raise ValueError(f"bad atom {tok!r}")
    return Atom(m.group(2).lower(), m.group(3).strip(), m.group(4).strip(), bool(m.group(1)))


def _parse_atoms_line(line: str) -> list[Atom]:
    return [
        _parse_atom(t)
        for t in re.findall(
            r"NOT\([^)]+\)|black\([^)]+\)|white\([^)]+\)|open\([^)]+\)",
            line,
            flags=re.I,
        )
    ]


def _sections(text: str) -> dict[str, list[str]]:
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
    return sections


def _lines(sections: dict[str, list[str]], key: str) -> list[str]:
    for k, v in sections.items():
        if key in k:
            return v
    return []


def load_domain(path: str | Path) -> GridDomain:
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    sections = _sections(text)

    def parse_actions(sec_key: str, color: str) -> list[Action]:
        lines = _lines(sections, sec_key)
        actions: list[Action] = []
        name = None
        pre: list[Atom] = []
        eff: list[Atom] = []
        mode = None
        for line in lines:
            low = line.lower()
            if low.startswith(":action"):
                if name is not None:
                    actions.append(Action(name, color, tuple(pre), tuple(eff)))
                name = line.split(None, 1)[1].strip() if len(line.split()) > 1 else "act"
                pre, eff, mode = [], [], None
            elif low.startswith(":parameters"):
                continue
            elif low.startswith(":precondition"):
                mode = "pre"
                rest = line.split(None, 1)[1] if len(line.split(None, 1)) > 1 else ""
                if rest:
                    pre.extend(_parse_atoms_line(rest))
            elif low.startswith(":effect"):
                mode = "eff"
                rest = line.split(None, 1)[1] if len(line.split(None, 1)) > 1 else ""
                if rest:
                    eff.extend(_parse_atoms_line(rest))
            elif mode == "pre":
                pre.extend(_parse_atoms_line(line))
            elif mode == "eff":
                eff.extend(_parse_atoms_line(line))
        if name is not None:
            actions.append(Action(name, color, tuple(pre), tuple(eff)))
        return actions

    return GridDomain(
        black_actions=parse_actions("blackactions", "B"),
        white_actions=parse_actions("whiteactions", "W"),
        path=str(path),
    )


def load_grid_problem(path: str | Path) -> GridProblem:
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    sections = _sections(text)

    bs = (_lines(sections, "boardsize") or ["3 3"])[0].split()
    W, H = int(bs[0]), int(bs[1])
    depth = int((_lines(sections, "depth") or ["1"])[0].split()[0])

    binit: list[tuple[int, int]] = []
    winit: list[tuple[int, int]] = []
    init_blob = " ".join(_lines(sections, "init"))
    for m in re.finditer(r"(black|white)\(\s*(\d+)\s*,\s*(\d+)\s*\)", init_blob, re.I):
        xy = (int(m.group(2)), int(m.group(3)))
        if m.group(1).lower() == "black":
            binit.append(xy)
        else:
            winit.append(xy)

    def parse_goals(key: str) -> list[list[Atom]]:
        goals: list[list[Atom]] = []
        for line in _lines(sections, key):
            if line.strip().lower() == "false":
                continue
            atoms = _parse_atoms_line(line)
            if atoms:
                goals.append(atoms)
        return goals

    turn = "first"
    for line in _lines(sections, "blackturn"):
        turn = line.strip().split()[0].lower()

    return GridProblem(
        width=W,
        height=H,
        depth=depth,
        black_init=binit,
        white_init=winit,
        black_goals=parse_goals("blackgoal"),
        white_goals=parse_goals("whitegoal"),
        black_turn=turn,
        path=str(path),
    )


def parse_coord_expr(s: str, ax: int, ay: int, W: int, H: int) -> int | None:
    s = s.strip().replace(" ", "")
    if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
        return int(s)
    bounds = {"xmin": 1, "ymin": 1, "xmax": W, "ymax": H}
    if s in bounds:
        return bounds[s]
    m = re.fullmatch(r"\?([xy])([+-]\d+)?", s)
    if not m:
        return None
    base = ax if m.group(1) == "x" else ay
    return base + int(m.group(2) or 0)


def eval_goal_shape(
    shape: list[Atom], ax: int, ay: int, W: int, H: int
) -> list[tuple[int, int, bool]] | None:
    """
    Instantiate a black-goal shape at anchor (ax,ay).
    Returns list of (x, y, negated) for black cells, or None if OOB.
    """
    cells: list[tuple[int, int, bool]] = []
    for atom in shape:
        if atom.pred != "black":
            return None
        x = parse_coord_expr(atom.x, ax, ay, W, H)
        y = parse_coord_expr(atom.y, ax, ay, W, H)
        if x is None or y is None or not (1 <= x <= W and 1 <= y <= H):
            return None
        cells.append((x, y, atom.negated))
    return cells


def ground_action(
    action: Action, x: int, y: int, W: int, H: int
) -> tuple[list[tuple[str, int, int, bool]], list[tuple[str, int, int]]] | None:
    """
    Ground action at parameters (x,y).

    Returns (preconditions, effects) where
      pre:  (pred, cx, cy, negated)
      eff:  (pred, cx, cy)  positive only
    or None if grounding is invalid (effect OOB / positive pre OOB).
    """
    pre: list[tuple[str, int, int, bool]] = []
    for atom in action.precondition:
        cx = parse_coord_expr(atom.x, x, y, W, H)
        cy = parse_coord_expr(atom.y, x, y, W, H)
        if cx is None or cy is None:
            return None
        if not (1 <= cx <= W and 1 <= cy <= H):
            if atom.negated:
                continue  # NOT(P) off-board ≡ true
            return None
        pre.append((atom.pred, cx, cy, atom.negated))

    eff: list[tuple[str, int, int]] = []
    for atom in action.effect:
        if atom.negated:
            continue
        cx = parse_coord_expr(atom.x, x, y, W, H)
        cy = parse_coord_expr(atom.y, x, y, W, H)
        if cx is None or cy is None or not (1 <= cx <= W and 1 <= cy <= H):
            return None
        eff.append((atom.pred, cx, cy))
    return pre, eff
