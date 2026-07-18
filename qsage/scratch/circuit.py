"""
Tiny QCIR builder (stdlib only).

Important: in QCIR, **variable ids and gate ids share one number space**.
Allocate every variable with ``fresh()`` *before* the first gate; then only
build gates. ``const_true`` / ``const_false`` reserve padding vars first.
"""

from __future__ import annotations


class Circuit:
    def __init__(self) -> None:
        self._next = 1
        self.prefix: list[tuple[str, list[int]]] = []
        self.gates: dict[int, tuple[str, list[int]]] = {}
        self._next_gate: int | None = None
        self.output: int | None = None
        self._pad: list[int] | None = None
        self._true: int | None = None
        self._false: int | None = None
        self._frozen = False  # True after first gate

    def fresh(self, n: int = 1) -> list[int]:
        if self._frozen:
            raise RuntimeError(
                "Circuit.fresh() after gates started — allocate all vars first"
            )
        ids = list(range(self._next, self._next + n))
        self._next += n
        return ids

    def exists(self, vs: list[int]) -> None:
        if vs:
            self.prefix.append(("exists", list(vs)))

    def forall(self, vs: list[int]) -> None:
        if vs:
            self.prefix.append(("forall", list(vs)))

    def _reserve_pad(self) -> None:
        """Two existential padding vars for ⊤/⊥ (must run before other gates)."""
        if self._pad is not None:
            return
        if self._frozen:
            raise RuntimeError("const_true/false need pad vars before gates")
        self._pad = self.fresh(2)
        self.exists(list(self._pad))

    def _gid(self) -> int:
        if self._next_gate is None:
            self._next_gate = self._next
            self._frozen = True
        g = self._next_gate
        self._next_gate += 1
        return g

    def and_(self, *lits: int) -> int:
        xs = [x for x in lits if x is not None]
        if not xs:
            return self.const_true()
        if len(xs) == 1:
            return xs[0]
        g = self._gid()
        self.gates[g] = ("and", list(xs))
        return g

    def or_(self, *lits: int) -> int:
        xs = [x for x in lits if x is not None]
        if not xs:
            return self.const_false()
        if len(xs) == 1:
            return xs[0]
        g = self._gid()
        self.gates[g] = ("or", list(xs))
        return g

    def not_(self, lit: int) -> int:
        return -lit

    def implies(self, a: int, b: int) -> int:
        return self.or_(self.not_(a), b)

    def iff(self, a: int, b: int) -> int:
        return self.and_(self.implies(a, b), self.implies(b, a))

    def const_true(self) -> int:
        self._reserve_pad()
        assert self._pad is not None
        if self._true is None:
            v = self._pad[0]
            self._true = self.or_(v, -v)
        return self._true

    def const_false(self) -> int:
        self._reserve_pad()
        assert self._pad is not None
        if self._false is None:
            v = self._pad[1]
            self._false = self.and_(v, -v)
        return self._false

    def at_most_one(self, vs: list[int]) -> int:
        if len(vs) <= 1:
            return self.const_true()
        parts = [self.or_(-vs[i], -vs[j]) for i in range(len(vs)) for j in range(i + 1, len(vs))]
        return self.and_(*parts)

    def exactly_one(self, vs: list[int]) -> int:
        if not vs:
            return self.const_false()
        if len(vs) == 1:
            return vs[0]
        return self.and_(self.or_(*vs), self.at_most_one(vs))

    def set_output(self, lit: int) -> None:
        self.output = lit

    def to_qcir(self) -> str:
        if self.output is None:
            raise RuntimeError("output not set")
        lines = ["#QCIR-G14", "# qsage.scratch standalone encoder"]
        for kind, vs in self.prefix:
            lines.append(f"{kind}({', '.join(map(str, vs))})")
        lines.append(f"output({self.output})")
        for g in sorted(self.gates):
            op, ins = self.gates[g]
            lines.append(f"{g} = {op}({', '.join(map(str, ins))})")
        return "\n".join(lines) + "\n"
