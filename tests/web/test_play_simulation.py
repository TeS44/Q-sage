"""
Extensive play simulations — no browser, but same API paths as the UI.

Mirrors what the frontend does: /api/new → /api/move → /api/ai → /api/solve
and asserts colours, turns, boards, and move budgets so bugs like
“first click places Black” are caught in CI.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from qsage.web.server import Handler

REPO = Path(__file__).resolve().parents[2]
HEX = "Benchmarks/B-Hex/hein_04_3x3-05.pg"
HTTT_DOM = "Benchmarks/SAT2023_GDDL/GDDL_models/httt/domain.ig"
HTTT_P = "Benchmarks/SAT2023_GDDL/GDDL_models/httt/3x3_3_domino.ig"
DOM_DOM = "Benchmarks/SAT2023_GDDL/GDDL_models/domineering/domain.ig"
DOM_P = "Benchmarks/SAT2023_GDDL/GDDL_models/domineering/2x3_4.ig"


@pytest.fixture(scope="module")
def http_base():
    """Live HTTP server on an ephemeral port (same Handler as qsage web)."""
    # Bind 127.0.0.1:0
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{port}"
    # wait until up
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/api/domains", timeout=0.2)
            break
        except Exception:
            time.sleep(0.05)
    yield base
    httpd.shutdown()


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=60) as r:
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
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read().decode())
        raise AssertionError(f"HTTP {e.code} {path}: {err}") from e


def _open_cells(state: dict) -> list[str]:
    return [p for p, v in (state.get("cells") or {}).items() if v == "open"]


def _count(state: dict, color: str) -> int:
    return sum(1 for v in (state.get("cells") or {}).values() if v == color)


# ---------------------------------------------------------------------------
# Hex: full click simulation
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not (REPO / HEX).is_file(), reason="hex missing")
def test_hex_load_black_opens_then_white_only(http_base: str) -> None:
    st = _get(
        http_base,
        f"/api/new?path={HEX}&kind=hex&mode=qbf",
    )
    assert st["kind"] == "hex"
    assert st["you_are"] == "White"
    assert st["opponent_is"] == "Black"
    assert st["human_color"] == "W"
    # Black should have opened (or needs_ai_move if qubi failed)
    if st.get("last_ai"):
        assert st["last_ai"]["color"] == "B"
        assert st["to_move"] == "W"
        assert st["your_turn"] is True
        assert st["cells"][st["last_ai"]["position"]] == "B"
    else:
        # Allow retry via AI endpoint
        if st.get("needs_ai_move"):
            st = _post(
                http_base,
                "/api/ai",
                {"session": st["session"], "mode": "qbf", "timeout": 3},
            )
        assert st["to_move"] == "W", st
        assert st["your_turn"] is True

    # Depth 5 → White 2 moves total
    assert st.get("white_moves_total") == 2
    assert st.get("black_moves_total") == 3
    assert st.get("your_moves_left") == 2

    # First human click MUST place White, never Black
    opens = _open_cells(st)
    assert opens
    pos = opens[0]
    b_before = _count(st, "B")
    st2 = _post(
        http_base,
        "/api/move",
        {
            "session": st["session"],
            "position": pos,
            "opponent": "qbf",
            "timeout": 2,
        },
    )
    assert st2["cells"][pos] == "W", (
        f"BUG: first click on {pos} placed {st2['cells'][pos]}, expected W. "
        f"you_just_played={st2.get('you_just_played')}"
    )
    if st2.get("you_just_played"):
        assert st2["you_just_played"]["color"] == "W"
        assert st2["you_just_played"]["position"] == pos

    # After White, Black may have replied on a *different* cell
    if st2.get("opponent_just_played"):
        assert st2["opponent_just_played"]["color"] == "B"
        assert st2["opponent_just_played"]["position"] != pos
        assert st2["cells"][st2["opponent_just_played"]["position"]] == "B"

    # Your remaining moves decreased by 1
    assert st2.get("your_moves_left") == 1 or st2.get("finished")


@pytest.mark.skipif(not (REPO / HEX).is_file(), reason="hex missing")
def test_hex_cannot_click_when_black_to_move(http_base: str) -> None:
    """If somehow Black still to move, /api/move must reject (not paint Black)."""
    from qsage.web import server as srv
    from qsage.web.hex_session import new_hex_session

    # Inject a session stuck on Black without opening
    s = new_hex_session(HEX)
    s["play_mode"] = "qbf"
    s["human_color"] = "W"
    s["ai_color"] = "B"
    # do NOT call maybe_play_ai
    assert s["to_move"] == "B"
    srv._SESSIONS[s["session"]] = s

    opens = _open_cells(s)
    with pytest.raises(AssertionError) as ei:
        _post(
            http_base,
            "/api/move",
            {
                "session": s["session"],
                "position": opens[0],
                "opponent": "qbf",
                "timeout": 1,
            },
        )
    assert "Not your turn" in str(ei.value) or "400" in str(ei.value)
    # Cell must still be open (not painted Black by the click)
    assert srv._SESSIONS[s["session"]]["cells"][opens[0]] == "open"


@pytest.mark.skipif(not (REPO / HEX).is_file(), reason="hex missing")
def test_hex_full_game_until_end_or_three_plies(http_base: str) -> None:
    """Play several White moves alternating with AI; never paint human Black."""
    st = _get(http_base, f"/api/new?path={HEX}&kind=hex&mode=random")
    # random AI is fast
    human_cells: list[str] = []
    for _ in range(5):
        if st.get("finished"):
            break
        if not st.get("your_turn"):
            st = _post(
                http_base,
                "/api/ai",
                {"session": st["session"], "mode": "random", "timeout": 1},
            )
            continue
        opens = _open_cells(st)
        if not opens:
            break
        pos = opens[0]
        st = _post(
            http_base,
            "/api/move",
            {
                "session": st["session"],
                "position": pos,
                "opponent": "random",
                "timeout": 1,
            },
        )
        assert st["cells"][pos] == "W", st["cells"][pos]
        human_cells.append(pos)

    for p in human_cells:
        assert st["cells"][p] == "W"


# ---------------------------------------------------------------------------
# Grid: board must exist + play works
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not (REPO / HTTT_P).is_file(), reason="httt missing")
def test_grid_httt_board_visible_and_playable(http_base: str) -> None:
    st = _get(
        http_base,
        f"/api/new?path={HTTT_P}&kind=grid&mode=qbf&domain_file={HTTT_DOM}",
    )
    assert st["kind"] == "grid"
    assert len(st.get("cells") or {}) == 9, "board must have 9 cells"
    assert st["board_w"] == 3 and st["board_h"] == 3
    assert st["you_are"] == "White"
    # Black should have opened
    if st["to_move"] == "B" and st.get("needs_ai_move"):
        st = _post(
            http_base,
            "/api/ai",
            {"session": st["session"], "mode": "qbf", "timeout": 2},
        )
    assert st["to_move"] == "W" or st.get("finished")
    if st.get("finished"):
        return
    assert st["your_turn"] is True
    assert st.get("your_legal_actions"), "must list legal moves"
    # play first legal
    act = st["your_legal_actions"][0]
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
    assert st2["cells"][pos] == "W", st2["cells"][pos]


@pytest.mark.skipif(not (REPO / DOM_P).is_file(), reason="domineering missing")
def test_grid_domineering_two_cells_and_legal_list(http_base: str) -> None:
    st = _get(
        http_base,
        f"/api/new?path={DOM_P}&kind=grid&mode=random&domain_file={DOM_DOM}",
    )
    assert st["kind"] == "grid"
    assert st.get("style") == "domineering"
    assert len(st["cells"]) == 2 * 3  # 2x3
    if st["to_move"] == "B":
        st = _post(
            http_base,
            "/api/ai",
            {"session": st["session"], "mode": "random", "timeout": 1},
        )
    if st.get("finished") or not st.get("your_turn"):
        return
    acts = st.get("your_legal_actions") or []
    assert acts, "White must have legal horizontal bars"
    for a in acts:
        assert len(a["cells"]) == 2, a
    act = acts[0]
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
    for c in act["cells"]:
        assert st2["cells"][c] == "W", (c, st2["cells"][c])


@pytest.mark.skipif(not (REPO / HTTT_P).is_file(), reason="httt missing")
def test_grid_solve_endpoint(http_base: str) -> None:
    st = _get(
        http_base,
        f"/api/new?path={HTTT_P}&kind=grid&mode=qbf&domain_file={HTTT_DOM}",
    )
    res = _post(
        http_base,
        "/api/solve",
        {"session": st["session"], "timeout": 3},
    )
    assert res["status"] in ("SAT", "UNSAT", "TIMEOUT", "ERROR")
    # known easy SAT
    assert res["status"] == "SAT", res


# ---------------------------------------------------------------------------
# Catalog / domains
# ---------------------------------------------------------------------------


def test_domains_and_playable_catalog(http_base: str) -> None:
    d = _get(http_base, "/api/domains")
    assert d["domains"]
    groups = {x["id"] for x in d["domains"]}
    assert any("Hex" in g for g in groups)
    # problems for first hex domain
    hex_g = next(x for x in d["domains"] if "Hex" in x["id"])
    probs = _get(
        http_base, "/api/problems?" + f"domain={urllib.parse.quote(hex_g['id'])}"
    )
    assert probs["problems"]


# need urllib.parse for quote
import urllib.parse  # noqa: E402
