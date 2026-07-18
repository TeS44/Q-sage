"""Normalized QCIR from bwnib must match paper goldens (no solver)."""

from __future__ import annotations

from pathlib import Path

import pytest

from qsage.encode.bwnib import encode_bwnib
from qsage.encode.golden_map import iter_bwnib_goldens
from qsage.encode.normalize import normalize_qcir

CASES = iter_bwnib_goldens()
_REPO = Path(__file__).resolve().parents[2]


def _id(case: tuple[Path, Path, Path]) -> str:
    golden, _, _ = case
    return str(golden.relative_to(_REPO))


@pytest.mark.parametrize("case", CASES, ids=_id)
def test_bwnib_matches_golden(case: tuple[Path, Path, Path]) -> None:
    golden, domain, problem = case
    assert domain.is_file(), domain
    assert problem.is_file(), problem
    got = normalize_qcir(encode_bwnib(domain, problem))
    want = normalize_qcir(golden.read_text(encoding="utf-8"))
    assert got == want


def test_at_least_one_golden() -> None:
    assert len(CASES) >= 50
