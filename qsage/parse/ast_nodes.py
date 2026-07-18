"""AST types for BDDL (grid games) and positional / Hex games."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Predicate(str, Enum):
    OPEN = "open"
    BLACK = "black"
    WHITE = "white"


@dataclass(frozen=True)
class Expr:
    """Board coordinate: integer, xmin/xmax/ymin/ymax, or ?x/?y ± k."""

    kind: str  # "const" | "var" | "bound"
    name: str | None = None
    value: int | None = None
    offset: int = 0

    def __str__(self) -> str:
        if self.kind == "const":
            return str(self.value)
        if self.kind == "bound":
            return self.name or ""
        base = f"?{self.name}"
        if self.offset > 0:
            return f"{base}+{self.offset}"
        if self.offset < 0:
            return f"{base}{self.offset}"
        return base

    @staticmethod
    def const(n: int) -> Expr:
        return Expr(kind="const", value=n)

    @staticmethod
    def var(name: str, offset: int = 0) -> Expr:
        return Expr(kind="var", name=name, offset=offset)

    @staticmethod
    def bound(name: str) -> Expr:
        return Expr(kind="bound", name=name)


@dataclass(frozen=True)
class SubCondition:
    """One atom, e.g. black(?x,?y+1) or NOT(open(?x,?y))."""

    predicate: Predicate
    x: Expr
    y: Expr
    negated: bool = False

    def __str__(self) -> str:
        body = f"{self.predicate.value}({self.x},{self.y})"
        return f"NOT({body})" if self.negated else body


# Conjunction of atoms (one action precondition/effect, or one goal shape).
Condition = tuple[SubCondition, ...]


@dataclass(frozen=True)
class Action:
    name: str
    parameters: tuple[str, str]  # always ("x", "y") today
    precondition: Condition
    effect: Condition


@dataclass(frozen=True)
class Domain:
    black_actions: tuple[Action, ...]
    white_actions: tuple[Action, ...]
    source: str | None = None


@dataclass(frozen=True)
class Problem:
    width: int
    height: int
    depth: int
    black_init: tuple[tuple[int, int], ...] = ()
    white_init: tuple[tuple[int, int], ...] = ()
    black_goals: tuple[Condition, ...] = ()
    white_goals: tuple[Condition, ...] = ()
    # Legacy "#blackturn second" for second-player instances.
    black_turn: str = "first"
    source: str | None = None

    @property
    def xmin(self) -> int:
        return 1

    @property
    def ymin(self) -> int:
        return 1

    @property
    def xmax(self) -> int:
        return self.width

    @property
    def ymax(self) -> int:
        return self.height


@dataclass(frozen=True)
class PositionalGame:
    """Hex-style positional board from a .pg file."""

    positions: tuple[str, ...]
    black_initials: tuple[str, ...]
    white_initials: tuple[str, ...]
    times: tuple[str, ...]
    black_turns: tuple[str, ...]
    neighbours: dict[str, tuple[str, ...]] = field(default_factory=dict)
    start_border: tuple[str, ...] = ()
    end_border: tuple[str, ...] = ()
    black_wins: tuple[tuple[str, ...], ...] = ()
    source: str | None = None

    @property
    def depth(self) -> int:
        return len(self.times)
