"""Official encode QCIR must match paper goldens (and equal gate counts)."""

from __future__ import annotations

from pathlib import Path

import pytest

from qsage.encode.bwnib import encode_bwnib
from qsage.encode.normalize import normalize_qcir
from qsage.encode.positional import encode_positional

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
def test_hex_pg_matches_golden(stem: str) -> None:
    path = HEX / f"{stem}.pg"
    if not path.is_file():
        pytest.skip("missing board")
    qcir = encode_positional(path, encoding="pg")
    golden = GOLD_PG / f"{stem}_pg.qcir"
    if not golden.is_file():
        pytest.skip("missing golden")
    gold = golden.read_text(encoding="utf-8")
    assert normalize_qcir(qcir) == normalize_qcir(gold)
    assert _gates(qcir) == _gates(gold)


@pytest.mark.parametrize("gfolder,fam,stem", GRID_CASES, ids=[c[2] for c in GRID_CASES])
def test_bwnib_matches_golden(gfolder: str, fam: str, stem: str) -> None:
    dom = MODELS / fam / "domain.ig"
    prob = MODELS / fam / f"{stem}.ig"
    if not prob.is_file():
        pytest.skip("missing problem")
    qcir = encode_bwnib(dom, prob)
    golden = GOLD_G / gfolder / f"{stem}_bwnib.qcir"
    if not golden.is_file():
        pytest.skip("missing golden")
    gold = golden.read_text(encoding="utf-8")
    assert normalize_qcir(qcir) == normalize_qcir(gold)
    assert _gates(qcir) == _gates(gold)


def test_encode_paper_has_no_legacy_imports() -> None:
    import ast

    paper = REPO / "qsage" / "encode" / "paper"
    for path in paper.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            mods: list[str] = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            for mod in mods:
                assert not mod.startswith("legacy"), path
                assert not mod.startswith("q_encodings"), path
                assert mod != "utils" and not mod.startswith("utils."), path
