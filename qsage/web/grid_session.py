"""
Grid (BDDL) board play for GDDL games.

Supports domain-driven play for:
  - occupy (HTTT)
  - connect-c (gravity-style occupy)
  - domineering (vertical Black / horizontal White diominoes)
  - breakthrough / breakthrough-second-player (piece moves + captures)
  - evader_pursuer / dual (pursuit movement)

QBF check via bwnib + QuBi for AI and solve.

Board labels: a1 = (1,1) bottom-left style with letter=x, number=y (1-based).
"""

from __future__ import annotations

import random
import uuid
from functools import lru_cache
from pathlib import Path

from qsage.parse.ast_nodes import Action, Domain, Expr, Predicate, SubCondition
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
    """Return occupy | connect | domineering | breakthrough | chase | complex."""
    bnames = {a.name for a in domain.black_actions}
    wnames = {a.name for a in domain.white_actions}
    names = bnames | wnames
    if bnames == {"occupy"} and wnames == {"occupy"}:
        return "occupy"
    if "vertical" in bnames or "horizontal" in wnames:
        return "domineering"
    if "occupy-bottom" in names or (
        "occupy" in names and names - {"occupy", "occupy-bottom"}
    ):
        return "connect"
    if "forward" in names or "left-diagonal" in names:
        return "breakthrough"
    if any(n in names for n in ("down", "up", "left", "right", "stay")):
        return "chase"
    return "complex"


@lru_cache(maxsize=64)
def _load_domain(domain_rel: str) -> Domain:
    return parse_domain((_REPO / domain_rel).resolve())


def _get_domain(sess: dict) -> Domain:
    return _load_domain(sess["domain"])


def new_grid_session(problem_rel: str, domain_rel: str | None = None) -> dict:
    if not domain_rel:
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

    help_by_style = {
        "domineering": " Domineering: Black vertical 2-cells, White horizontal 2-cells.",
        "breakthrough": " Breakthrough: click destination of a piece move (forward/diagonal).",
        "chase": " Pursuit: click destination of your piece move.",
        "connect": " Connect: place in a column (gravity); click a legal drop cell.",
        "occupy": " Click an open cell to place your stone.",
        "complex": " Click a legal action from the side list (or board anchor).",
    }

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
        "winner_color": None,
        "winning_cells": None,
        "history": [],
        "last_ai": None,
        "play_mode": "qbf",
        "human_color": "W",
        "ai_color": "B",
        "black_first": black_first,
        "message": (
            f"Grid {style}: You are White · opponent Black (QBF). "
            f"Board {w}×{h}, depth {problem.depth}."
            + help_by_style.get(style, help_by_style["complex"])
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

    style = sess.get("style") or "occupy"
    help_map = {
        "domineering": (
            "Domineering: click the lower (Black) or left (White) cell of a 2-cell bar."
        ),
        "breakthrough": "Breakthrough: click the destination cell of your piece move.",
        "chase": "Pursuit: click the destination cell of your piece move.",
        "connect": "Connect-C: click a legal drop cell (gravity).",
        "occupy": "Click any open cell to place your stone.",
    }

    return {
        "session": sess["session"],
        "kind": "grid",
        "path": sess["path"],
        "domain": sess.get("domain"),
        "style": style,
        "board_w": sess["width"],
        "board_h": sess["height"],
        "width": sess["width"],
        "height": sess["height"],
        "cells": dict(sess["cells"]),
        "to_move": sess["to_move"],
        "finished": sess["finished"],
        "winner": sess["winner"],
        "winner_color": sess.get("winner_color"),
        "winning_cells": list(sess.get("winning_cells") or []),
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
        "action_help": help_map.get(style, "Click a legal action from the side list."),
    }


def _in_board(sess: dict, x: int, y: int) -> bool:
    return 1 <= x <= sess["width"] and 1 <= y <= sess["height"]


def _eval_coord(expr: Expr, x: int, y: int, w: int, h: int) -> int | None:
    """Resolve an Expr to an integer coordinate, or None if undefined."""
    if expr.kind == "const":
        return int(expr.value) if expr.value is not None else None
    if expr.kind == "bound":
        name = (expr.name or "").lower()
        base = {
            "xmin": 1,
            "ymin": 1,
            "xmax": w,
            "ymax": h,
        }.get(name)
        if base is None:
            return None
        return base + int(expr.offset or 0)
    # var
    name = (expr.name or "").lower()
    if name == "x":
        return x + int(expr.offset or 0)
    if name == "y":
        return y + int(expr.offset or 0)
    return None


def _cell_pred(sess: dict, pred: Predicate, cx: int, cy: int) -> bool:
    """True if predicate holds at (cx,cy). Off-board is always False."""
    if not _in_board(sess, cx, cy):
        return False
    lab = _xy_to_label(cx, cy)
    v = sess["cells"].get(lab, "open")
    if pred == Predicate.OPEN:
        return v == "open"
    if pred == Predicate.BLACK:
        return v == "B"
    if pred == Predicate.WHITE:
        return v == "W"
    return False


def _atom_holds(sess: dict, atom: SubCondition, x: int, y: int) -> bool:
    w, h = sess["width"], sess["height"]
    cx = _eval_coord(atom.x, x, y, w, h)
    cy = _eval_coord(atom.y, x, y, w, h)
    if cx is None or cy is None:
        return False
    holds = _cell_pred(sess, atom.predicate, cx, cy)
    return (not holds) if atom.negated else holds


def _action_effects(
    sess: dict, action: Action, x: int, y: int
) -> dict[str, str] | None:
    """
    Compute cell updates for applying action at parameters (x,y).
    Returns {label: new_value} or None if any effect coordinate is off-board.
    """
    w, h = sess["width"], sess["height"]
    updates: dict[str, str] = {}
    for atom in action.effect:
        if atom.negated:
            # effects in BDDL are positive facts only
            continue
        cx = _eval_coord(atom.x, x, y, w, h)
        cy = _eval_coord(atom.y, x, y, w, h)
        if cx is None or cy is None or not _in_board(sess, cx, cy):
            return None
        lab = _xy_to_label(cx, cy)
        if atom.predicate == Predicate.OPEN:
            updates[lab] = "open"
        elif atom.predicate == Predicate.BLACK:
            updates[lab] = "B"
        elif atom.predicate == Predicate.WHITE:
            updates[lab] = "W"
    return updates


def _destination_label(
    action: Action, x: int, y: int, w: int, h: int, color: str
) -> str | None:
    """
    Click target for an action.

    - Piece moves (effect opens a cell): destination of the mover's stone.
    - Placements / diominoes: parameter cell (x,y) when painted, else first paint.
    """
    color_pred = Predicate.BLACK if color == "B" else Predicate.WHITE
    place_labs: list[str] = []
    open_labs: list[str] = []
    for atom in action.effect:
        if atom.negated:
            continue
        cx = _eval_coord(atom.x, x, y, w, h)
        cy = _eval_coord(atom.y, x, y, w, h)
        if cx is None or cy is None:
            continue
        if not (1 <= cx <= w and 1 <= cy <= h):
            continue
        lab = _xy_to_label(cx, cy)
        if atom.predicate == color_pred:
            place_labs.append(lab)
        elif atom.predicate == Predicate.OPEN:
            open_labs.append(lab)
    src = _xy_to_label(x, y)
    if open_labs:
        # Piece relocation: click where the piece lands
        open_set = set(open_labs)
        for lab in place_labs:
            if lab not in open_set:
                return lab
        return place_labs[-1] if place_labs else src
    # Placement / multi-cell paint: click parameter cell if it is painted
    if src in place_labs:
        return src
    return place_labs[0] if place_labs else src


def legal_actions_for(sess: dict, color: str) -> list[dict]:
    """
    Enumerate legal domain actions for color.

    Each: {key, anchor, cells, from, action, label, description}
    anchor = click target (destination of the piece / placement cell).
    """
    domain = _get_domain(sess)
    actions = domain.black_actions if color == "B" else domain.white_actions
    w, h = sess["width"], sess["height"]
    out: list[dict] = []
    seen_keys: set[str] = set()

    for act in actions:
        for x in range(1, w + 1):
            for y in range(1, h + 1):
                if not all(_atom_holds(sess, atom, x, y) for atom in act.precondition):
                    continue
                updates = _action_effects(sess, act, x, y)
                if updates is None:
                    continue
                # stay / no-op still legal
                src = _xy_to_label(x, y)
                dest = _destination_label(act, x, y, w, h, color) or src
                key = f"{act.name}@{x},{y}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                cells = sorted(updates.keys())
                if not cells:
                    cells = [src]
                out.append(
                    {
                        "key": key,
                        "anchor": dest,
                        "from": src,
                        "action": act.name,
                        "cells": cells,
                        "label": f"{act.name} {src}→{dest}"
                        if src != dest
                        else f"{act.name} {dest}",
                        "description": (
                            f"{'Black' if color == 'B' else 'White'} "
                            f"{act.name} at ({x},{y}) → {dest}"
                        ),
                        "param_x": x,
                        "param_y": y,
                    }
                )

    # Stable order: by dest then action name
    out.sort(key=lambda a: (a["anchor"], a["action"], a["from"]))
    return out


def legal_cells_for(sess: dict, color: str) -> list[str]:
    """Unique click anchors for the side."""
    seen: list[str] = []
    for a in legal_actions_for(sess, color):
        if a["anchor"] not in seen:
            seen.append(a["anchor"])
    return seen


@lru_cache(maxsize=128)
def _load_problem(problem_rel: str):
    return parse_problem((_REPO / problem_rel).resolve())


def _get_problem(sess: dict):
    return _load_problem(sess["path"])


def _goal_shape_cells(
    sess: dict, shape, x: int, y: int
) -> list[str] | None:
    """
    If all positive atoms of a goal shape hold at binding (x,y), return the
    cell labels they mention; otherwise None.
    """
    w, h = sess["width"], sess["height"]
    cells: list[str] = []
    for atom in shape:
        cx = _eval_coord(atom.x, x, y, w, h)
        cy = _eval_coord(atom.y, x, y, w, h)
        if cx is None or cy is None:
            return None
        if not _in_board(sess, cx, cy):
            # Off-board positive atom fails; negated off-board is True
            if atom.negated:
                continue
            return None
        if not _atom_holds(sess, atom, x, y):
            return None
        if not atom.negated and atom.predicate in (
            Predicate.BLACK,
            Predicate.WHITE,
        ):
            cells.append(_xy_to_label(cx, cy))
    return cells


def evaluate_color_goal(sess: dict, color: str) -> list[str] | None:
    """
    True if some goal shape for `color` is satisfied.

    Returns the cells of the first matching shape (for UI highlight), or None.
    Goals use free ?x,?y — we search all board bindings.
    """
    problem = _get_problem(sess)
    shapes = problem.black_goals if color == "B" else problem.white_goals
    if not shapes:
        return None
    w, h = sess["width"], sess["height"]
    for shape in shapes:
        if not shape:
            continue
        for x in range(1, w + 1):
            for y in range(1, h + 1):
                cells = _goal_shape_cells(sess, shape, x, y)
                if cells is not None:
                    # de-dupe preserving order
                    seen: list[str] = []
                    for c in cells:
                        if c not in seen:
                            seen.append(c)
                    return seen
    return None


def _set_grid_winner(
    sess: dict, who: str, cells: list[str] | None, message: str
) -> None:
    sess["finished"] = True
    sess["winner"] = who
    sess["winner_color"] = "B" if who == "Black" else "W"
    sess["winning_cells"] = list(cells) if cells else None
    sess["message"] = message


def _update_winner_from_goals(sess: dict, prefer_color: str | None = None) -> None:
    """
    After a move, check BDDL goals. Prefer the mover's goal if both hit.
    """
    if sess.get("finished"):
        return
    order = []
    if prefer_color in ("B", "W"):
        order.append(prefer_color)
    for c in ("B", "W"):
        if c not in order:
            order.append(c)
    for color in order:
        cells = evaluate_color_goal(sess, color)
        if cells:
            who = "Black" if color == "B" else "White"
            _set_grid_winner(
                sess,
                who,
                cells,
                f"{who} achieved goal: {' · '.join(cells)}",
            )
            return


def _find_action(sess: dict, color: str, pos: str, key: str | None = None) -> dict | None:
    acts = legal_actions_for(sess, color)
    if key:
        for a in acts:
            if a["key"] == key:
                return a
    for a in acts:
        if a["anchor"] == pos:
            return a
    # also allow clicking the source for piece games
    for a in acts:
        if a.get("from") == pos:
            return a
    return None


def apply_grid_move(
    sess: dict,
    pos: str,
    color: str | None = None,
    *,
    as_human: bool = False,
    action_key: str | None = None,
) -> list[str]:
    """
    Apply a legal domain action.

    `pos` is the click anchor (destination). Optional action_key disambiguates.
    Returns list of cells whose value changed to the mover's color (for UI paint).
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

    chosen = _find_action(sess, color, pos, key=action_key)
    if chosen is None:
        raise ValueError(f"illegal move {pos} for {color}")

    domain = _get_domain(sess)
    actions = domain.black_actions if color == "B" else domain.white_actions
    act = next(a for a in actions if a.name == chosen["action"])
    x, y = int(chosen["param_x"]), int(chosen["param_y"])
    updates = _action_effects(sess, act, x, y)
    if updates is None:
        raise ValueError(f"illegal move effects at {pos}")

    # Snapshot for undo (all cells that will change)
    before: dict[str, str] = {}
    for lab, new_v in updates.items():
        old = sess["cells"].get(lab, "open")
        if old != new_v:
            before[lab] = old

    for lab, new_v in updates.items():
        sess["cells"][lab] = new_v

    # Cells "painted" by this color (UI highlight)
    painted = [lab for lab, v in updates.items() if v == color]
    if not painted:
        # stay or pure open effects — still report dest
        painted = [chosen["anchor"]]

    sess["history"].append(
        {
            "pos": chosen["anchor"],
            "color": color,
            "before": before,
            "painted": painted,
            "key": chosen["key"],
        }
    )
    sess["moves_played"] += 1
    sess["to_move"] = "W" if color == "B" else "B"

    # Goal check first (connect-k, breakthrough, etc.)
    _update_winner_from_goals(sess, prefer_color=color)

    nxt = sess["to_move"]
    if not sess["finished"]:
        if sess["moves_played"] >= sess["depth_bound"]:
            # Depth bound without either goal: QBF dual — Black failed
            bg = evaluate_color_goal(sess, "B")
            wg = evaluate_color_goal(sess, "W")
            if bg:
                _set_grid_winner(
                    sess,
                    "Black",
                    bg,
                    f"Black achieved goal: {' · '.join(bg)}",
                )
            elif wg:
                _set_grid_winner(
                    sess,
                    "White",
                    wg,
                    f"White achieved goal: {' · '.join(wg)}",
                )
            else:
                sess["finished"] = True
                sess["winner"] = (
                    "White — depth limit (Black goal not reached)"
                )
                sess["winner_color"] = "W"
                sess["message"] = sess["winner"]
        elif not legal_actions_for(sess, nxt):
            sess["finished"] = True
            prev = "B" if nxt == "W" else "W"
            # If the previous player completed a goal, already handled above
            if not sess.get("winner"):
                sess["winner"] = (
                    f"{'Black' if prev == 'B' else 'White'} "
                    f"(opponent has no moves)"
                )
                sess["winner_color"] = prev
                sess["message"] = sess["winner"]

    return painted


def random_grid_move(sess: dict, color: str | None = None) -> str | None:
    color = color or sess["to_move"]
    acts = legal_actions_for(sess, color)
    if not acts or sess["finished"]:
        return None
    act = random.choice(acts)
    painted = apply_grid_move(sess, act["anchor"], color, action_key=act["key"])
    sess["last_ai"] = {
        "color": color,
        "position": act["anchor"],
        "cells": painted,
        "mode": "random",
        "action": act["action"],
        "key": act["key"],
    }
    return act["anchor"]


def _write_midgame_ig(sess: dict, out: Path) -> None:
    """Write a BDDL problem reflecting the current board + remaining depth."""
    problem = parse_problem(_REPO / sess["path"])
    remaining = max(1, int(sess["depth_bound"]) - int(sess["moves_played"]))
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

    acts = legal_actions_for(sess, "B")
    if not acts:
        return None

    timeout = float(timeout)
    budget = min(len(acts), max(2, int(6.0 / max(timeout, 0.5))))
    candidates = acts[:]
    random.shuffle(candidates)
    candidates = candidates[:budget]

    sat_key: str | None = None
    sat_anchor: str | None = None
    for act in candidates:
        apply_grid_move(sess, act["anchor"], "B", action_key=act["key"])
        st = _residual_status(sess, timeout=timeout)
        undo_grid(sess)
        if st == "SAT":
            sat_key = act["key"]
            sat_anchor = act["anchor"]
            break

    if sat_key is None:
        return random_grid_move(sess, "B")

    painted = apply_grid_move(sess, sat_anchor or "", "B", action_key=sat_key)
    sess["last_ai"] = {
        "color": "B",
        "position": sat_anchor,
        "cells": painted,
        "mode": "qbf",
        "key": sat_key,
    }
    return sat_anchor


def undo_grid(sess: dict) -> None:
    if not sess["history"]:
        raise ValueError("nothing to undo")
    entry = sess["history"].pop()
    # Support both new dict history and legacy (pos, color, painted) tuples
    if isinstance(entry, dict):
        before = entry.get("before") or {}
        for lab, old in before.items():
            sess["cells"][lab] = old
        color = entry["color"]
    else:
        pos, color, painted = entry
        for lab in painted:
            sess["cells"][lab] = "open"
    sess["moves_played"] -= 1
    sess["to_move"] = color
    sess["finished"] = False
    sess["winner"] = None
    sess["winner_color"] = None
    sess["winning_cells"] = None
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
