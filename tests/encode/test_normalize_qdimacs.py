"""Unit tests for normalize + a tiny QDIMACS conversion smoke check."""

from __future__ import annotations

from qsage.encode.normalize import normalize_qcir
from qsage.encode.qdimacs import qcir_to_qdimacs


def test_normalize_strips_comments() -> None:
    raw = """#QCIR-G14
# comment
exists(1, 2)
output(3)
3 = and(1, 2)
"""
    assert normalize_qcir(raw) == "exists(1, 2)\noutput(3)\n3 = and(1, 2)\n"


def test_qdimacs_smoke() -> None:
    qcir = """#QCIR-G14
exists(1, 2)
output(3)
3 = and(1, 2)
"""
    qd = qcir_to_qdimacs(qcir)
    assert qd.startswith("p cnf")
    assert "e " in qd
    assert " 0\n" in qd
