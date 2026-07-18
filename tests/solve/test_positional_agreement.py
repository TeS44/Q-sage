"""
Paper (arXiv:2301.07345): every encoding is True iff Black has a bounded winning strategy.
So pg, cp, and ibign must agree on SAT/UNSAT for the same instance.
"""

from __future__ import annotations

import pytest

from qsage.encode.positional import encode_positional
from qsage.solve.qubi import qubi_available, solve_qcir_qubi
from qsage.solve.result import Status

# Small/medium Hein boards where all three encodings finish quickly
AGREE_STEMS = [
    "hein_04_3x3-03",  # no win
    "hein_04_3x3-05",  # win
    "hein_09_4x4-05",  # no win
    "hein_09_4x4-07",  # win
    "hein_12_4x4-05",  # no win
    "hein_12_4x4-07",  # win
    "hein_07_4x4-07",  # no win
    "hein_07_4x4-09",  # win
]


@pytest.mark.skipif(not qubi_available(), reason="QuBi not built")
@pytest.mark.parametrize("stem", AGREE_STEMS)
def test_pg_cp_ibign_same_answer(stem: str) -> None:
    answers = {}
    for enc in ("pg", "cp", "ibign"):
        qcir = encode_positional(f"Benchmarks/B-Hex/{stem}.pg", enc)
        res = solve_qcir_qubi(qcir, timeout=120)
        assert res.status in (Status.SAT, Status.UNSAT), (
            f"{stem} {enc}: {res.status} {res.message}"
        )
        answers[enc] = res.status
    assert len(set(answers.values())) == 1, f"{stem} disagree: {answers}"
