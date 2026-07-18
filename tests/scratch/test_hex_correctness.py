"""
Semantic correctness for scratch Hex — always dual-check vs previous ``pg``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qsage.scratch.hex import encode_hex_file
from qsage.solve.qubi import qubi_available

from tests.scratch.conftest_oracle import (
    assert_scratch_matches_prev,
    solve_scratch_and_prev_hex,
)

REPO = Path(__file__).resolve().parents[2]
HEX_DIR = REPO / "Benchmarks" / "B-Hex"

HEX_EXPECT: list[tuple[str, str]] = [
    ("hein_04_3x3-03", "UNSAT"),
    ("hein_04_3x3-05", "SAT"),
    ("hein_09_4x4-05", "UNSAT"),
    ("hein_09_4x4-07", "SAT"),
    ("hein_12_4x4-05", "UNSAT"),
    ("hein_12_4x4-07", "SAT"),
    ("hein_07_4x4-07", "UNSAT"),
]


@pytest.mark.skipif(not HEX_DIR.is_dir(), reason="no B-Hex")
def test_encode_hex_produces_qcir() -> None:
    path = HEX_DIR / "hein_04_3x3-05.pg"
    if not path.is_file():
        pytest.skip("missing board")
    text = encode_hex_file(path)
    assert text.startswith("#QCIR-G14")
    assert "exists(" in text
    assert "forall(" in text
    assert "output(" in text
    assert len(text) > 100


@pytest.mark.skipif(not qubi_available(), reason="QuBi not built")
@pytest.mark.parametrize("stem,expect", HEX_EXPECT, ids=[s for s, _ in HEX_EXPECT])
def test_hex_sat_unsat_vs_paper_and_previous_pg(stem: str, expect: str) -> None:
    path = HEX_DIR / f"{stem}.pg"
    if not path.is_file():
        pytest.skip(f"missing {path}")
    scratch, prev = solve_scratch_and_prev_hex(path, timeout=180)
    assert_scratch_matches_prev(
        scratch, prev, label=stem, paper_expect=expect
    )


@pytest.mark.skipif(not qubi_available(), reason="QuBi not built")
def test_empty_board_depth_unsat_vs_previous() -> None:
    path = HEX_DIR / "hein_04_3x3-03.pg"
    if not path.is_file():
        pytest.skip("missing")
    scratch, prev = solve_scratch_and_prev_hex(path, timeout=60)
    assert_scratch_matches_prev(
        scratch, prev, label="hein_04_3x3-03", paper_expect="UNSAT"
    )
