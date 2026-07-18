"""
Standalone grid occupy-game encoding (HTTT-style).

Same legality rule as hex.py: each ply selects exactly one cell; placement
only if free (else no-op). Universal player cannot falsify via illegal multi-hot.
"""

from __future__ import annotations

from pathlib import Path

from qsage.scratch.circuit import Circuit
from qsage.scratch.parse_bddl import (
    GridProblem,
    eval_goal_shape,
    load_grid_problem,
)


def encode_grid_files(domain: str | Path, problem: str | Path) -> str:
    _ = domain
    return encode_grid(load_grid_problem(problem))


def encode_grid(problem: GridProblem) -> str:
    return _build(problem).to_qcir()


def _build(prob: GridProblem) -> Circuit:
    c = Circuit()
    W, H, depth = prob.width, prob.height, prob.depth
    cells = [(x, y) for x in range(1, W + 1) for y in range(1, H + 1)]
    n = len(cells)
    ci = {xy: i for i, xy in enumerate(cells)}

    B0 = {ci[xy] for xy in prob.black_init if xy in ci}
    W0 = {ci[xy] for xy in prob.white_init if xy in ci}

    black_first = prob.black_turn != "second"

    def is_black_ply(t: int) -> bool:
        return (t % 2 == 0) if black_first else (t % 2 == 1)

    move: list[list[int]] = []
    for t in range(depth):
        vs = c.fresh(n)
        move.append(vs)
        if is_black_ply(t):
            c.exists(vs)
        else:
            c.forall(vs)

    c.const_true()
    c.const_false()

    cons: list[int] = []
    play: list[list[int]] = [[c.const_false() for _ in range(n)] for _ in range(depth)]

    for t in range(depth):
        cons.append(c.exactly_one(move[t]))
        for i in range(n):
            if i in B0 or i in W0:
                free = c.const_false()
            else:
                earlier = [play[s][i] for s in range(t)]
                free = (
                    c.const_true()
                    if not earlier
                    else c.and_(*[c.not_(p) for p in earlier])
                )
            play[t][i] = c.and_(move[t][i], free)

    def is_black(i: int) -> int:
        if i in B0:
            return c.const_true()
        parts = [play[t][i] for t in range(depth) if is_black_ply(t)]
        return c.or_(*parts) if parts else c.const_false()

    black_lit = [is_black(i) for i in range(n)]

    shape_ok: list[int] = []
    for shape in prob.black_goals:
        for ax in range(1, W + 1):
            for ay in range(1, H + 1):
                inst = eval_goal_shape(shape, ax, ay, W, H)
                if not inst:
                    continue
                lits = []
                for x, y, neg in inst:
                    lit = black_lit[ci[(x, y)]]
                    lits.append(c.not_(lit) if neg else lit)
                if lits:
                    shape_ok.append(c.and_(*lits))

    win = c.or_(*shape_ok) if shape_ok else c.const_false()
    c.set_output(c.and_(*cons, win))
    return c
