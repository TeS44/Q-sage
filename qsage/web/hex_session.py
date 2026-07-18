"""Hex board session: human / random / QBF checks."""

from __future__ import annotations

import random
import tempfile
import uuid
from pathlib import Path

from qsage.parse.positional import parse_pg

_REPO = Path(__file__).resolve().parents[2]


def new_hex_session(rel_path: str) -> dict:
    path = (_REPO / rel_path).resolve()
    if not str(path).startswith(str(_REPO.resolve())):
        raise ValueError("path outside repo")
    if not path.is_file():
        raise FileNotFoundError(rel_path)
    game = parse_pg(path)
    cells = {pos: "open" for pos in game.positions}
    for pos in game.black_initials:
        cells[pos] = "B"
    for pos in game.white_initials:
        cells[pos] = "W"
    # Who moves first from the instance file (#times / #blackturns)
    times = list(game.times)
    black_turns = list(game.black_turns)
    if times and black_turns:
        black_opens = times[0] in black_turns
    else:
        black_opens = True  # Hex default: Black first
    first_color = "B" if black_opens else "W"
    return {
        "session": uuid.uuid4().hex,
        "kind": "hex",
        "path": rel_path,
        "positions": list(game.positions),
        "neighbours": {k: list(v) for k, v in game.neighbours.items()},
        "start_border": list(game.start_border),
        "end_border": list(game.end_border),
        "black_turns": black_turns,
        "times": times,
        "cells": cells,
        "history": [],
        "to_move": first_color,
        "finished": False,
        "winner": None,
        "depth_bound": game.depth,
        "moves_played": 0,
        "last_ai": None,
        "message": None,
        # vs AI: human is White, engine is Black (standard online Hex)
        "human_color": "W",
        "ai_color": "B",
        "play_mode": "qbf",
        "black_opens": black_opens,
        "first_color": first_color,
    }


def _hex_move_budget(sess: dict) -> dict:
    """
    Depth = total plies (half-moves), not full turns.

    Example depth 5 with Black on t1,t3,t5:
      Black 3 moves, White (you) 2 moves.
    """
    times = list(sess.get("times") or [])
    black_turns = set(sess.get("black_turns") or [])
    depth = int(sess.get("depth_bound") or len(times) or 0)
    if times and black_turns:
        schedule = ["B" if t in black_turns else "W" for t in times]
    else:
        # fallback: alternate, Black first
        schedule = ["B" if i % 2 == 0 else "W" for i in range(depth)]
    # pad/truncate to depth
    if len(schedule) < depth:
        schedule = schedule + [
            "B" if (len(schedule) + i) % 2 == 0 else "W"
            for i in range(depth - len(schedule))
        ]
    schedule = schedule[:depth]

    black_total = schedule.count("B")
    white_total = schedule.count("W")
    played = int(sess.get("moves_played") or 0)
    remaining_schedule = schedule[played:]
    black_left = remaining_schedule.count("B")
    white_left = remaining_schedule.count("W")
    human = sess.get("human_color") or "W"
    ai = sess.get("ai_color") or "B"
    your_total = white_total if human == "W" else black_total
    your_left = white_left if human == "W" else black_left
    opp_total = black_total if ai == "B" else white_total
    opp_left = black_left if ai == "B" else white_left

    return {
        "depth_plies": depth,
        "depth_explain": (
            f"Depth {depth} = {depth} half-moves total "
            f"(Black {black_total}, White {white_total}). "
            f"You (White) get {your_total} move(s)."
        ),
        "schedule": schedule,
        "black_moves_total": black_total,
        "white_moves_total": white_total,
        "black_moves_left": black_left,
        "white_moves_left": white_left,
        "your_moves_total": your_total,
        "your_moves_left": your_left,
        "opponent_moves_total": opp_total,
        "opponent_moves_left": opp_left,
        "plies_left": max(0, depth - played),
    }


def public_hex(sess: dict) -> dict:
    # Keep winning_path up to date whenever Black has connected
    if not sess.get("winning_path"):
        wp = black_winning_path(sess)
        if wp:
            sess["winning_path"] = wp
            if not sess.get("finished"):
                sess["finished"] = True
                sess["winner"] = "Black"

    mode = sess.get("play_mode") or "qbf"
    human = sess.get("human_color") or "W"
    ai = sess.get("ai_color") or "B"
    labels = {"B": "Black", "W": "White"}
    opp_name = {
        "qbf": "QBF (QuBi)",
        "hybrid": "Hybrid (book + QBF)",
        "random": "Random",
        "none": "— (manual / both sides)",
    }.get(mode, mode)
    budget = _hex_move_budget(sess)
    your_turn = (not sess["finished"]) and sess["to_move"] == human
    last = sess.get("last_ai") or {}
    last_pos = last.get("position")
    last_mode = last.get("mode") or mode

    if sess["finished"]:
        turn_hint = f"Game over" + (f" — {sess['winner']}" if sess.get("winner") else "")
    elif your_turn and last_pos and last.get("color") == "B":
        turn_hint = (
            f"QBF played Black at {last_pos} — your turn (White). "
            f"You have {budget['your_moves_left']} move(s) left."
        )
    elif your_turn:
        turn_hint = (
            f"Your turn (White) — {budget['your_moves_left']} move(s) left. "
            "Click an empty hex."
        )
    else:
        turn_hint = (
            f"Opponent’s turn — Black ({opp_name}); "
            f"Black has {budget['black_moves_left']} move(s) left…"
        )

    msg = sess.get("message")
    if your_turn and last_pos and last.get("color") == "B":
        msg = (
            f"Black played at {last_pos} via {last_mode}. "
            f"You are White — {budget['your_moves_left']} move(s) remaining "
            f"(depth {budget['depth_plies']} plies: "
            f"Black {budget['black_moves_total']}, White {budget['white_moves_total']})."
        )

    return {
        "session": sess["session"],
        "kind": "hex",
        "path": sess["path"],
        "cells": dict(sess["cells"]),
        "to_move": sess["to_move"],
        "finished": sess["finished"],
        "winner": sess["winner"],
        "depth_bound": sess["depth_bound"],
        "moves_played": sess["moves_played"],
        "last_ai": sess.get("last_ai"),
        "message": msg,
        **budget,
        "positions": list(sess["positions"]),
        "neighbours": {
            k: list(v) for k, v in (sess.get("neighbours") or {}).items()
        },
        "start_border": list(sess.get("start_border") or []),
        "end_border": list(sess.get("end_border") or []),
        "play_mode": mode,
        "human_color": human,
        "ai_color": ai,
        "you_are": labels.get(human, human),
        "opponent_is": labels.get(ai, ai),
        "opponent_engine": opp_name,
        "your_turn": your_turn,
        "turn_hint": turn_hint,
        "black_opens": sess.get("black_opens", True),
        "first_color": sess.get("first_color", "B"),
        "opening_note": (
            "Instance: Black moves first (from #blackturns)"
            if sess.get("black_opens", True)
            else "Instance: White moves first"
        ),
        "needs_ai_move": (
            not sess["finished"]
            and mode in ("qbf", "hybrid", "random")
            and sess["to_move"] == ai
        ),
        "winning_path": list(sess.get("winning_path") or [])
        if sess.get("finished") and sess.get("winner") == "Black"
        else list(black_winning_path(sess) or []),
        "black_borders": {
            "start": list(sess.get("start_border") or []),
            "end": list(sess.get("end_border") or []),
            "goal": "Black connects start ↔ end borders (dark edges)",
        },
        "white_borders": {
            "left": "first letter column (a…)",
            "right": "last letter column",
            "goal": "White blocks Black; White edges shown light",
        },
        "legal_actions": legal_actions_hex(sess, sess["to_move"])
        if not sess["finished"]
        else [],
        "your_legal_actions": legal_actions_hex(sess, human)
        if your_turn
        else [],
        "action_help": "Hex: click one empty cell to place your White stone.",
    }


def open_cells(sess: dict) -> list[str]:
    return [p for p, v in sess["cells"].items() if v == "open"]


def legal_actions_hex(sess: dict, color: str | None = None) -> list[dict]:
    """Open cells as single-stone occupy actions."""
    color = color or sess.get("to_move") or "W"
    if sess.get("finished") or sess.get("to_move") != color:
        # still list human legal when it's their turn only for "your" list
        pass
    if sess.get("finished"):
        return []
    if sess.get("to_move") != color:
        return []
    return [
        {
            "anchor": p,
            "cells": [p],
            "label": f"play {p}",
            "description": f"Place {'Black' if color == 'B' else 'White'} on {p}",
        }
        for p in sorted(open_cells(sess))
    ]


def black_winning_path(sess: dict) -> list[str] | None:
    """
    Shortest Black path from start_border to end_border (cell labels), or None.
    """
    owned = {p for p, v in sess["cells"].items() if v == "B"}
    starts = [p for p in (sess.get("start_border") or []) if p in owned]
    ends = {p for p in (sess.get("end_border") or []) if p in owned}
    if not starts or not ends:
        return None
    neigh = sess.get("neighbours") or {}
    parent: dict[str, str | None] = {s: None for s in starts}
    queue = list(starts)
    found: str | None = None
    while queue:
        u = queue.pop(0)
        if u in ends:
            found = u
            break
        for v in neigh.get(u, []):
            if v in owned and v not in parent:
                parent[v] = u
                queue.append(v)
    if found is None:
        return None
    path = []
    cur: str | None = found
    while cur is not None:
        path.append(cur)
        cur = parent.get(cur)
    path.reverse()
    return path


def _path_exists(sess: dict, color: str) -> bool:
    """Black path start→end (White win = Black fails to connect within bound)."""
    if color != "B":
        return False
    return black_winning_path(sess) is not None


def apply_move(
    sess: dict,
    pos: str,
    color: str | None = None,
    *,
    as_human: bool = False,
) -> None:
    if sess["finished"]:
        raise ValueError("game finished")
    human = sess.get("human_color") or "W"
    mode = sess.get("play_mode") or "qbf"
    # Human clicks ALWAYS place White when playing vs the engine.
    # Never use to_move for the stone colour on a human click.
    if as_human and mode in ("qbf", "hybrid", "random"):
        human = "W"
        sess["human_color"] = "W"
        sess["ai_color"] = "B"
        color = "W"
        if sess["to_move"] != "W":
            raise ValueError(
                "Not your turn — you are White; wait for Black (QBF)"
            )
    else:
        color = color or sess["to_move"]
    if color not in ("B", "W"):
        raise ValueError(f"bad color {color!r}")
    if pos not in sess["cells"] or sess["cells"][pos] != "open":
        raise ValueError(f"illegal move {pos}")
    if color != sess["to_move"]:
        raise ValueError(
            f"not {color}'s turn (to_move={sess['to_move']})"
        )
    sess["cells"][pos] = color
    sess["history"].append((pos, color))
    sess["moves_played"] += 1
    sess["to_move"] = "W" if color == "B" else "B"
    # win / horizon
    bpath = black_winning_path(sess)
    if bpath:
        sess["finished"] = True
        sess["winner"] = "Black"
        sess["winning_path"] = bpath
        sess["message"] = (
            f"Black connected borders via {' → '.join(bpath)}"
        )
    elif sess["moves_played"] >= sess["depth_bound"] or not open_cells(sess):
        sess["finished"] = True
        if not sess["winner"]:
            sess["winner"] = "White (Black failed to connect)"
            sess["winning_path"] = None


def random_move(sess: dict, color: str | None = None) -> str | None:
    color = color or sess["to_move"]
    if sess["finished"] or sess["to_move"] != color:
        return None
    opens = open_cells(sess)
    if not opens:
        return None
    pos = random.choice(opens)
    apply_move(sess, pos, color)
    sess["last_ai"] = {"color": color, "position": pos, "mode": "random"}
    return pos


def undo(sess: dict) -> None:
    if not sess["history"]:
        raise ValueError("nothing to undo")
    pos, color = sess["history"].pop()
    sess["cells"][pos] = "open"
    sess["moves_played"] -= 1
    sess["to_move"] = color
    sess["finished"] = False
    sess["winner"] = None
    sess["last_ai"] = None


def _write_midgame_pg(sess: dict) -> Path:
    """Snapshot current board as a .pg for re-encoding."""
    remaining = max(1, sess["depth_bound"] - sess["moves_played"])
    # build times t1..t_remaining; black on odd plies if original black first
    times = [f"t{i}" for i in range(1, remaining + 1)]
    # default black on t1,t3,... of remaining horizon
    black_turns = [times[i] for i in range(0, len(times), 2)]
    if sess["to_move"] == "W":
        # white to move first in residual game → black on t2,t4,...
        black_turns = [times[i] for i in range(1, len(times), 2)]

    blacks = [p for p, v in sess["cells"].items() if v == "B"]
    whites = [p for p, v in sess["cells"].items() if v == "W"]
    lines = [
        "#blackinitials",
        *blacks,
        "#whiteinitials",
        *whites,
        "#times",
        " ".join(times),
        "#blackturns",
        " ".join(black_turns) if black_turns else "",
        "#positions",
        " ".join(sess["positions"]),
        "#neighbours",
    ]
    for p in sess["positions"]:
        nbs = sess["neighbours"].get(p, [])
        lines.append(p + (" " + " ".join(nbs) if nbs else ""))
    lines += [
        "#startboarder",
        " ".join(sess.get("start_border") or []),
        "#endboarder",
        " ".join(sess.get("end_border") or []),
    ]
    td = Path(tempfile.mkdtemp(prefix="qsage_web_"))
    out = td / "mid.pg"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def solve_qbf(
    sess: dict,
    *,
    midgame: bool = False,
    encoding: str = "pg",
    timeout: float = 3.0,
) -> dict:
    """QuBi solve with a hard timeout (default 3s). Never hangs indefinitely."""
    from qsage.encode.positional import encode_positional
    from qsage.solve.qubi import qubi_available, solve_qcir_qubi

    if not qubi_available():
        return {
            "status": "ERROR",
            "detail": "QuBi not built (scripts/build_qubi_macos.sh)",
        }
    if midgame:
        pg = _write_midgame_pg(sess)
        qcir = encode_positional(pg, encoding)
        detail = (
            f"mid-game residual ({encoding}), "
            f"remaining≤{sess['depth_bound'] - sess['moves_played']}"
        )
    else:
        qcir = encode_positional(_REPO / sess["path"], encoding)
        detail = f"original puzzle ({encoding})"
    res = solve_qcir_qubi(qcir, timeout=float(timeout))
    return {
        "status": res.status.value,
        "seconds": res.seconds,
        "detail": detail,
        "message": res.message,
        "timeout": float(timeout),
        "meaning": (
            "Black has a winning strategy from this position"
            if res.status.value == "SAT"
            else "Black has no winning strategy within the bound"
            if res.status.value == "UNSAT"
            else f"No answer within {timeout}s"
            if res.status.value == "TIMEOUT"
            else res.message
        ),
    }


def ai_qbf_black_move(sess: dict, timeout: float = 2.0) -> str | None:
    """
    Greedy one-ply: try each open cell as Black; pick first that leaves
    mid-game QBF still SAT (or any legal if all timeout).
    """
    if sess["finished"] or sess["to_move"] != "B":
        return None
    opens = open_cells(sess)
    if not opens:
        return None
    # Prefer faster heuristic: random among moves that keep SAT
    # Cap how many cells we try so AI never runs opens × timeout forever
    timeout = float(timeout)
    budget = min(len(opens), max(1, int(6.0 / max(timeout, 0.5))))
    candidates = opens[:]
    random.shuffle(candidates)
    candidates = candidates[:budget]
    for pos in candidates:
        apply_move(sess, pos, "B")
        try:
            r = solve_qbf(sess, midgame=True, timeout=timeout)
            good = r.get("status") == "SAT"
        except Exception:
            good = False
        undo(sess)
        if good:
            apply_move(sess, pos, "B")
            sess["last_ai"] = {"color": "B", "position": pos, "mode": "qbf"}
            return pos
    return random_move(sess, "B")


def maybe_play_ai(sess: dict, *, timeout: float = 2.0) -> str | None:
    """
    If it is the AI colour's turn under qbf/hybrid/random, play one AI move.
    Used after load (Black opens) and after a human White move.
    """
    mode = sess.get("play_mode") or "qbf"
    ai = sess.get("ai_color") or "B"
    if sess.get("finished") or mode not in ("qbf", "hybrid", "random"):
        return None
    if sess.get("to_move") != ai:
        return None
    if mode == "hybrid":
        return ai_hybrid_black_move(sess, qbf_timeout=timeout)
    if mode == "qbf":
        return ai_qbf_black_move(sess, timeout=timeout)
    return random_move(sess, ai)


def ai_hybrid_black_move(sess: dict, *, qbf_timeout: float = 2.0) -> str | None:
    """
    Hybrid: partial-cert opening book first, then short QBF, then random.

    Partial certs live under Benchmarks/partial_certs/ (see
    scripts/generate_partial_certs.py).
    """
    if sess["finished"] or sess["to_move"] != "B":
        return None
    from qsage.web.partial_certs import lookup_move

    hit = lookup_move(sess["path"], sess["cells"], "B")
    if hit and hit["move"] in open_cells(sess):
        apply_move(sess, hit["move"], "B")
        sess["last_ai"] = {
            "color": "B",
            "position": hit["move"],
            "mode": "hybrid-cert",
            "ply": hit.get("ply"),
        }
        sess["message"] = (
            f"Hybrid: partial cert move {hit['move']} "
            f"(book depth {hit.get('hybrid_depth')})"
        )
        return hit["move"]

    # QBF with short timeout for interactive feel
    pos = ai_qbf_black_move(sess, timeout=qbf_timeout)
    if pos and sess.get("last_ai"):
        sess["last_ai"]["mode"] = "hybrid-qbf"
        sess["message"] = f"Hybrid: QBF tail move {pos}"
    return pos
