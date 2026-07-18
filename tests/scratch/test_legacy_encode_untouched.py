"""Guard: golden QCIR path (qsage.encode) still works."""

from __future__ import annotations

from pathlib import Path

import pytest

from qsage.encode.bwnib import encode_bwnib
from qsage.encode.normalize import normalize_qcir

REPO = Path(__file__).resolve().parents[2]


def test_bwnib_still_matches_one_golden() -> None:
    domain = REPO / "Benchmarks/SAT2023_GDDL/GDDL_models/httt/domain.ig"
    problem = REPO / "Benchmarks/SAT2023_GDDL/GDDL_models/httt/3x3_3_domino.ig"
    golden = REPO / "Benchmarks/SAT2023_GDDL/QBF_instances/httt/3x3_3_domino_bwnib.qcir"
    if not golden.is_file():
        pytest.skip("golden missing")
    got = normalize_qcir(encode_bwnib(domain, problem))
    want = normalize_qcir(golden.read_text(encoding="utf-8"))
    assert got == want
