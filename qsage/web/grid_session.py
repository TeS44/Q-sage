"""
Grid (BDDL) board play for GDDL games.

Supports:
  - occupy (HTTT, simple place-a-stone)
  - domineering-style (vertical Black / horizontal White diominoes)
  - QBF check via bwnib + QuBi (always)

Board labels: a1 = (1,1) bottom-left style with letter=x, number=y (1-based).
"""

from __future__ import annotations

import random
import uuid
from pathlib import Path

from qsage.parse.ast_nodes import Domain, Predicate, Problem
from qsage.parse.bddl import parse_domain, parse_problem

_REPO = Path(__file__).resolve().parents[2]


def _xy_to_label(x: int, y: int) -> str:
    return f"{chr(96 + x)}{y}"


def _label_to_xy(lab: str) -> tuple[int, int]:
    m = __import__("re").match(r"^([a-zA-Z]+)(\d+)$", lab)
    if not m:
        raise ValueError(f"bad cell {lab}")
    letters = m.group(1).lower()
    x = 0
    for ch in letters:
        x = x * 26 + (ord(ch) - 96)
    y = int(m.group(2))
    return x, y


def _detect_style(domain: Domain) -> str:
    """Return occupy | domineering | complex."""
    bnames = {a.name for a in domain.black_actions}
    wnames = {a.name for a in domain.white_actions}
    if bnames == {"occupy"} and wnames == {"occupy"}:
        return "occupy"
    if "vertical" in bnames or "horizontal" in wnames:
        return "domineering"
    if any("occupy" in n for n in bnames | wnames):
        return "occupy"  # connect-c etc. treat as single-cell for play
    return "complex"


def new_grid_session(problem_rel: str, domain_rel: str | None = None) -> dict:
    if not domain_rel:
        # sibling domain.ig
        p = Path(problem_rel)
        domain_rel = str(p.parent / "domain.ig")
    dpath = (_REPO / domain_rel).resolve()
    ppath = (_REPO / problem_rel).resolve()
    if not str(dpath).startswith(str(_REPO.resolve())):
        raise ValueError("domain outside repo")
    if not str(ppath).startswith(str(_REPO.resolve())):
        raise ValueError("problem outside repo")
    if not dpath.is_file():
        raise FileNotFoundError(domain_rel)
    if not ppath.is_file():
        raise FileNotFoundError(problem_rel)

    domain = parse_domain(dpath)
    problem = parse_problem(ppath)
    style = _detect_style(domain)

    w, h = problem.width, problem.height
    cells: dict[str, str] = {}
    for x in range(1, w + 1):
        for y in range(1, h + 1):
            cells[_xy_to_label(x, y)] = "open"
    for x, y in problem.black_init:
        cells[_xy_to_label(x, y)] = "B"
    for x, y in problem.white_init:
        cells[_xy_to_label(x, y)] = "W"

    black_first = problem.black_turn != "second"
    to_move = "B" if black_first else "W"

    return {
        "session": uuid.uuid4().hex,
        "kind": "grid",
        "path": problem_rel,
        "domain": domain_rel,
        "style": style,
        "width": w,
        "height": h,
        "cells": cells,
        "depth_bound": problem.depth,
        "moves_played": 0,
        "to_move": to_move,
        "finished": False,
        "winner": None,
        "history": [],
        "last_ai": None,
        "play_mode": "qbf",
        "human_color": "W",
        "ai_color": "B",
        "black_first": black_first,
        "message": (
            f"Grid {style}: You are White · opponent Black (QBF). "
            f"Board {w}×{h}, depth {problem.depth}."
            + (
                " Domineering: Black vertical 2-cells, White horizontal 2-cells."
                if style == "domineering"
                else " Click an open cell to place."
            )
        ),
    }


def _grid_move_budget(sess: dict) -> dict:
    """
    Depth = total plies. With Black first: Black gets ceil(d/2), White floor(d/2).

    Example depth 5, Black first → Black 3, White (you) 2.
    """
    depth = int(sess.get("depth_bound") or 0)
    black_first = bool(sess.get("black_first", True))
    schedule = []
    for i in range(depth):
        if black_first:
            schedule.append("B" if i % 2 == 0 else "W")
        else:
            schedule.append("W" if i % 2 == 0 else "B")
    black_total = schedule.count("B")
    white_total = schedule.count("W")
    played = int(sess.get("moves_played") or 0)
    rem = schedule[played:]
    black_left = rem.count("B")
    white_left = rem.count("W")
    return {
        "depth_plies": depth,
        "depth_explain": (
            f"Depth {depth} = {depth} half-moves total "
            f"(Black {black_total}, White {white_total}). "
            f"You (White) get {white_total} move(s)."
        ),
        "schedule": schedule,
        "black_moves_total": black_total,
        "white_moves_total": white_total,
        "black_moves_left": black_left,
        "white_moves_left": white_left,
        "your_moves_total": white_total,
        "your_moves_left": white_left,
        "opponent_moves_total": black_total,
        "opponent_moves_left": black_left,
        "plies_left": max(0, depth - played),
    }


def public_grid(sess: dict) -> dict:
    human = sess.get("human_color") or "W"
    ai = sess.get("ai_color") or "B"
    mode = sess.get("play_mode") or "qbf"
    labels = {"B": "Black", "W": "White"}
    budget = _grid_move_budget(sess)
    your_turn = (not sess["finished"]) and sess["to_move"] == human
    last = sess.get("last_ai") or {}
    if sess["finished"]:
        turn_hint = f"Game over" + (
            f" — {sess['winner']}" if sess.get("winner") else ""
        )
    elif your_turn and last.get("color") == "B" and last.get("position"):
        turn_hint = (
            f"QBF played Black at {last['position']} — your turn (White). "
            f"You have {budget['your_moves_left']} move(s) left."
        )
    elif your_turn:
        turn_hint = (
            f"Your turn (White) — {budget['your_moves_left']} move(s) left."
        )
    else:
        turn_hint = (
            f"Opponent’s turn — Black ({mode}); "
            f"{budget['black_moves_left']} Black move(s) left…"
        )

    return {
        "session": sess["session"],
        "kind": "grid",
        "path": sess["path"],
        "domain": sess.get("domain"),
        "style": sess.get("style"),
        "board_w": sess["width"],
        "board_h": sess["height"],
        "width": sess["width"],
        "height": sess["height"],
        "cells": dict(sess["cells"]),
        "to_move": sess["to_move"],
        "finished": sess["finished"],
        "winner": sess["winner"],
        "depth_bound": sess["depth_bound"],
        "moves_played": sess["moves_played"],
        "last_ai": sess.get("last_ai"),
        "message": sess.get("message"),
        **budget,
        "play_mode": mode,
        "human_color": human,
        "ai_color": ai,
        "you_are": labels[human],
        "opponent_is": labels[ai],
        "opponent_engine": "QBF (QuBi)" if mode == "qbf" else mode,
        "your_turn": your_turn,
        "turn_hint": turn_hint,
        "needs_ai_move": (
            not sess["finished"]
            and mode in ("qbf", "random")
            and sess["to_move"] == ai
        ),
        "positions": list(sess["cells"].keys()),
        "legal_actions": legal_actions_for(
            sess, sess["to_move"] if not sess["finished"] else human
        ),
        "your_legal_actions": legal_actions_for(sess, human)
        if your_turn
        else [],
        "action_help": (
            "Domineering: click the lower (Black) or left (White) cell of a 2-cell bar; "
            "both cells fill."
            if sess.get("style") == "domineering"
            else "Click any open cell to place your stone."
        ),
    }


def _open(sess: dict, x: int, y: int) -> bool:
    lab = _xy_to_label(x, y)
    return sess["cells"].get(lab) == "open"


def _in_board(sess: dict, x: int, y: int) -> bool:
    return 1 <= x <= sess["width"] and 1 <= y <= sess["height"]


def legal_cells_for(sess: dict, color: str) -> list[str]:
    """Cells the player can click (anchor for multi-cell moves)."""
    return [a["anchor"] for a in legal_actions_for(sess, color)]


def legal_actions_for(sess: dict, color: str) -> list[dict]:
    """
    List of legal actions for the side panel and hover previews.

    Each action: {anchor, cells, label, description}
    """
    style = sess.get("style") or "occupy"
    w, h = sess["width"], sess["height"]
    out: list[dict] = []
    if style == "domineering":
        if color == "B":
            for x in range(1, w + 1):
                for y in range(1, h):
                    if _open(sess, x, y) and _open(sess, x, y + 1):
                        a = _xy_to_label(x, y)
                        b = _xy_to_label(x, y + 1)
                        out.append(
                            {
                                "anchor": a,
                                "cells": [a, b],
                                "label": f"vertical {a}+{b}",
                                "description": f"Black vertical diomino covering {a} and {b}",
                            }
                        )
        else:
            for x in range(1, w):
                for y in range(1, h + 1):
                    if _open(sess, x, y) and _open(sess, x + 1, y):
                        a = _xy_to_label(x, y)
                        b = _xy_to_label(x + 1, y)
                        out.append(
                            {
                                "anchor": a,
                                "cells": [a, b],
                                "label": f"horizontal {a}+{b}",
                                "description": f"White horizontal diomino covering {a} and {b}",
                            }
                        )
    else:
        for p, v in sorted(sess["cells"].items()):
            if v == "open":
                out.append(
                    {
                        "anchor": p,
                        "cells": [p],
                        "label": f"occupy {p}",
                        "description": f"Place stone on {p}",
                    }
                )
    return out


def apply_grid_move(sess: dict, pos: str, color: str | None = None, *, as_human: bool = False) -> list[str]:
    """
    Apply move; returns list of cells painted.
    """
    if sess["finished"]:
        raise ValueError("game finished")
    mode = sess.get("play_mode") or "qbf"
    if as_human and mode in ("qbf", "random"):
        color = "W"
        if sess["to_move"] != "W":
            raise ValueError("Not your turn — you are White; wait for Black")
    else:
        color = color or sess["to_move"]
    if color != sess["to_move"]:
        raise ValueError(f"not {color}'s turn")

    legal = legal_cells_for(sess, color)
    if pos not in legal:
        raise ValueError(f"illegal move {pos} for {color}")

    x, y = _label_to_xy(pos)
    style = sess.get("style") or "occupy"
    painted: list[str] = []

    if style == "domineering":
        if color == "B":
            cells = [(x, y), (x, y + 1)]
        else:
            cells = [(x, y), (x + 1, y)]
        for cx, cy in cells:
            if not _in_board(sess, cx, cy) or not _open(sess, cx, cy):
                raise ValueError(f"illegal domineering at {pos}")
        for cx, cy in cells:
            lab = _xy_to_label(cx, cy)
            sess["cells"][lab] = color
            painted.append(lab)
    else:
        sess["cells"][pos] = color
        painted.append(pos)

    sess["history"].append((pos, color, painted))
    sess["moves_played"] += 1
    sess["to_move"] = "W" if color == "B" else "B"

    # end conditions: no legal moves for next player, or depth reached
    nxt = sess["to_move"]
    if sess["moves_played"] >= sess["depth_bound"]:
        sess["finished"] = True
        sess["winner"] = sess["winner"] or "Depth limit"
    elif not legal_cells_for(sess, nxt):
        sess["finished"] = True
        # player to move cannot move — previous player wins (maker-breaker-ish)
        prev = "B" if nxt == "W" else "W"
        sess["winner"] = f"{'Black' if prev == 'B' else 'White'} (opponent no moves)"

    return painted


def random_grid_move(sess: dict, color: str | None = None) -> str | None:
    color = color or sess["to_move"]
    legal = legal_cells_for(sess, color)
    if not legal or sess["finished"]:
        return None
    pos = random.choice(legal)
    painted = apply_grid_move(sess, pos, color)
    sess["last_ai"] = {
        "color": color,
        "position": pos,
        "cells": painted,
        "mode": "random",
    }
    return pos


def _write_midgame_ig(sess: dict, out: Path) -> None:
    """Write a BDDL problem reflecting the current board + remaining depth."""
    problem = parse_problem(_REPO / sess["path"])
    remaining = max(1, int(sess["depth_bound"]) - int(sess["moves_played"]))
    # Who moves first in residual
    black_turn = "first" if sess["to_move"] == "B" else "second"

    lines = [
        "#boardsize",
        f"{sess['width']} {sess['height']}",
        "#init",
    ]
    for lab, v in sorted(sess["cells"].items()):
        if v == "B":
            x, y = _label_to_xy(lab)
            lines.append(f"black({x},{y})")
        elif v == "W":
            x, y = _label_to_xy(lab)
            lines.append(f"white({x},{y})")
    lines += ["#depth", str(remaining), "#blackgoal"]
    # goals as printed atoms from parsed problem
    for shape in problem.black_goals:
        if not shape:
            lines.append("False")
            continue
        parts = []
        for atom in shape:
            body = f"{atom.predicate.value}({atom.x},{atom.y})"
            parts.append(f"NOT({body})" if atom.negated else body)
        lines.append(" ".join(parts) if parts else "False")
    if not problem.black_goals:
        lines.append("False")
    lines.append("#whitegoal")
    for shape in problem.white_goals:
        if not shape:
            continue
        parts = []
        for atom in shape:
            body = f"{atom.predicate.value}({atom.x},{atom.y})"
            parts.append(f"NOT({body})" if atom.negated else body)
        if parts:
            lines.append(" ".join(parts))
    lines += ["#blackturn", black_turn]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _residual_status(sess: dict, timeout: float) -> str:
    """SAT/UNSAT/TIMEOUT/ERROR for current position via bwnib+QuBi."""
    import tempfile

    from qsage.encode.bwnib import encode_bwnib
    from qsage.solve.qubi import qubi_available, solve_qcir_qubi

    if not qubi_available():
        return "ERROR"
    with tempfile.TemporaryDirectory(prefix="qsage_grid_mid_") as td:
        mid = Path(td) / "mid.ig"
        _write_midgame_ig(sess, mid)
        try:
            qcir = encode_bwnib(_REPO / sess["domain"], mid)
            res = solve_qcir_qubi(qcir, timeout=float(timeout))
            return res.status.value
        except Exception:
            return "ERROR"


def maybe_play_ai_grid(sess: dict, *, timeout: float = 2.0) -> str | None:
    """
    Black AI using external QuBi for correctness when possible.

    One-ply search: try legal Black moves; prefer a move whose residual
    position is still SAT (Black still has a winning strategy). Falls back
    to random if QuBi times out or no SAT move is found.
    """
    if sess["finished"] or sess["to_move"] != "B":
        return None
    mode = sess.get("play_mode") or "qbf"
    if mode == "random":
        return random_grid_move(sess, "B")

    legal = legal_cells_for(sess, "B")
    if not legal:
        return None

    # Budget: few candidates so UI stays interactive
    timeout = float(timeout)
    budget = min(len(legal), max(2, int(6.0 / max(timeout, 0.5))))
    candidates = legal[:]
    random.shuffle(candidates)
    candidates = candidates[:budget]

    sat_move: str | None = None
    for pos in candidates:
        apply_grid_move(sess, pos, "B")
        # After Black move it is White's turn — residual with white to move
        st = _residual_status(sess, timeout=timeout)
        # undo
        undo_grid(sess)
        if st == "SAT":
            sat_move = pos
            break

    if sat_move is None:
        # no proven SAT move in budget — random legal
        return random_grid_move(sess, "B")

    painted = apply_grid_move(sess, sat_move, "B")
    sess["last_ai"] = {
        "color": "B",
        "position": sat_move,
        "cells": painted,
        "mode": "qbf",
    }
    return sat_move


def undo_grid(sess: dict) -> None:
    if not sess["history"]:
        raise ValueError("nothing to undo")
    pos, color, painted = sess["history"].pop()
    for lab in painted:
        sess["cells"][lab] = "open"
    sess["moves_played"] -= 1
    sess["to_move"] = color
    sess["finished"] = False
    sess["winner"] = None
    sess["last_ai"] = None


def solve_grid_qbf(sess: dict, *, timeout: float = 3.0) -> dict:
    from qsage.encode.bwnib import encode_bwnib
    from qsage.solve.qubi import qubi_available, solve_qcir_qubi

    if not qubi_available():
        return {"status": "ERROR", "detail": "QuBi missing"}
    domain = _REPO / sess["domain"]
    problem = _REPO / sess["path"]
    qcir = encode_bwnib(domain, problem)
    res = solve_qcir_qubi(qcir, timeout=float(timeout))
    return {
        "status": res.status.value,
        "seconds": res.seconds,
        "detail": "bwnib on original grid instance (not mid-game rewrite)",
        "timeout": float(timeout),
        "meaning": (
            "Black has a winning strategy (SAT)"
            if res.status.value == "SAT"
            else "No Black win in bound (UNSAT)"
            if res.status.value == "UNSAT"
            else f"No answer within {timeout}s"
            if res.status.value == "TIMEOUT"
            else res.message
        ),
    }
