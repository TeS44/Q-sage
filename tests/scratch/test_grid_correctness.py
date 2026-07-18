"""
Semantic tests for scratch grid — always dual-check vs previous ``bwnib``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qsage.scratch.grid import encode_grid_files
from qsage.scratch.parse_bddl import load_grid_problem
from qsage.solve.qubi import qubi_available

from tests.scratch.conftest_oracle import (
    assert_scratch_matches_prev,
    solve_scratch_and_prev_grid,
)

REPO = Path(__file__).resolve().parents[2]
MODELS = REPO / "Benchmarks" / "SAT2023_GDDL" / "GDDL_models"
HTTT = MODELS / "httt"
DOMAIN = HTTT / "domain.ig"

# (domain_folder, problem_stem) — always vs bwnib
GRID_DUAL = [
    ("httt", "3x3_3_domino"),
    ("httt", "3x3_9_tic"),
    ("httt", "3x3_5_el"),
    ("connect-c", "2x2_3_connect2"),
    ("connect-c", "3x3_3_connect2"),
    ("domineering", "2x2_2"),
    ("breakthrough", "2x4_13"),
]


@pytest.mark.skipif(not DOMAIN.is_file(), reason="no httt domain")
def test_encode_grid_qcir_shape() -> None:
    prob = HTTT / "3x3_3_domino.ig"
    text = encode_grid_files(DOMAIN, prob)
    assert text.startswith("#QCIR-G14")
    assert "exists(" in text
    assert "output(" in text
    p = load_grid_problem(prob)
    assert p.depth == 3
    assert p.black_goals


@pytest.mark.skipif(not qubi_available(), reason="QuBi not built")
@pytest.mark.parametrize(
    "folder,stem",
    GRID_DUAL,
    ids=[f"{f}/{s}" for f, s in GRID_DUAL],
)
def test_grid_scratch_matches_previous_bwnib(folder: str, stem: str) -> None:
    domain = MODELS / folder / "domain.ig"
    problem = MODELS / folder / f"{stem}.ig"
    if not domain.is_file() or not problem.is_file():
        pytest.skip("missing files")
    scratch, prev = solve_scratch_and_prev_grid(
        domain, problem, timeout=180
    )
    assert_scratch_matches_prev(
        scratch, prev, label=f"{folder}/{stem}"
    )
