"""
Semantic correctness for scratch Hex encoding.

Ground truth: paper / qsage positional table (Black has bounded winning strategy).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qsage.scratch.hex import encode_hex_file

REPO = Path(__file__).resolve().parents[2]
HEX_DIR = REPO / "Benchmarks" / "B-Hex"
QUBI = REPO / "solvers" / "qubi" / "qubi"

# (stem, expected) — from docs/POSITIONAL_RESULTS.md / paper
HEX_EXPECT: list[tuple[str, str]] = [
    ("hein_04_3x3-03", "UNSAT"),
    ("hein_04_3x3-05", "SAT"),
    ("hein_09_4x4-05", "UNSAT"),
    ("hein_09_4x4-07", "SAT"),
    ("hein_12_4x4-05", "UNSAT"),
    ("hein_12_4x4-07", "SAT"),
    ("hein_07_4x4-07", "UNSAT"),
    ("hein_07_4x4-09", "SAT"),
]


def _qubi_available() -> bool:
    return QUBI.is_file()


def _solve_qcir(qcir: str, timeout: int = 120) -> str:
    """Return SAT | UNSAT | UNKNOWN using QuBi."""
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".qcir", delete=False) as f:
        f.write(qcir)
        path = f.name
    try:
        proc = subprocess.run(
            [str(QUBI), "-v=0", "-w=1", path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    raw = (proc.stdout or "") + (proc.stderr or "")
    up = raw.upper()
    if "RESULT: TRUE" in up or up.rstrip().endswith("TRUE"):
        return "SAT"
    if "RESULT: FALSE" in up or up.rstrip().endswith("FALSE"):
        return "UNSAT"
    if "TRUE" in up and "FALSE" not in up.split("RESULT")[-1]:
        return "SAT"
    if "FALSE" in up:
        return "UNSAT"
    return f"UNKNOWN:{raw[-200:]}"


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


@pytest.mark.skipif(not _qubi_available(), reason="QuBi not built")
@pytest.mark.xfail(reason="scratch Hex QBF still experimental; play UI uses qsage.encode", strict=False)
@pytest.mark.parametrize("stem,expect", HEX_EXPECT, ids=[s for s, _ in HEX_EXPECT])
def test_hex_sat_unsat_vs_paper(stem: str, expect: str) -> None:
    path = HEX_DIR / f"{stem}.pg"
    if not path.is_file():
        pytest.skip(f"missing {path}")
    qcir = encode_hex_file(path)
    got = _solve_qcir(qcir, timeout=180)
    assert got == expect, f"{stem}: expected {expect}, got {got}"


@pytest.mark.skipif(not _qubi_available(), reason="QuBi not built")
@pytest.mark.xfail(reason="scratch experimental", strict=False)
def test_empty_board_depth1_no_path_is_unsat_when_no_connection() -> None:
    """Sanity: depth 0-ish board with no black path and no moves → UNSAT."""
    # hein_04 depth 3 is known UNSAT (not enough moves to connect)
    path = HEX_DIR / "hein_04_3x3-03.pg"
    if not path.is_file():
        pytest.skip("missing")
    assert _solve_qcir(encode_hex_file(path)) == "UNSAT"
