"""
Certificate (winning-strategy) play for grid games.

Uses python-sat + viz_meta action/state variables (same idea as
legacy/general_interactive_play.py).
"""

from __future__ import annotations

import uuid
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def _parse_meta(path: Path) -> dict:
    sections: dict[str, list[list[str]]] = {}
    cur = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        if line.startswith("#"):
            cur = line.split()[0]
            sections.setdefault(cur, [])
            rest = line[len(line.split()[0]) :].strip()
            if rest:
                sections[cur].append(rest.split())
            continue
        if cur:
            sections[cur].append(line.split())
    return sections


def _bin_fmt(vars_: list[int], number: int) -> list[int]:
    n = len(vars_)
    bits = format(number, f"0{n}b")
    return [vars_[j] if bits[j] == "1" else -vars_[j] for j in range(n)]


def _model_bits(vars_: list[int], model: list[int]) -> str:
    s = set(model)
    out = ""
    for v in vars_:
        if v in s:
            out += "1"
        elif -v in s:
            out += "0"
        else:
            out += "0"
    return out


def _model_assign(vars_: list[int], model: list[int]) -> list[int]:
    s = set(model)
    out = []
    for v in vars_:
        if v in s:
            out.append(v)
        else:
            out.append(-v)
    return out


def new_cert_session(rel_dir: str) -> dict:
    try:
        from pysat.formula import CNF
        from pysat.solvers import Minisat22
    except ImportError as e:
        raise RuntimeError(
            "python-sat required for certificate play: pip install python-sat"
        ) from e

    d = (_REPO / rel_dir).resolve()
    if not str(d).startswith(str(_REPO.resolve())):
        raise ValueError("path outside repo")
    cert = d / "certificate.cnf"
    meta_path = d / "viz_meta_out"
    if not cert.is_file() or not meta_path.is_file():
        raise FileNotFoundError(f"need certificate.cnf + viz_meta_out in {rel_dir}")

    meta = _parse_meta(meta_path)
    bx = int(meta["#boardsize"][0][0])
    by = int(meta["#boardsize"][0][1])
    depth = int(meta["#depth"][0][0])

    action_vars = []
    for cur in meta.get("#actionvars", []):
        single = []
        for tok in cur:
            inner = tok.strip("[]")
            if not inner:
                single.append([])
            else:
                single.append([int(x) for x in inner.split(",") if x])
        action_vars.append(single)

    sx, sy = meta["#symbolicpos"][0]
    symb_x = [int(x) for x in sx.strip("[]").split(",") if x]
    symb_y = [int(y) for y in sy.strip("[]").split(",") if y]
    state_vars = [[int(x) for x in row] for row in meta.get("#statevars", [])]

    formula = CNF(from_file=str(cert))
    solver = Minisat22(bootstrap_with=formula.clauses)

    sess = {
        "session": uuid.uuid4().hex,
        "kind": "certificate",
        "path": rel_dir,
        "board_w": bx,
        "board_h": by,
        "depth_bound": depth,
        "action_vars": action_vars,
        "symb_x": symb_x,
        "symb_y": symb_y,
        "state_vars": state_vars,
        "solver": solver,
        "moves_played_vars": [],
        "time_step": 0,
        "history": [],
        "finished": False,
        "winner": None,
        "to_move": "B",
        "last_ai": None,
        "message": "Strategy certificate loaded (Black = certified strategy)",
    }
    sess["cells"] = _read_board(sess)
    return sess


def _read_board(sess: dict) -> dict[str, str]:
    """Map board from certificate + assumptions at current time_step."""
    pred = {"00": "open", "01": "open", "10": "B", "11": "W"}
    k = min(sess["time_step"], len(sess["state_vars"]) - 1)
    cells: dict[str, str] = {}
    m = sess["solver"]
    for j in range(sess["board_h"]):
        for i in range(sess["board_w"]):
            assm = list(sess["moves_played_vars"])
            assm.extend(_bin_fmt(sess["symb_x"], i))
            assm.extend(_bin_fmt(sess["symb_y"], j))
            m.solve(assumptions=assm)
            model = m.get_model() or []
            bits = _model_bits(sess["state_vars"][k], model)
            if len(bits) < 2:
                bits = bits.ljust(2, "0")
            label = chr(97 + i) + str(j + 1)
            cells[label] = pred.get(bits[:2], "open")
    return cells


def public_cert(sess: dict) -> dict:
    return {
        "session": sess["session"],
        "kind": "certificate",
        "path": sess["path"],
        "cells": dict(sess["cells"]),
        "to_move": sess["to_move"],
        "finished": sess["finished"],
        "winner": sess["winner"],
        "depth_bound": sess["depth_bound"],
        "moves_played": sess["time_step"],
        "last_ai": sess.get("last_ai"),
        "message": sess.get("message"),
        "board_w": sess["board_w"],
        "board_h": sess["board_h"],
    }


def strategy_black_move(sess: dict) -> dict:
    """Apply certified Black move at current time_step."""
    if sess["finished"]:
        raise ValueError("finished")
    k = sess["time_step"]
    if k % 2 != 0:
        raise ValueError("not Black's turn in certificate schedule")
    if k >= len(sess["action_vars"]):
        sess["finished"] = True
        return public_cert(sess)

    m = sess["solver"]
    m.solve(assumptions=list(sess["moves_played_vars"]))
    model = m.get_model()
    if model is None:
        raise RuntimeError("certificate unsat under current play — invalid line")

    av = sess["action_vars"][k]
    # action name bits, x bits, y bits
    x_vars = av[1] if len(av) > 1 else []
    y_vars = av[2] if len(av) > 2 else []
    x_bin = _model_bits(x_vars, model) if x_vars else "0"
    y_bin = _model_bits(y_vars, model) if y_vars else "0"
    xi = int(x_bin, 2) if x_bin else 0
    yi = int(y_bin, 2) if y_bin else 0
    label = chr(97 + xi) + str(yi + 1)

    for part in av:
        if part:
            sess["moves_played_vars"].extend(_model_assign(part, model))
    sess["time_step"] += 1
    sess["to_move"] = "W"
    sess["cells"] = _read_board(sess)
    sess["last_ai"] = {"color": "B", "position": label, "mode": "strategy"}
    sess["history"].append(("B", label, list(sess["moves_played_vars"])))
    if sess["time_step"] >= sess["depth_bound"]:
        sess["finished"] = True
        sess["winner"] = "Black (strategy depth complete)"
    return public_cert(sess)


def white_move(sess: dict, pos: str) -> dict:
    """User White move as occupy(x,y) encoded into assumptions."""
    if sess["finished"]:
        raise ValueError("finished")
    k = sess["time_step"]
    if k % 2 == 0:
        raise ValueError("Black to move — call strategy first")
    if k >= len(sess["action_vars"]):
        sess["finished"] = True
        return public_cert(sess)

    # parse a1 → x=0,y=0
    col = ord(pos[0].lower()) - 97
    row = int(pos[1:]) - 1
    if not (0 <= col < sess["board_w"] and 0 <= row < sess["board_h"]):
        raise ValueError(f"bad cell {pos}")

    av = sess["action_vars"][k]
    # white action name index 0 = occupy typically
    name_vars = av[0] if av else []
    x_vars = av[1] if len(av) > 1 else []
    y_vars = av[2] if len(av) > 2 else []
    # set action name = 0 (first white action)
    if name_vars:
        sess["moves_played_vars"].extend(_bin_fmt(name_vars, 0))
    if x_vars:
        sess["moves_played_vars"].extend(_bin_fmt(x_vars, col))
    if y_vars:
        sess["moves_played_vars"].extend(_bin_fmt(y_vars, row))

    sess["time_step"] += 1
    sess["to_move"] = "B"
    sess["cells"] = _read_board(sess)
    sess["history"].append(("W", pos, None))
    if sess["time_step"] >= sess["depth_bound"]:
        sess["finished"] = True
    return public_cert(sess)
