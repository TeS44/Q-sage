"""Grid board play — must show cells and accept White moves."""

from __future__ import annotations

from pathlib import Path

import pytest

from qsage.web.grid_session import (
    apply_grid_move,
    legal_cells_for,
    maybe_play_ai_grid,
    new_grid_session,
    public_grid,
    solve_grid_qbf,
)

REPO = Path(__file__).resolve().parents[2]
HTTT = "Benchmarks/SAT2023_GDDL/GDDL_models/httt"
DOM = "Benchmarks/SAT2023_GDDL/GDDL_models/domineering"


@pytest.mark.skipif(
    not (REPO / HTTT / "3x3_3_domino.ig").is_file(), reason="benchmark missing"
)
def test_httt_board_has_cells_and_white_move() -> None:
    s = new_grid_session(
        f"{HTTT}/3x3_3_domino.ig",
        f"{HTTT}/domain.ig",
    )
    assert s["width"] == 3 and s["height"] == 3
    assert len(s["cells"]) == 9
    assert all(v == "open" for v in s["cells"].values())
    # Black first → AI open
    maybe_play_ai_grid(s)
    pub = public_grid(s)
    assert pub["kind"] == "grid"
    assert len(pub["cells"]) == 9
    assert sum(1 for v in pub["cells"].values() if v == "B") == 1
    assert pub["to_move"] == "W"
    assert pub["your_turn"] is True
    # White places
    legal = legal_cells_for(s, "W")
    assert legal
    pos = legal[0]
    apply_grid_move(s, pos, color="W", as_human=True)
    assert s["cells"][pos] == "W"


@pytest.mark.skipif(
    not (REPO / DOM / "2x2_2.ig").is_file(), reason="benchmark missing"
)
def test_domineering_two_cell_move() -> None:
    s = new_grid_session(f"{DOM}/2x2_2.ig", f"{DOM}/domain.ig")
    assert s["style"] == "domineering"
    # Black vertical at a1 covers a1,a2
    assert "a1" in legal_cells_for(s, "B")
    apply_grid_move(s, "a1", color="B")
    assert s["cells"]["a1"] == "B" and s["cells"]["a2"] == "B"
    # White horizontal at b1? board is 2x2: after black a1+a2, white can b1 if b1 and ... 
    # a1,a2 taken; white needs (x,y)+(x+1,y). Only row free is y with open pairs.
    legal_w = legal_cells_for(s, "W")
    # might be empty if black took a column — that's ok
    assert s["to_move"] == "W"


@pytest.mark.skipif(
    not (REPO / HTTT / "3x3_3_domino.ig").is_file(), reason="benchmark missing"
)
def test_grid_qbf_solve_fast() -> None:
    s = new_grid_session(
        f"{HTTT}/3x3_3_domino.ig",
        f"{HTTT}/domain.ig",
    )
    r = solve_grid_qbf(s, timeout=3.0)
    assert r["status"] in ("SAT", "UNSAT", "TIMEOUT")
    # this instance is known SAT under 3s
    assert r["status"] == "SAT", r
