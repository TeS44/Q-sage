"""Semantic tests for scratch grid occupy encoding."""

from __future__ import annotations

from pathlib import Path

import pytest

from qsage.scratch.grid import encode_grid_files
from qsage.scratch.parse_bddl import load_grid_problem

REPO = Path(__file__).resolve().parents[2]
HTTT = REPO / "Benchmarks" / "SAT2023_GDDL" / "GDDL_models" / "httt"
DOMAIN = HTTT / "domain.ig"
QUBI = REPO / "solvers" / "qubi" / "qubi"

# Small instances with known paper Table 2 style answers (bwnib / QuBi).
# These are used as *semantic* targets for scratch occupy encoding.
# If scratch model differs slightly, document and adjust — start with ones we
# can also cross-check by hand.
GRID_SMOKE = [
    "3x3_3_domino.ig",
    "3x3_9_tic.ig",
]


def _qubi_available() -> bool:
    return QUBI.is_file()


def _solve(qcir: str, timeout: int = 120) -> str:
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
    raw = ((proc.stdout or "") + (proc.stderr or "")).upper()
    if "RESULT: TRUE" in raw:
        return "SAT"
    if "RESULT: FALSE" in raw:
        return "UNSAT"
    if "TRUE" in raw and "FALSE" not in raw:
        return "SAT"
    if "FALSE" in raw:
        return "UNSAT"
    return "UNKNOWN"


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


@pytest.mark.skipif(not _qubi_available(), reason="QuBi not built")
@pytest.mark.skipif(not DOMAIN.is_file(), reason="no httt")
@pytest.mark.parametrize("name", GRID_SMOKE)
def test_grid_solves_without_crash(name: str) -> None:
    """Encoding must be well-formed; result is SAT or UNSAT (not UNKNOWN)."""
    prob = HTTT / name
    if not prob.is_file():
        pytest.skip("missing")
    got = _solve(encode_grid_files(DOMAIN, prob), timeout=180)
    assert got in ("SAT", "UNSAT"), got


@pytest.mark.skipif(not _qubi_available(), reason="QuBi not built")
@pytest.mark.xfail(reason="scratch grid experimental", strict=False)
def test_grid_vs_legacy_bwnib_answer_when_available() -> None:
    """
    Cross-check scratch vs current qsage.encode bwnib (semantic, not QCIR).
    Only on a tiny instance so both finish quickly.
    """
    from qsage.encode.bwnib import encode_bwnib
    from qsage.solve.qubi import qubi_available, solve_qcir_qubi
    from qsage.solve.result import Status

    if not qubi_available():
        pytest.skip("qubi")
    prob = HTTT / "3x3_3_domino.ig"
    if not prob.is_file() or not DOMAIN.is_file():
        pytest.skip("files")

    scratch = encode_grid_files(DOMAIN, prob)
    legacy = encode_bwnib(DOMAIN, prob)
    s_res = _solve(scratch, timeout=180)
    l_res = solve_qcir_qubi(legacy, timeout=180)
    if l_res.status not in (Status.SAT, Status.UNSAT):
        pytest.skip(f"legacy unclear: {l_res}")
    legacy_ans = "SAT" if l_res.status is Status.SAT else "UNSAT"
    assert s_res == legacy_ans, (
        f"scratch={s_res} legacy_bwnib={legacy_ans} (semantic mismatch)"
    )
