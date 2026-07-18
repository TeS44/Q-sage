"""
Extensive play simulation over *all* playable QBF instances.

For every entry in Benchmarks/playable_qbf.json:
  1. HTTP /api/new loads a non-empty board (hex/grid)
  2. Roles: you=White, opponent=Black (vs engine)
  3. If Black to move, AI can open (random mode is fast)
  4. Multi-ply White play: every human paint is White; legal actions non-empty when turn
  5. Domain-driven games (breakthrough, chase, connect) have legal moves
  6. /api/solve returns SAT|UNSAT|TIMEOUT (not crash)

Also meta-tests: every major game family present with ≥2 instances.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from qsage.web.server import Handler

REPO = Path(__file__).resolve().parents[2]
PLAYABLE = REPO / "Benchmarks" / "playable_qbf.json"


def _load_instances() -> list[dict]:
    if not PLAYABLE.is_file():
        return []
    data = json.loads(PLAYABLE.read_text(encoding="utf-8"))
    return list(data.get("instances") or [])


INSTANCES = _load_instances()


@pytest.fixture(scope="module")
def http_base():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            urllib.request.urlopen(base + "/api/domains", timeout=0.3)
            break
        except Exception:
            time.sleep(0.05)
    yield base
    httpd.shutdown()


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=90) as r:
        return json.loads(r.read().decode())


def _post(base: str, path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            err = json.loads(raw)
        except Exception:
            err = raw
        raise AssertionError(f"HTTP {e.code} {path}: {err}") from e


def _id(inst: dict) -> str:
    return inst.get("label") or inst.get("path") or "?"


def _new_session(base: str, inst: dict, mode: str = "random") -> dict:
    kind = inst.get("kind") or "grid"
    q = {"path": inst["path"], "kind": kind, "mode": mode}
    if inst.get("domain"):
        q["domain_file"] = inst["domain"]
    return _get(base, f"/api/new?{urllib.parse.urlencode(q)}")


def _ensure_white_turn(base: str, st: dict) -> dict:
    """Run AI if Black is to move (opening or mid-game)."""
    for _ in range(4):
        if st.get("finished"):
            return st
        if st.get("your_turn") and st.get("to_move") == "W":
            return st
        if st.get("needs_ai_move") or st.get("to_move") == "B":
            st = _post(
                base,
                "/api/ai",
                {"session": st["session"], "mode": "random", "timeout": 1},
            )
            continue
        break
    return st


def _pick_white_action(st: dict) -> dict | None:
    acts = st.get("your_legal_actions") or []
    if acts:
        return acts[0]
    # Hex may only expose open cells
    cells = st.get("cells") or {}
    opens = [p for p, v in cells.items() if v == "open"]
    if opens:
        return {"anchor": opens[0], "cells": [opens[0]]}
    return None


@pytest.mark.skipif(not INSTANCES, reason="no playable_qbf.json")
@pytest.mark.parametrize("inst", INSTANCES, ids=[_id(i) for i in INSTANCES])
def test_instance_load_board_roles_multiplay_solve(http_base: str, inst: dict) -> None:
    kind = inst.get("kind") or "grid"
    path = inst["path"]
    assert (REPO / path).is_file(), path

    st = _new_session(http_base, inst, mode="random")

    # --- board must exist ---
    cells = st.get("cells") or {}
    assert cells, f"{path}: empty cells — board not shown"
    if kind == "hex":
        assert st.get("kind") == "hex"
        assert len(cells) >= 4
    else:
        assert st.get("kind") == "grid"
        w = st.get("board_w") or st.get("width")
        h = st.get("board_h") or st.get("height")
        assert w and h, f"{path}: missing board size"
        assert len(cells) == int(w) * int(h), (
            f"{path}: expected {int(w) * int(h)} cells, got {len(cells)}"
        )

    # --- roles ---
    assert st.get("you_are") == "White" or st.get("human_color") == "W", st
    assert st.get("opponent_is") == "Black" or st.get("ai_color") == "B", st

    # --- depth budget present ---
    assert st.get("depth_plies") or st.get("depth_bound"), path
    if st.get("your_moves_total") is not None:
        assert st["your_moves_total"] >= 0

    # --- multi-ply random play (up to 8 human moves or end) ---
    st = _ensure_white_turn(http_base, st)
    human_dests: list[str] = []
    for _ply in range(8):
        if st.get("finished"):
            break
        st = _ensure_white_turn(http_base, st)
        if st.get("finished") or not st.get("your_turn"):
            break

        # When it is White's turn, legal actions must exist for playable grids
        # (unless board is fully locked — should then finish).
        act = _pick_white_action(st)
        if act is None:
            # Stuck without moves — only acceptable if finished after recheck
            assert st.get("finished") or st.get("to_move") != "W", (
                f"{path}: White to move with zero legal actions; "
                f"style={st.get('style')} cells={st.get('cells')}"
            )
            break

        pos = act["anchor"]
        st2 = _post(
            http_base,
            "/api/move",
            {
                "session": st["session"],
                "position": pos,
                "opponent": "random",
                "timeout": 1,
            },
        )
        # Human action is always recorded as White. Black may recapture the same
        # square on the AI reply (breakthrough / chase) — that is legal.
        yjp = st2.get("you_just_played") or {}
        assert yjp.get("color") == "W" or yjp == {}, (
            f"{path}: you_just_played not White: {yjp}"
        )
        if yjp:
            assert yjp.get("position") == pos or pos in (yjp.get("cells") or [pos]), (
                f"{path}: you_just_played pos mismatch {yjp} vs {pos}"
            )
        # If Black did not reply, destination must still be White
        ojp = st2.get("opponent_just_played")
        if not ojp and not st2.get("finished"):
            assert st2["cells"].get(pos) == "W", (
                f"{path}: no AI reply but {pos}={st2['cells'].get(pos)}, expected W"
            )
        # Human click never paints Black as the human action itself
        if ojp:
            assert ojp.get("color") == "B"
        human_dests.append(pos)
        st = st2

    # At least one of: game finished, or we played, or AI-only finished opening
    # (domineering 2x2 may end after Black with White having no move)
    assert (
        st.get("finished")
        or human_dests
        or st.get("last_ai")
        or st.get("to_move") == "W"
    ), f"{path}: session idle with no progress"

    # --- solve original instance (hard timeout) ---
    st_s = _new_session(http_base, inst, mode="random")
    res = _post(
        http_base,
        "/api/solve",
        {"session": st_s["session"], "timeout": 3, "midgame": False},
    )
    assert res.get("status") in (
        "SAT",
        "UNSAT",
        "TIMEOUT",
        "ERROR",
    ), f"{path}: bad solve status {res}"
    if inst.get("status") in ("SAT", "UNSAT"):
        assert res["status"] != "ERROR", f"{path}: solve ERROR {res}"


@pytest.mark.skipif(not INSTANCES, reason="no playable_qbf.json")
def test_every_game_family_represented() -> None:
    games = {i["game"] for i in INSTANCES}
    for g in (
        "hex",
        "httt",
        "domineering",
        "connect-c",
        "breakthrough",
        "breakthrough-second-player",
        "evader_pursuer",
        "evader_pursuer_dual",
    ):
        assert g in games, f"missing game family {g} in playable set"


@pytest.mark.skipif(not INSTANCES, reason="no playable_qbf.json")
def test_at_least_two_per_major_game() -> None:
    c = Counter(i["game"] for i in INSTANCES)
    for g, n in c.items():
        assert n >= 1, g
    for g in ("hex", "httt", "domineering", "connect-c", "breakthrough"):
        assert c[g] >= 2, f"{g} only has {c[g]}"


@pytest.mark.skipif(not INSTANCES, reason="no playable_qbf.json")
@pytest.mark.parametrize(
    "game",
    sorted({i["game"] for i in INSTANCES}),
)
def test_one_per_game_family_has_legal_moves_when_white(http_base: str, game: str) -> None:
    """Each game family: pick fastest instance, ensure White can move or game ends cleanly."""
    candidates = [i for i in INSTANCES if i["game"] == game]
    inst = min(candidates, key=lambda x: float(x.get("seconds") or 99))
    st = _new_session(http_base, inst, mode="random")
    st = _ensure_white_turn(http_base, st)
    if st.get("finished"):
        return
    assert st.get("your_turn") and st.get("to_move") == "W", (
        f"{game}: expected White turn after AI open, got {st.get('to_move')} "
        f"finished={st.get('finished')}"
    )
    act = _pick_white_action(st)
    assert act is not None, (
        f"{game}/{inst['path']}: White has no legal actions; "
        f"style={st.get('style')} cells={st.get('cells')}"
    )
    st2 = _post(
        http_base,
        "/api/move",
        {
            "session": st["session"],
            "position": act["anchor"],
            "opponent": "random",
            "timeout": 1,
        },
    )
    assert st2.get("you_just_played", {}).get("color", "W") == "W" or st2[
        "cells"
    ].get(act["anchor"]) != "B"


# Fast QBF AI smoke (one instance per major family — not all 67)
_QBF_SMOKE = [
    i
    for i in INSTANCES
    if i.get("seconds", 99) < 0.1
    and i["game"] in ("hex", "httt", "domineering", "connect-c", "breakthrough")
]
# pick first per game
_seen_g: set[str] = set()
_QBF_PICK: list[dict] = []
for _i in sorted(_QBF_SMOKE, key=lambda x: x.get("seconds", 99)):
    if _i["game"] not in _seen_g:
        _seen_g.add(_i["game"])
        _QBF_PICK.append(_i)


@pytest.mark.skipif(not _QBF_PICK, reason="no fast smoke instances")
@pytest.mark.parametrize("inst", _QBF_PICK, ids=[_id(i) for i in _QBF_PICK])
def test_qbf_mode_smoke(http_base: str, inst: dict) -> None:
    """QBF play mode loads and Black AI can open without ERROR."""
    st = _new_session(http_base, inst, mode="qbf")
    assert st.get("cells")
    if st.get("needs_ai_move") or st.get("to_move") == "B":
        st = _post(
            http_base,
            "/api/ai",
            {"session": st["session"], "mode": "qbf", "timeout": 2},
        )
    # After AI (or if White first), board still coherent
    assert st.get("cells")
    assert st.get("you_are") == "White"
    res = _post(
        http_base,
        "/api/solve",
        {"session": st["session"], "timeout": 3, "midgame": False},
    )
    assert res.get("status") in ("SAT", "UNSAT", "TIMEOUT", "ERROR")
    assert res.get("status") != "ERROR" or not inst.get("status")
