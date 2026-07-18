"""Scratch public API must emit the same QCIR as previous / paper goldens."""

from __future__ import annotations

from pathlib import Path

import pytest

from qsage.encode.bwnib import encode_bwnib
from qsage.encode.normalize import normalize_qcir
from qsage.encode.positional import encode_positional
from qsage.scratch.grid import encode_grid_files
from qsage.scratch.hex import encode_hex_file

REPO = Path(__file__).resolve().parents[2]
HEX = REPO / "Benchmarks" / "B-Hex"
GOLD_PG = REPO / "Benchmarks" / "positional_goldens" / "pg"
MODELS = REPO / "Benchmarks" / "SAT2023_GDDL" / "GDDL_models"
GOLD_G = REPO / "Benchmarks" / "SAT2023_GDDL" / "QBF_instances"


def _gates(q: str) -> int:
    return sum(1 for line in q.splitlines() if " = " in line)


HEX_STEMS = [
    "hein_04_3x3-03",
    "hein_04_3x3-05",
    "hein_09_4x4-05",
    "hein_09_4x4-07",
    "hein_12_4x4-05",
    "hein_12_4x4-07",
    "hein_07_4x4-07",
    "browne_5x5_07",
]

GRID_CASES = [
    ("httt", "httt", "3x3_3_domino"),
    ("httt", "httt", "3x3_9_tic"),
    ("D", "domineering", "2x2_2"),
    ("D", "domineering", "2x4_4"),
    ("C4", "connect-c", "2x2_3_connect2"),
    ("B", "breakthrough", "2x4_13"),
    ("BSP", "breakthrough-second-player", "2x4_8"),
]


@pytest.mark.parametrize("stem", HEX_STEMS)
def test_hex_qcir_matches_previous_and_golden(stem: str) -> None:
    path = HEX / f"{stem}.pg"
    if not path.is_file():
        pytest.skip("missing board")
    scratch = encode_hex_file(path)
    prev = encode_positional(path, encoding="pg")
    assert normalize_qcir(scratch) == normalize_qcir(prev)
    assert _gates(scratch) == _gates(prev)
    golden = GOLD_PG / f"{stem}_pg.qcir"
    if golden.is_file():
        assert normalize_qcir(scratch) == normalize_qcir(
            golden.read_text(encoding="utf-8")
        )


@pytest.mark.parametrize("gfolder,fam,stem", GRID_CASES, ids=[c[2] for c in GRID_CASES])
def test_grid_qcir_matches_previous_and_golden(
    gfolder: str, fam: str, stem: str
) -> None:
    dom = MODELS / fam / "domain.ig"
    prob = MODELS / fam / f"{stem}.ig"
    if not prob.is_file():
        pytest.skip("missing problem")
    scratch = encode_grid_files(dom, prob)
    prev = encode_bwnib(dom, prob)
    assert normalize_qcir(scratch) == normalize_qcir(prev)
    assert _gates(scratch) == _gates(prev)
    golden = GOLD_G / gfolder / f"{stem}_bwnib.qcir"
    if golden.is_file():
        assert normalize_qcir(scratch) == normalize_qcir(
            golden.read_text(encoding="utf-8")
        )


def test_no_legacy_imports_in_scratch_paper() -> None:
    """Paper package must not import the legacy/ tree."""
    import ast

    paper = REPO / "qsage" / "scratch" / "paper"
    for path in paper.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "legacy" not in alias.name, path
                    assert not alias.name.startswith("q_encodings"), path
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith("legacy"), path
                assert "legacy" not in mod, path
                # old package names must not appear as top-level deps
                assert not mod.startswith("q_encodings"), path
                assert not mod.startswith("utils."), path
                assert mod != "utils", path
