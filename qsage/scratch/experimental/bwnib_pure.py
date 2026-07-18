"""
Black–white nested index-based encoding (bwnib) — arXiv:2303.16949.

From-scratch rewrite of the paper / legacy ``BlackWhiteNestedIndexBased``
encoder.  Readable structure, same formula family:

* Move vars: log action id + (x, y) cell indices (+ bound / stop bits)
* Board: ∀(x,y) with 2-bit predicates (occupied, colour) per ply
* Nested final matrix (Black ∃ / White ∀ strategy)
* Maker–breaker (``#blackgoal False``, e.g. Domineering): Black wins when
  White has no valid move
* Maker–maker (HTTT, Connect, Breakthrough, …): Black wins by completing
  a black goal shape; White early-stop checks that White has not won

Coordinates: BDDL files are 1-indexed; the binary encoding uses 0-based
indices (as in the previous code).

No imports from ``qsage.encode`` or ``legacy``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from qsage.scratch.experimental.bits import (
    adder,
    bin_lits,
    equals_value,
    equals_vars,
    less_than,
    nbits,
    subtractor,
)
from qsage.scratch.circuit import Circuit
from qsage.scratch.parse_bddl import (
    Action,
    Atom,
    GridDomain,
    GridProblem,
    eval_goal_shape,
)


# ---------------------------------------------------------------------------
# Action model (string form as in legacy Parse)
# ---------------------------------------------------------------------------


@dataclass
class BwnibAction:
    name: str
    positive_preconditions: list[str] = field(default_factory=list)
    negative_preconditions: list[str] = field(default_factory=list)
    positive_effects: list[str] = field(default_factory=list)
    negative_effects: list[str] = field(default_factory=list)
    positive_indexbounds: list[str] = field(default_factory=list)  # lt(?x,k)
    negative_indexbounds: list[str] = field(default_factory=list)


def _atom_str(a: Atom) -> str:
    return f"{a.pred}({a.x},{a.y})"


def _index_bounds_from_atoms(atoms: list[Atom], W: int, H: int) -> tuple[list[str], list[str]]:
    """
    Index bounds as in legacy ``compute_index_bounds`` + ``action.py``.

    Offsets in preconditions/effects produce::

        le(?x, xmax-k) → lt(?x, W-k)     (positive / upper)
        ge(?x, xmin+k) → lt(?x, k)       (negative bound: x ≥ k in 0-based)

    Example — left-diagonal ``?x-1,?y-1`` on a 2×4 board::

        +ib: lt(?x,2), lt(?y,4)
        -ib: lt(?x,1), lt(?y,1)
    """
    xmin = xmax = ymin = ymax = 0
    for a in atoms:
        for s, is_x in ((a.x.replace(" ", ""), True), (a.y.replace(" ", ""), False)):
            if s.startswith("?") and "+" in s:
                val = int(s.split("+")[1])
                if is_x:
                    xmax = max(xmax, val)
                else:
                    ymax = max(ymax, val)
            elif s.startswith("?") and "-" in s:
                val = int(s.split("-")[1])
                if is_x:
                    xmin = max(xmin, val)
                else:
                    ymin = max(ymin, val)

    pos = [f"lt(?x,{W - xmax})", f"lt(?y,{H - ymax})"]
    neg: list[str] = []
    # ge(?x, 1+xmin) → result = 1+xmin → result-1 = xmin → neg lt(?x, xmin)
    if xmin > 0:
        neg.append(f"lt(?x,{xmin})")
    if ymin > 0:
        neg.append(f"lt(?y,{ymin})")
    return pos, neg


def _convert_action(a: Action, W: int, H: int) -> BwnibAction:
    pos_pre: list[str] = []
    neg_pre: list[str] = []
    for atom in a.precondition:
        s = _atom_str(atom)
        if atom.negated:
            neg_pre.append(s)
        else:
            pos_pre.append(s)
    pos_eff = [_atom_str(e) for e in a.effect if not e.negated]
    neg_eff = [_atom_str(e) for e in a.effect if e.negated]
    all_atoms = list(a.precondition) + list(a.effect)
    pib, nib = _index_bounds_from_atoms(all_atoms, W, H)
    return BwnibAction(
        name=a.name,
        positive_preconditions=pos_pre,
        negative_preconditions=neg_pre,
        positive_effects=pos_eff,
        negative_effects=neg_eff,
        positive_indexbounds=pib,
        negative_indexbounds=nib,
    )


# ---------------------------------------------------------------------------
# Encoder
# ---------------------------------------------------------------------------


class BwnibEncoder:
    """
    Build a QCIR formula for one domain+problem pair.

    Main steps (see ``_build``)::

        1. allocate quantifiers / variables   (_alloc)
        2. transitions for each ply           (_black/_white/_dummy_transition)
        3. initial board under ∀ cell         (_initial)
        4. black / white goal circuits        (_black_goal, _white_goal_block)
        5. nested strategy matrix             (_nested_final)
    """

    def __init__(self, domain: GridDomain, problem: GridProblem) -> None:
        self.W = problem.width
        self.H = problem.height
        self.depth = int(problem.depth)
        self.black_first = problem.black_turn != "second"
        # even depth → pad, last dummy black (legacy last_turn)
        if self.depth % 2 == 0:
            self.depth += 1
            self.last_turn_black = False  # last is dummy
        else:
            self.last_turn_black = True

        self.black_actions = [_convert_action(a, self.W, self.H) for a in domain.black_actions]
        self.white_actions = [_convert_action(a, self.W, self.H) for a in domain.white_actions]
        if not self.black_actions:
            self.black_actions = [
                BwnibAction(
                    "occupy",
                    ["open(?x,?y)"],
                    [],
                    ["black(?x,?y)"],
                    [],
                    [f"lt(?x,{self.W})", f"lt(?y,{self.H})"],
                    [],
                )
            ]
        if not self.white_actions:
            self.white_actions = [
                BwnibAction(
                    "occupy",
                    ["open(?x,?y)"],
                    [],
                    ["white(?x,?y)"],
                    [],
                    [f"lt(?x,{self.W})", f"lt(?y,{self.H})"],
                    [],
                )
            ]

        self.n_black = len(self.black_actions)
        self.n_white = len(self.white_actions)
        self.max_white_pre = max(
            (len(a.positive_preconditions) + len(a.negative_preconditions) for a in self.white_actions),
            default=1,
        )
        self.maker_maker = bool(problem.white_goals)

        self._black_goal_atoms: list[list[Atom]] = list(problem.black_goals)
        self._white_goal_atoms: list[list[Atom]] = list(problem.white_goals)
        self.black_init = [(x - 1, y - 1) for x, y in problem.black_init]
        self.white_init = [(x - 1, y - 1) for x, y in problem.white_init]

        self.nb_act = nbits(self.n_black)
        self.nw_act = nbits(self.n_white)
        self.nx = nbits(self.W)
        self.ny = nbits(self.H)
        self.upper_x = 1 << self.nx
        self.upper_y = 1 << self.ny
        self.upper_ba = 1 << self.nb_act
        self.upper_wa = 1 << self.nw_act

        self.c = Circuit()
        self._alloc()
        self._build()

    def _alloc(self) -> None:
        c = self.c
        D = self.depth
        self.move: list[list] = []  # [t] -> [act, x, y, stop, (white: illegal_inds, white_stop?)]
        for t in range(D):
            if t % 2 == 0:
                act = c.fresh(self.nb_act)
            else:
                act = c.fresh(self.nw_act)
            x = c.fresh(self.nx)
            y = c.fresh(self.ny)
            stop = c.fresh(1)  # game-stop / padding bit
            entry = [act, x, y, stop]
            if t % 2 == 1:
                # white illegal indicators + optional white stop for maker-maker
                entry.append(c.fresh(max(1, self.max_white_pre)))
                if self.maker_maker:
                    entry.append(c.fresh(1))
            self.move.append(entry)

        # Quantifier prefix — matches legacy generate_quantifier_blocks:
        # white action is ∃ if only one white action; white x/y are ∃ if size 1;
        # bound + illegal indicators are always ∃; remaining white bits are ∀.
        for t in range(D):
            m = self.move[t]
            if t % 2 == 0:
                c.exists(m[0] + m[1] + m[2] + m[3])
            else:
                exists_w: list[int] = []
                forall_w: list[int] = []
                if self.n_white == 1:
                    exists_w.extend(m[0])
                else:
                    forall_w.extend(m[0])
                if self.W == 1:
                    exists_w.extend(m[1])
                else:
                    forall_w.extend(m[1])
                if self.H == 1:
                    exists_w.extend(m[2])
                else:
                    forall_w.extend(m[2])
                # maker-maker white-stop is universal
                if self.maker_maker:
                    forall_w.extend(m[5])
                if exists_w:
                    c.exists(exists_w)
                if forall_w:
                    c.forall(forall_w)
                # bound boolean + precondition indicators: existential
                c.exists(m[3])
                c.exists(m[4])

        # black goal choice + indices (∃)
        self.n_bg = max(1, len(self._black_goal_atoms))
        if self.n_bg > 1:
            self.bg_choice = c.fresh(nbits(self.n_bg))
            c.exists(self.bg_choice)
        else:
            self.bg_choice = []
        self.bg_x = c.fresh(self.nx)
        self.bg_y = c.fresh(self.ny)
        c.exists(self.bg_x + self.bg_y)

        # White-has-not-won witnesses: for each grounded white-shape placement,
        # ∃ a cell in that placement that is not white (see _white_goal_block).
        self._white_hole_vars: list[list[int]] = []
        if self.maker_maker and self._white_goal_atoms:
            for shape in self._white_goal_atoms:
                for ax in range(1, self.W + 1):
                    for ay in range(1, self.H + 1):
                        wshape = [
                            Atom("black", a.x, a.y, a.negated)
                            if a.pred == "white"
                            else a
                            for a in shape
                        ]
                        cells = eval_goal_shape(wshape, ax, ay, self.W, self.H)
                        if not cells:
                            continue
                        # one-hot (or binary) choice of which cell is the hole
                        n = len(cells)
                        bits = c.fresh(nbits(n) if n > 1 else 1)
                        c.exists(bits)
                        self._white_hole_vars.append(bits)
        else:
            self._white_hole_vars = []
        # symbolic board indices: ∃ if size 1 else ∀ (legacy)
        self.fx = c.fresh(self.nx)
        self.fy = c.fresh(self.ny)
        exists_idx: list[int] = []
        forall_idx: list[int] = []
        (exists_idx if self.W == 1 else forall_idx).extend(self.fx)
        (exists_idx if self.H == 1 else forall_idx).extend(self.fy)
        if exists_idx:
            c.exists(exists_idx)
        if forall_idx:
            c.forall(forall_idx)

        # predicates (occupied, colour) per time
        self.pred: list[list[int]] = []
        for _ in range(D + 1):
            vs = c.fresh(2)
            self.pred.append(vs)
            c.exists(vs)

        # QCIR ⊤/⊥ pads must exist before any gate (Circuit contract)
        c.const_true()
        c.const_false()

    # ---- helpers ----

    def _bin(self, vars_: list[int], val: int) -> int:
        return self.c.and_(*bin_lits(vars_, val))

    def _pred_lit(self, pred: str, t: int, sign: str) -> int:
        """Predicate holding at symbolic cell at time t."""
        c = self.c
        occ, col = self.pred[t]
        if pred == "black":
            body = c.and_(occ, -col)
        elif pred == "white":
            body = c.and_(occ, col)
        else:
            body = -occ  # open
        return body if sign == "pos" else -body

    def _pos_eq_pair(self, x_vars: list[int], y_vars: list[int], pair: list[str]) -> int:
        """Equality of (transformed x,y) with ∀ position (legacy generate_position_equalities…)."""
        c = self.c
        cx, cy = pair[0], pair[1]

        def axis(vars_: list[int], expr: str, forall_v: list[int]) -> int:
            expr = expr.strip()
            if expr in ("?x", "?y", "?c"):
                return equals_vars(c, vars_, forall_v)
            if expr.startswith("?x+") or expr.startswith("?y+") or expr.startswith("?c+"):
                n = int(expr.split("+")[1])
                return equals_vars(c, adder(c, vars_, n), forall_v)
            if expr.startswith("?x-") or expr.startswith("?y-") or expr.startswith("?c-"):
                n = int(expr.split("-")[1])
                return equals_vars(c, subtractor(c, vars_, n), forall_v)
            if expr == "xmax":
                return equals_value(c, forall_v, self.W - 1)
            if expr == "ymax":
                return equals_value(c, forall_v, self.H - 1)
            if expr == "xmin" or expr == "ymin":
                return equals_value(c, forall_v, 0)
            # constant 1-based → 0-based
            if expr.isdigit():
                return equals_value(c, forall_v, int(expr) - 1)
            # fallback
            return equals_vars(c, vars_, forall_v)

        return c.and_(axis(x_vars, cx, self.fx), axis(y_vars, cy, self.fy))

    def _parse_atom(self, s: str) -> tuple[str, list[str]]:
        s = s.replace(" ", "")
        m = re.match(r"(open|black|white)\(([^,]+),([^)]+)\)", s)
        if not m:
            raise ValueError(s)
        return m.group(1), [m.group(2), m.group(3)]

    def _if_then_pred(self, cond: int, pred: str, t: int, sign: str) -> int:
        body = self._pred_lit(pred, t, "pos")
        if sign == "pos":
            return self.c.implies(cond, body)
        return self.c.implies(cond, -body)

    def _index_bound_gate(self, x_vars: list[int], y_vars: list[int], bound: str) -> int | None:
        """lt(?x,k) or lt(?y,k); return None if redundant (bound == upper power)."""
        bound = bound.replace(" ", "")
        m = re.match(r"lt\(\?(x|y),(\d+)\)", bound)
        if not m:
            return None
        k = int(m.group(2))
        if m.group(1) == "x":
            if k == self.upper_x:
                return None
            return less_than(self.c, x_vars, k)
        if k == self.upper_y:
            return None
        return less_than(self.c, y_vars, k)

    # ---- transitions ----

    def _black_transition(self, t: int) -> int:
        c = self.c
        parts: list[int] = []
        act_v, x_v, y_v, stop = self.move[t][0], self.move[t][1], self.move[t][2], self.move[t][3]
        if self.upper_ba != self.n_black:
            parts.append(less_than(c, act_v, self.n_black))
        prop = equals_vars(c, self.pred[t], self.pred[t + 1])

        for i, action in enumerate(self.black_actions):
            if_act = self._bin(act_v, i)
            then_parts: list[int] = []
            for b in action.positive_indexbounds:
                g = self._index_bound_gate(x_v, y_v, b)
                if g is not None:
                    then_parts.append(g)
            for b in action.negative_indexbounds:
                g = self._index_bound_gate(x_v, y_v, b)
                if g is not None:
                    then_parts.append(-g)

            for pre in action.positive_preconditions:
                pred, pair = self._parse_atom(pre)
                eq = self._pos_eq_pair(x_v, y_v, pair)
                then_parts.append(self._if_then_pred(eq, pred, t, "pos"))
            for pre in action.negative_preconditions:
                pred, pair = self._parse_atom(pre)
                eq = self._pos_eq_pair(x_v, y_v, pair)
                then_parts.append(self._if_then_pred(eq, pred, t, "neg"))

            touched: list[int] = []
            for eff in action.positive_effects:
                pred, pair = self._parse_atom(eff)
                eq = self._pos_eq_pair(x_v, y_v, pair)
                touched.append(eq)
                then_parts.append(self._if_then_pred(eq, pred, t + 1, "pos"))
            for eff in action.negative_effects:
                pred, pair = self._parse_atom(eff)
                eq = self._pos_eq_pair(x_v, y_v, pair)
                touched.append(eq)
                then_parts.append(self._if_then_pred(eq, pred, t + 1, "neg"))

            touch_or = c.or_(*touched) if touched else c.const_false()
            then_parts.append(c.or_(touch_or, prop))
            then_all = c.and_(*then_parts) if then_parts else c.const_true()
            parts.append(c.implies(if_act, then_all))

        return c.and_(*parts)

    def _white_transition(self, t: int) -> int:
        """White transition + bound/precondition boolean linkage (legacy)."""
        c = self.c
        parts: list[int] = []
        act_v, x_v, y_v = self.move[t][0], self.move[t][1], self.move[t][2]
        bound_bit = self.move[t][3][0]  # legacy bound boolean
        pre_bits = self.move[t][4]
        prop = equals_vars(c, self.pred[t], self.pred[t + 1])

        # --- bounds → bound_bit ---
        bound_gates: list[int] = []
        if self.upper_wa != self.n_white:
            bound_gates.append(less_than(c, act_v, self.n_white))
        for i, action in enumerate(self.white_actions):
            if_act = self._bin(act_v, i)
            lt_parts: list[int] = []
            for b in action.positive_indexbounds:
                g = self._index_bound_gate(x_v, y_v, b)
                if g is not None:
                    lt_parts.append(g)
            for b in action.negative_indexbounds:
                g = self._index_bound_gate(x_v, y_v, b)
                if g is not None:
                    lt_parts.append(-g)
            if lt_parts:
                bound_gates.append(c.implies(if_act, c.and_(*lt_parts)))
        if not bound_gates:
            bound_gates.append(c.const_true())
        final_bound = c.and_(*bound_gates)
        parts.append(c.iff(bound_bit, final_bound))

        # --- preconditions → pre_bits ---
        for i, action in enumerate(self.white_actions):
            if_act = self._bin(act_v, i)
            pre_list = (
                [(p, "pos") for p in action.positive_preconditions]
                + [(p, "neg") for p in action.negative_preconditions]
            )
            for j, (pre, sign) in enumerate(pre_list):
                pred, pair = self._parse_atom(pre)
                eq = self._pos_eq_pair(x_v, y_v, pair)
                hold = self._pred_lit(pred, t, sign)
                bit = pre_bits[j] if j < len(pre_bits) else pre_bits[0]
                parts.append(c.or_(-if_act, -eq, c.iff(bit, hold)))

        # --- effects when valid ---
        for i, action in enumerate(self.white_actions):
            if_act = self._bin(act_v, i)
            pre_list = (
                [(p, "pos") for p in action.positive_preconditions]
                + [(p, "neg") for p in action.negative_preconditions]
            )
            valid_parts = [bound_bit]
            for j in range(len(pre_list)):
                valid_parts.append(pre_bits[j] if j < len(pre_bits) else pre_bits[0])
            valid = c.and_(*valid_parts)

            touched: list[int] = []
            then_parts: list[int] = []
            for eff in action.positive_effects:
                pred, pair = self._parse_atom(eff)
                eq = self._pos_eq_pair(x_v, y_v, pair)
                touched.append(eq)
                then_parts.append(self._if_then_pred(eq, pred, t + 1, "pos"))
            for eff in action.negative_effects:
                pred, pair = self._parse_atom(eff)
                eq = self._pos_eq_pair(x_v, y_v, pair)
                touched.append(eq)
                then_parts.append(self._if_then_pred(eq, pred, t + 1, "neg"))
            touch_or = c.or_(*touched) if touched else c.const_false()
            then_parts.append(c.or_(touch_or, prop))
            then_all = c.and_(*then_parts) if then_parts else prop
            parts.append(c.implies(c.and_(valid, if_act), then_all))

        if self.n_white == 1:
            parts.append(-act_v[0])

        return c.and_(*parts)

    def _dummy_transition(self, t: int) -> int:
        c = self.c
        m = self.move[t]
        # force all move bits 0
        zeros = m[0] + m[1] + m[2] + m[3]
        force0 = c.and_(*[-v for v in zeros])
        prop = equals_vars(c, self.pred[t], self.pred[t + 1])
        return c.and_(force0, prop)

    # ---- initial / goals / nested final ----

    def _initial(self) -> int:
        c = self.c
        parts: list[int] = []
        if self.black_init:
            is_b = c.or_(
                *[
                    c.and_(equals_value(c, self.fx, x), equals_value(c, self.fy, y))
                    for x, y in self.black_init
                ]
            )
            parts.append(c.implies(is_b, c.and_(self.pred[0][0], -self.pred[0][1])))
        else:
            is_b = c.const_false()
        if self.white_init:
            is_w = c.or_(
                *[
                    c.and_(equals_value(c, self.fx, x), equals_value(c, self.fy, y))
                    for x, y in self.white_init
                ]
            )
            parts.append(c.implies(is_w, c.and_(self.pred[0][0], self.pred[0][1])))
        else:
            is_w = c.const_false()
        if self.black_init or self.white_init:
            parts.append(c.or_(is_b, is_w, -self.pred[0][0]))
        else:
            parts.append(-self.pred[0][0])
        return c.and_(*parts)

    def _black_goal(self) -> int:
        """
        Black goal at final board (legacy generate_black_goal_gate).

        Quantifier order: ∃ goal indices, then ∀ board cell.  For a shape,
        each atom becomes ``(transformed goal idx = ∀cell) → colour``.
        That is *not* the same as grounding OR_anchor under a single ∀
        (which is always true on the empty board).
        """
        c = self.c
        if not self._black_goal_atoms:
            return c.const_false()

        shape_ok: list[int] = []
        for gi, shape in enumerate(self._black_goal_atoms):
            lits: list[int] = []
            # index bounds from offsets in the shape (legacy lt/nlt)
            xmin = xmax = ymin = ymax = 0
            for atom in shape:
                for s, is_x in (
                    (atom.x.replace(" ", ""), True),
                    (atom.y.replace(" ", ""), False),
                ):
                    if s.startswith("?") and "+" in s:
                        v = int(s.split("+")[1])
                        if is_x:
                            xmax = max(xmax, v)
                        else:
                            ymax = max(ymax, v)
                    elif s.startswith("?") and "-" in s:
                        v = int(s.split("-")[1])
                        if is_x:
                            xmin = max(xmin, v)
                        else:
                            ymin = max(ymin, v)
            # 0-based less-than bounds
            lits.append(less_than(c, self.bg_x, self.W - xmax))
            lits.append(less_than(c, self.bg_y, self.H - ymax))
            if xmin > 0:
                lits.append(c.not_(less_than(c, self.bg_x, xmin)))
            if ymin > 0:
                lits.append(c.not_(less_than(c, self.bg_y, ymin)))
            for atom in shape:
                pair = [atom.x.replace(" ", ""), atom.y.replace(" ", "")]
                eq = self._pos_eq_pair(self.bg_x, self.bg_y, pair)
                sign = "neg" if atom.negated else "pos"
                lits.append(
                    self._if_then_pred(eq, atom.pred, self.depth, sign)
                )
            body = c.and_(*lits)
            if len(self._black_goal_atoms) > 1:
                shape_ok.append(c.and_(self._bin(self.bg_choice, gi), body))
            else:
                shape_ok.append(body)
        goal = c.or_(*shape_ok) if shape_ok else c.const_false()
        n = len(self._black_goal_atoms)
        if n > 1 and (1 << nbits(n)) != n:
            goal = c.and_(goal, less_than(c, self.bg_choice, n))
        return goal

    def _white_goal_block(self) -> int:
        """
        White has *not* completed any goal shape (maker–maker early-stop).

        For every grounded placement S of every white shape, some cell of S
        is not white.  Encoded as ∃ hole-index (allocated in ``_alloc``)
        then under ∀cell: ``(cell = S[hole]) → ¬white``.
        """
        c = self.c
        if not self._white_goal_atoms:
            return c.const_true()

        parts: list[int] = []
        hole_i = 0
        not_white = c.not_(
            c.and_(self.pred[self.depth][0], self.pred[self.depth][1])
        )
        for shape in self._white_goal_atoms:
            for ax in range(1, self.W + 1):
                for ay in range(1, self.H + 1):
                    wshape = [
                        Atom("black", a.x, a.y, a.negated)
                        if a.pred == "white"
                        else a
                        for a in shape
                    ]
                    cells = eval_goal_shape(wshape, ax, ay, self.W, self.H)
                    if not cells:
                        continue
                    bits = self._white_hole_vars[hole_i]
                    hole_i += 1
                    n = len(cells)
                    # ∃ hole i.  ∀cell.  (cell = S[i] → ¬white)
                    # Prenex: for each i, (choice=i ∧ cell=S[i]) → ¬white
                    for i, (x, y, _neg) in enumerate(cells):
                        ch = c.const_true() if n == 1 else self._bin(bits, i)
                        at = c.and_(
                            equals_value(c, self.fx, x - 1),
                            equals_value(c, self.fy, y - 1),
                        )
                        parts.append(
                            c.implies(c.and_(ch, at), not_white)
                        )
                    if n > 1 and (1 << nbits(n)) != n:
                        parts.append(less_than(c, bits, n))
        return c.and_(*parts) if parts else c.const_true()

    def _white_valid(self, t: int) -> int:
        """bound_bit ∧ precondition bits (legacy valid move)."""
        m = self.move[t]
        return self.c.and_(m[3][0], *m[4])

    def _nested_final(self, transitions: list[int], initial: int, black_goal: int, white_goal: int) -> int:
        c = self.c
        # start: last transition ∧ black_goal
        cur = c.and_(transitions[-1], black_goal)
        for i in range(self.depth - 1):
            rev = self.depth - i - 2
            if rev % 2 == 1:
                # white
                valid = self._white_valid(rev)
                if self.maker_maker:
                    # Legacy maker–maker (generate_final_gate):
                    #   (valid ∧ ¬wstop) ⇒ continue (need rest of nest / black win)
                    #   (valid ∧ wstop)  ⇒ freeze board ∧ white_goal
                    # wstop is universal; black's later moves are ∃ *after* this
                    # ∀ block, so they may depend on wstop (different b2 for
                    # stop vs continue).  Do **not** put black_goal in the
                    # stop branch — that freezes the board before Black's
                    # remaining plies and makes short SAT instances UNSAT.
                    wstop = self.move[rev][5][0]
                    prop = equals_vars(
                        c, self.pred[rev + 1], self.pred[self.depth]
                    )
                    cont = c.implies(c.and_(valid, -wstop), cur)
                    stop_ok = c.implies(
                        c.and_(valid, wstop),
                        c.and_(prop, white_goal),
                    )
                    cur = c.and_(transitions[rev], cont, stop_ok)
                else:
                    # Maker–breaker: valid ⇒ rest; ¬valid (stuck) ⇒ Black wins.
                    cur = c.and_(transitions[rev], c.implies(valid, cur))
            else:
                # black: or(stop, cur); stop → prop ∧ black_goal
                stop = self.move[rev][3][0]
                cont = c.or_(stop, cur)
                prop = equals_vars(c, self.pred[rev + 1], self.pred[self.depth])
                stop_ok = c.implies(stop, c.and_(prop, black_goal))
                cur = c.and_(transitions[rev], cont, stop_ok)
        return c.and_(initial, cur)

    def _build(self) -> None:
        D = self.depth
        transitions: list[int] = []
        # first ply
        if self.black_first:
            transitions.append(self._black_transition(0))
        else:
            transitions.append(self._dummy_transition(0))
        for t in range(1, D - 1):
            if t % 2 == 0:
                transitions.append(self._black_transition(t))
            else:
                transitions.append(self._white_transition(t))
        if self.last_turn_black:
            transitions.append(self._black_transition(D - 1))
        else:
            transitions.append(self._dummy_transition(D - 1))

        initial = self._initial()
        black_goal = self._black_goal()
        white_goal = self._white_goal_block() if self.maker_maker else self.c.const_true()
        out = self._nested_final(transitions, initial, black_goal, white_goal)
        self.c.set_output(out)

    def to_qcir(self) -> str:
        return self.c.to_qcir()


def encode_bwnib(domain: GridDomain, problem: GridProblem) -> str:
    return BwnibEncoder(domain, problem).to_qcir()
