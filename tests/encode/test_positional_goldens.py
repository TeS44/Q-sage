"""Normalized QCIR for positional encodings must match saved legacy goldens."""

from __future__ import annotations

from pathlib import Path

import pytest

from qsage.encode.normalize import normalize_qcir
from qsage.encode.positional import POSITIONAL_ENCODINGS, encode_positional

_REPO = Path(__file__).resolve().parents[2]
_GOLD = _REPO / "Benchmarks" / "positional_goldens"
_BENCH = _REPO / "Benchmarks" / "B-Hex"


def _cases() -> list[tuple[str, Path, Path]]:
    out: list[tuple[str, Path, Path]] = []
    for enc in sorted(POSITIONAL_ENCODINGS):
        d = _GOLD / enc
        if not d.is_dir():
            continue
        for golden in sorted(d.glob(f"*_{enc}.qcir")):
            stem = golden.name[: -len(f"_{enc}.qcir")]
            problem = _BENCH / f"{stem}.pg"
            if problem.is_file():
                out.append((enc, problem, golden))
    return out


CASES = _cases()


def _id(case: tuple[str, Path, Path]) -> str:
    enc, _, golden = case
    return f"{enc}/{golden.name}"


@pytest.mark.parametrize("case", CASES, ids=_id)
def test_positional_matches_golden(case: tuple[str, Path, Path]) -> None:
    enc, problem, golden = case
    got = normalize_qcir(encode_positional(problem, enc))
    want = normalize_qcir(golden.read_text(encoding="utf-8"))
    assert got == want


def test_positional_golden_count() -> None:
    # 40 boards × 3 encodings
    assert len(CASES) >= 100
