"""Unit tests for the standalone circuit builder."""

from __future__ import annotations

from qsage.scratch.circuit import Circuit


def test_and_or_not_emit_qcir() -> None:
    c = Circuit()
    x, y = c.fresh(2)
    c.exists([x, y])
    g = c.and_(x, c.or_(y, c.not_(x)))
    c.set_output(g)
    text = c.to_qcir()
    assert text.startswith("#QCIR-G14")
    assert "exists(" in text
    assert "output(" in text
    assert " = and(" in text or " = or(" in text


def test_exactly_one() -> None:
    c = Circuit()
    vs = c.fresh(3)
    c.exists(vs)
    c.set_output(c.exactly_one(vs))
    text = c.to_qcir()
    assert "output(" in text
    # three vars → pairwise at-most-one gates
    assert text.count(" = or(") + text.count(" = and(") >= 1


def test_const_true_false() -> None:
    c = Circuit()
    c.set_output(c.and_(c.const_true(), c.not_(c.const_false())))
    text = c.to_qcir()
    assert "output(" in text
