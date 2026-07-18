"""
Binary-index helpers for paper-style encodings (path-based Hex / bwnib).

Moves and board cells are identified by ``ceil(log2(N))`` bits, not one-hot.
"""

from __future__ import annotations

import math

from qsage.scratch.circuit import Circuit


def nbits(n: int) -> int:
    """Bits needed to name ``n`` values (at least 1)."""
    if n <= 1:
        return 1
    return math.ceil(math.log2(n))


def bin_lits(vars_: list[int], value: int) -> list[int]:
    """Literals that hold iff ``vars_`` encode ``value`` (MSB first)."""
    k = len(vars_)
    out: list[int] = []
    for j in range(k):
        bit = (value >> (k - 1 - j)) & 1
        out.append(vars_[j] if bit else -vars_[j])
    return out


def equals_value(c: Circuit, vars_: list[int], value: int) -> int:
    return c.and_(*bin_lits(vars_, value))


def equals_vars(c: Circuit, a: list[int], b: list[int]) -> int:
    """Bitwise equality of two same-length bitvectors."""
    assert len(a) == len(b)
    return c.and_(*[c.iff(x, y) for x, y in zip(a, b)])


def less_than(c: Circuit, vars_: list[int], bound: int) -> int:
    """
    ``vars_`` (MSB first) encode an integer strictly less than ``bound``.

    Same construction as legacy ``utils.lessthen_cir`` (used for move
    domains that are not a power of two).
    """
    k = len(vars_)
    if bound <= 0:
        return c.const_false()
    if bound >= (1 << k):
        # every k-bit value is < bound
        return c.const_true()
    rep = format(bound, f"0{k}b")
    assert len(rep) == k
    clauses: list[int] = []
    for i in range(k):
        if rep[i] != "1":
            continue
        step: list[int] = []
        for j in range(i):
            step.append(vars_[j] if rep[j] == "1" else -vars_[j])
        step.append(-vars_[i])
        clauses.append(c.and_(*step) if step else c.const_true())
    return c.or_(*clauses) if clauses else c.const_false()


def adder(c: Circuit, vars_: list[int], num: int) -> list[int]:
    """
    Bitvector ``vars_ + num`` (MSB first). Same as legacy ``adder_cir``.
    Returns a list of literals/gates (not fresh vars).
    """
    k = len(vars_)
    rep = format(num, f"0{k}b")
    # carry[k-1] = 0; carry[i] from lower bits
    carries: list[int] = [0] * k
    carries[k - 1] = c.const_false()  # empty OR = 0 in legacy
    for i in range(1, k):
        idx = k - i - 1
        if rep[idx + 1] == "0":
            carries[idx] = c.and_(carries[idx + 1], vars_[idx + 1])
        else:
            carries[idx] = c.or_(carries[idx + 1], vars_[idx + 1])
    sums: list[int] = [0] * k
    for i in range(k):
        idx = k - 1 - i
        eq = c.iff(carries[idx], vars_[idx])
        # legacy: if bit 0, sum = ¬eq; if bit 1, sum = eq
        sums[idx] = -eq if rep[idx] == "0" else eq
    return sums


def subtractor(c: Circuit, vars_: list[int], num: int) -> list[int]:
    """``vars_ - num`` via two's complement (legacy ``subtractor_cir``)."""
    k = len(vars_)
    rep = format(num, f"0{k}b")
    ones = "".join("1" if ch == "0" else "0" for ch in rep)
    twos = int(ones, 2) + 1
    return adder(c, vars_, twos)
