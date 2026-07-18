"""
Standalone Hex path-win QBF encoding.

Semantics (Black is existential):
  After ``depth`` alternating plies, can Black force a path of Black stones
  from start_border to end_border?

Important encoding rule
-----------------------
Universal (White) variables must **never** be able to falsify the matrix by
playing illegally (e.g. multi-hot). Otherwise every instance is UNSAT.

So each ply always selects **exactly one** cell (pointer). The stone is only
placed if that cell is still free; otherwise the ply is a no-op.
"""

from __future__ import annotations

from pathlib import Path

from qsage.scratch.circuit import Circuit
from qsage.scratch.parse_pg import HexGame, load_pg


def encode_hex_file(path: str | Path) -> str:
    return encode_hex(load_pg(path))


def encode_hex(game: HexGame) -> str:
    return _build(game).to_qcir()


def _build(game: HexGame) -> Circuit:
    c = Circuit()
    pos = list(game.positions)
    n = len(pos)
    ix = {p: i for i, p in enumerate(pos)}

    B0 = {ix[p] for p in game.black_initials if p in ix}
    W0 = {ix[p] for p in game.white_initials if p in ix}
    start = [ix[p] for p in game.start_border if p in ix]
    end = [ix[p] for p in game.end_border if p in ix]

    neigh: list[list[int]] = [[] for _ in range(n)]
    for p, nbs in game.neighbours.items():
        if p not in ix:
            continue
        i = ix[p]
        for q in nbs:
            if q in ix and ix[q] != i:
                neigh[i].append(ix[q])

    depth = game.depth
    if depth <= 0:
        depth = max(1, n)

    if game.black_turns and game.times:
        tmap = {t: i for i, t in enumerate(game.times)}
        black_plies = sorted({tmap[t] for t in game.black_turns if t in tmap})
    else:
        black_plies = list(range(0, depth, 2))
    black_ply = set(black_plies)

    # --- all vars first ---
    move: list[list[int]] = []
    for t in range(depth):
        vs = c.fresh(n)
        move.append(vs)
        if t in black_ply:
            c.exists(vs)
        else:
            c.forall(vs)

    c.const_true()
    c.const_false()

    cons: list[int] = []

    # play[t][i] = move[t][i] ∧ free_before(t,i)
    play: list[list[int]] = [[c.const_false() for _ in range(n)] for _ in range(depth)]

    for t in range(depth):
        cons.append(c.exactly_one(move[t]))

        for i in range(n):
            # free iff not initial and not successfully played earlier
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
        parts = [play[t][i] for t in range(depth) if t in black_ply]
        return c.or_(*parts) if parts else c.const_false()

    def is_white(i: int) -> int:
        if i in W0:
            return c.const_true()
        parts = [play[t][i] for t in range(depth) if t not in black_ply]
        return c.or_(*parts) if parts else c.const_false()

    black_lit = [is_black(i) for i in range(n)]
    # optional: cell never both colours (should follow from free)
    for i in range(n):
        cons.append(c.or_(c.not_(is_black(i)), c.not_(is_white(i))))

    # reachability on final black stones
    r = [
        black_lit[i] if i in start else c.const_false()
        for i in range(n)
    ]
    for _ in range(n):
        nxt = []
        for i in range(n):
            incoming = [r[i]] + [r[j] for j in neigh[i]]
            nxt.append(c.and_(black_lit[i], c.or_(*incoming)))
        r = nxt

    win = c.or_(*[r[i] for i in end]) if end else c.const_false()
    c.set_output(c.and_(*cons, win))
    return c
