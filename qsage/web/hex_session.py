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
    return {
        "session": uuid.uuid4().hex,
        "kind": "hex",
        "path": rel_path,
        "positions": list(game.positions),
        "neighbours": {k: list(v) for k, v in game.neighbours.items()},
        "start_border": list(game.start_border),
        "end_border": list(game.end_border),
        "black_turns": list(game.black_turns),
        "times": list(game.times),
        "cells": cells,
        "history": [],
        "to_move": "B",
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
    }


def public_hex(sess: dict) -> dict:
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
    your_turn = (not sess["finished"]) and sess["to_move"] == human
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
        "message": sess.get("message"),
        "positions": list(sess["positions"]),
        "start_border": list(sess.get("start_border") or []),
        "end_border": list(sess.get("end_border") or []),
        "play_mode": mode,
        "human_color": human,
        "ai_color": ai,
        "you_are": labels.get(human, human),
        "opponent_is": labels.get(ai, ai),
        "opponent_engine": opp_name,
        "your_turn": your_turn,
        "turn_hint": (
            "Game over"
            if sess["finished"]
            else (
                f"Your turn — play as {labels.get(human, human)}"
                if your_turn
                else f"Opponent’s turn — {labels.get(ai, ai)} ({opp_name})"
            )
        ),
        "needs_ai_move": (
            not sess["finished"]
            and mode in ("qbf", "hybrid", "random")
            and sess["to_move"] == ai
        ),
    }


def open_cells(sess: dict) -> list[str]:
    return [p for p, v in sess["cells"].items() if v == "open"]


def _path_exists(sess: dict, color: str) -> bool:
    """Black path start→end or White path (swap borders not defined — only Black win)."""
    if color != "B":
        return False
    owned = {p for p, v in sess["cells"].items() if v == "B"}
    start = [p for p in sess.get("start_border") or [] if p in owned]
    end = set(sess.get("end_border") or [])
    neigh = sess.get("neighbours") or {}
    stack = list(start)
    seen = set(start)
    while stack:
        u = stack.pop()
        if u in end:
            return True
        for v in neigh.get(u, []):
            if v in owned and v not in seen:
                seen.add(v)
                stack.append(v)
    return False


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
    # Human clicks always place the human's colour (White vs AI) — never "whoever is to move".
    if as_human and mode in ("qbf", "hybrid", "random"):
        color = human
    else:
        color = color or sess["to_move"]
    if as_human and mode in ("qbf", "hybrid", "random"):
        if sess["to_move"] != human:
            raise ValueError(
                f"Not your turn — you are {'White' if human == 'W' else 'Black'}; "
                f"wait for {'Black' if human == 'W' else 'White'}"
            )
        if color != human:
            raise ValueError(
                f"You play as {'White' if human == 'W' else 'Black'} only"
            )
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
    if _path_exists(sess, "B"):
        sess["finished"] = True
        sess["winner"] = "Black"
    elif sess["moves_played"] >= sess["depth_bound"] or not open_cells(sess):
        sess["finished"] = True
        if not sess["winner"]:
            sess["winner"] = "White (Black failed to connect)"


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
