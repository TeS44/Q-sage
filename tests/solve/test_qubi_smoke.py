"""Smoke tests for QuBi (skip if binary missing)."""

from pathlib import Path

import pytest

from qsage.solve.paper_checks import paper_cases
from qsage.solve.qubi import _parse_qubi, qubi_available, solve_qcir_qubi
from qsage.solve.result import Status


def test_parse_result_true() -> None:
    assert _parse_qubi("Result: TRUE\n") is Status.SAT
    assert _parse_qubi("Result: FALSE\n") is Status.UNSAT


@pytest.mark.skipif(not qubi_available(), reason="solvers/qubi/qubi not built")
def test_domino_paper_sat() -> None:
    q = Path("Benchmarks/SAT2023_GDDL/QBF_instances/httt/3x3_3_domino_bwnib.qcir")
    res = solve_qcir_qubi(q.read_text(), timeout=30)
    assert res.status is Status.SAT


@pytest.mark.skipif(not qubi_available(), reason="solvers/qubi/qubi not built")
def test_paper_table2_sample() -> None:
    fails = []
    for case in paper_cases():
        res = solve_qcir_qubi(case.golden_qcir.read_text(), timeout=60)
        if res.status.value != case.expect:
            fails.append((case.name, case.expect, res.status.value, res.message))
    assert not fails, fails
