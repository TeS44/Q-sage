"""
Shared helpers: always dual-check scratch against the previous (production) encoders.

- Hex → ``qsage.encode.positional`` (``pg``), prefer golden QCIR if present
- Grid → ``qsage.encode.bwnib``
"""

from __future__ import annotations

from pathlib import Path

from qsage.solve.qubi import solve_qcir_qubi
from qsage.solve.result import Status

REPO = Path(__file__).resolve().parents[2]
GOLD_PG = REPO / "Benchmarks" / "positional_goldens" / "pg"


def status_str(res) -> str:
    if res.status is Status.SAT:
        return "SAT"
    if res.status is Status.UNSAT:
        return "UNSAT"
    return res.status.value


def solve_scratch_and_prev_hex(
    path: Path, *, timeout: float = 90.0
) -> tuple[str, str]:
    """Return (scratch_status, previous_pg_status)."""
    from qsage.encode.positional import encode_positional
    from qsage.scratch.hex import encode_hex_file

    scratch_q = encode_hex_file(path)
    s = status_str(solve_qcir_qubi(scratch_q, timeout=timeout))

    golden = GOLD_PG / f"{path.stem}_pg.qcir"
    if golden.is_file():
        prev_q = golden.read_text(encoding="utf-8")
    else:
        prev_q = encode_positional(path, encoding="pg")
    p = status_str(solve_qcir_qubi(prev_q, timeout=timeout))
    return s, p


def solve_scratch_and_prev_grid(
    domain: Path, problem: Path, *, timeout: float = 120.0
) -> tuple[str, str]:
    """Return (scratch_status, previous_bwnib_status)."""
    from qsage.encode.bwnib import encode_bwnib
    from qsage.scratch.grid import encode_grid_files

    s = status_str(
        solve_qcir_qubi(encode_grid_files(domain, problem), timeout=timeout)
    )
    p = status_str(solve_qcir_qubi(encode_bwnib(domain, problem), timeout=timeout))
    return s, p


def assert_scratch_matches_prev(
    scratch: str,
    prev: str,
    *,
    label: str,
    paper_expect: str | None = None,
) -> None:
    """
    Require scratch ≡ previous encoder on SAT/UNSAT.
    Optionally also require paper_expect when previous is definitive.
    """
    if prev not in ("SAT", "UNSAT"):
        raise AssertionError(
            f"{label}: previous encoder unclear ({prev}); cannot dual-check"
        )
    if scratch not in ("SAT", "UNSAT"):
        raise AssertionError(
            f"{label}: scratch unclear ({scratch}); previous={prev}"
        )
    assert scratch == prev, (
        f"{label}: scratch={scratch} previous={prev}"
        + (f" paper={paper_expect}" if paper_expect else "")
    )
    if paper_expect in ("SAT", "UNSAT"):
        assert prev == paper_expect, (
            f"{label}: previous={prev} disagrees with paper={paper_expect}"
        )
        assert scratch == paper_expect, (
            f"{label}: scratch={scratch} disagrees with paper={paper_expect}"
        )
