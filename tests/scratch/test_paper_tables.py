"""
Paper tables + dual-check against previous encoders.

Every case asserts:
  1. scratch SAT/UNSAT == previous code (pg / bwnib)
  2. that answer == paper expectation when known

Breakthrough rows still open vs nested bwnib are xfail (must still *run*
the dual-check so the failure mode stays visible).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qsage.solve.paper_checks import paper_cases
from qsage.solve.qubi import qubi_available

from tests.scratch.conftest_oracle import (
    assert_scratch_matches_prev,
    solve_scratch_and_prev_grid,
    solve_scratch_and_prev_hex,
    status_str,
)

REPO = Path(__file__).resolve().parents[2]
MODELS = REPO / "Benchmarks" / "SAT2023_GDDL" / "GDDL_models"
HEX_DIR = REPO / "Benchmarks" / "B-Hex"

FOLDER = {
    "httt": "httt",
    "B": "breakthrough",
    "BSP": "breakthrough-second-player",
    "C4": "connect-c",
    "D": "domineering",
}

HEX_PAPER_STEMS: list[tuple[str, str]] = [
    ("hein_04_3x3-03", "UNSAT"),
    ("hein_04_3x3-05", "SAT"),
    ("hein_07_4x4-07", "UNSAT"),
    ("hein_09_4x4-05", "UNSAT"),
    ("hein_09_4x4-07", "SAT"),
    ("hein_12_4x4-05", "UNSAT"),
    ("hein_12_4x4-07", "SAT"),
    ("hein_06_4x4-11", "UNSAT"),
    ("browne_5x5_07", "UNSAT"),
]


@pytest.mark.skipif(not qubi_available(), reason="QuBi not built")
@pytest.mark.parametrize(
    "stem,expect", HEX_PAPER_STEMS, ids=[s for s, _ in HEX_PAPER_STEMS]
)
def test_hex_paper_and_previous_pg(stem: str, expect: str) -> None:
    path = HEX_DIR / f"{stem}.pg"
    if not path.is_file():
        pytest.skip(f"missing {path}")
    scratch, prev = solve_scratch_and_prev_hex(path, timeout=120)
    assert_scratch_matches_prev(
        scratch, prev, label=stem, paper_expect=expect
    )


@pytest.mark.skipif(not qubi_available(), reason="QuBi not built")
def test_hex_depth_pairs_vs_previous_pg() -> None:
    """UNSAT at low depth, SAT at critical depth — both encoders agree."""
    pairs = [
        ("hein_04_3x3-03", "hein_04_3x3-05"),
        ("hein_09_4x4-05", "hein_09_4x4-07"),
        ("hein_12_4x4-05", "hein_12_4x4-07"),
    ]
    for lo, hi in pairs:
        plo, phi = HEX_DIR / f"{lo}.pg", HEX_DIR / f"{hi}.pg"
        if not plo.is_file() or not phi.is_file():
            pytest.skip("missing pair")
        s_lo, p_lo = solve_scratch_and_prev_hex(plo, timeout=120)
        s_hi, p_hi = solve_scratch_and_prev_hex(phi, timeout=120)
        assert_scratch_matches_prev(
            s_lo, p_lo, label=lo, paper_expect="UNSAT"
        )
        assert_scratch_matches_prev(
            s_hi, p_hi, label=hi, paper_expect="SAT"
        )


@pytest.mark.skipif(not qubi_available(), reason="QuBi not built")
@pytest.mark.parametrize("case", paper_cases(), ids=[c.name for c in paper_cases()])
def test_paper_case_vs_previous_encoder(case) -> None:
    """
    Dual oracle: scratch == previous (bwnib/pg) == paper expect.
    """
    if case.name.startswith("hex/"):
        path = HEX_DIR / f"{case.name.split('/', 1)[1]}.pg"
        scratch, prev = solve_scratch_and_prev_hex(path, timeout=120)
        assert_scratch_matches_prev(
            scratch, prev, label=case.name, paper_expect=case.expect
        )
        return

    folder, stem = case.name.split("/", 1)
    model = FOLDER[folder]
    domain = MODELS / model / "domain.ig"
    problem = MODELS / model / f"{stem}.ig"
    if not domain.is_file() or not problem.is_file():
        pytest.skip("missing model files")

    scratch, prev = solve_scratch_and_prev_grid(
        domain, problem, timeout=120
    )
    assert_scratch_matches_prev(
        scratch,
        prev,
        label=case.name,
        paper_expect=case.expect,
    )


_GRID_FAMILY_SMOKE = [
    ("httt", "3x3_3_domino"),
    ("httt", "3x3_5_el"),
    ("httt", "3x3_9_tic"),
    ("connect-c", "2x2_3_connect2"),
    ("domineering", "2x2_2"),
    ("breakthrough", "2x4_13"),
]


@pytest.mark.skipif(not qubi_available(), reason="QuBi not built")
@pytest.mark.parametrize(
    "folder,stem",
    _GRID_FAMILY_SMOKE,
    ids=[f"{f}/{s}" for f, s in _GRID_FAMILY_SMOKE],
)
def test_grid_families_always_vs_bwnib(folder: str, stem: str) -> None:
    """Smoke dual-check across game families (previous = bwnib)."""
    domain = MODELS / folder / "domain.ig"
    problem = MODELS / folder / f"{stem}.ig"
    if not domain.is_file() or not problem.is_file():
        pytest.skip("missing")
    scratch, prev = solve_scratch_and_prev_grid(
        domain, problem, timeout=90
    )
    assert_scratch_matches_prev(scratch, prev, label=f"{folder}/{stem}")
