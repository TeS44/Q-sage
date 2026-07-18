"""Parsers for scratch inputs."""

from __future__ import annotations

from pathlib import Path

import pytest

from qsage.scratch.parse_bddl import load_grid_problem
from qsage.scratch.parse_pg import load_pg

REPO = Path(__file__).resolve().parents[2]
HEX = REPO / "Benchmarks" / "B-Hex" / "hein_04_3x3-05.pg"
GRID = (
    REPO
    / "Benchmarks"
    / "SAT2023_GDDL"
    / "GDDL_models"
    / "httt"
    / "3x3_3_domino.ig"
)
DOMAIN = (
    REPO
    / "Benchmarks"
    / "SAT2023_GDDL"
    / "GDDL_models"
    / "httt"
    / "domain.ig"
)


@pytest.mark.skipif(not HEX.is_file(), reason="benchmark missing")
def test_load_hex_hein04() -> None:
    g = load_pg(HEX)
    assert len(g.positions) == 9
    assert g.depth == 5
    assert g.black_initials
    assert g.start_border
    assert g.end_border
    assert g.neighbours


@pytest.mark.skipif(not GRID.is_file(), reason="benchmark missing")
def test_load_grid_domino() -> None:
    p = load_grid_problem(GRID)
    assert p.width == 3 and p.height == 3
    assert p.depth == 3
    assert p.black_goals
