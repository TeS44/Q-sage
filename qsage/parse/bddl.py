"""Parse BDDL domain/problem files (.ig) with a Lark grammar."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from lark import Transformer, v_args
from lark.exceptions import LarkError

from qsage.parse.ast_nodes import (
    Action,
    Condition,
    Domain,
    Expr,
    Predicate,
    Problem,
    SubCondition,
)
from qsage.parse.util import load_text, make_lark, strip_comments

_GRAMMAR = Path(__file__).parent / "grammars" / "bddl.lark"
_parser = None


def _parser_cached():
    global _parser
    if _parser is None:
        _parser = make_lark(_GRAMMAR)
    return _parser


class ParseError(ValueError):
    pass


@v_args(inline=True)
class _ToAst(Transformer):
    """Turn Lark trees into dataclasses in ast_nodes."""

    def INT(self, t):
        return int(t)

    def NAME(self, t):
        return str(t)

    def PRED(self, t):
        return Predicate(str(t))

    def PARAM(self, t):
        return str(t)[1:]  # "?x" -> "x"

    def BOUND(self, t):
        return str(t)

    def OP(self, t):
        return str(t)

    def TURN_NAME(self, t):
        return str(t)

    def var_offset(self, name, op, n):
        return Expr.var(name, n if op == "+" else -n)

    def var_plain(self, name):
        return Expr.var(name, 0)

    def bound_name(self, name):
        return Expr.bound(name)

    def const_int(self, n):
        return Expr.const(n)

    def atom(self, pred, x, y):
        return SubCondition(pred, x, y, negated=False)

    def pos_atom(self, atom):
        return atom

    def not_atom(self, atom):
        return SubCondition(atom.predicate, atom.x, atom.y, negated=True)

    def not_atom_paren(self, atom):
        return self.not_atom(atom)

    def condition(self, *subs):
        return tuple(subs)

    def param_list(self, a, b):
        return (a, b)

    def action(self, name, params, pre, eff):
        return Action(name, params, pre, eff)

    def black_actions_section(self, *actions):
        return tuple(actions)

    def white_actions_section(self, *actions):
        return tuple(actions)

    def domain(self, black, white):
        return Domain(black, white)

    def init_atom(self, pred, x, y):
        return (pred, x, y)

    def boardsize_section(self, w, h):
        return (w, h)

    def init_section(self, *atoms):
        return atoms

    def depth_section(self, d):
        return d

    def goal_line(self, *subs):
        return tuple(subs)

    def false_goal(self):
        return ()  # "False" means no goals

    def goal_lines(self, *lines):
        return tuple(lines)

    def goal_content(self, content):
        return content

    def black_goals(self, content):
        return content

    def white_goals(self, content):
        return content

    def goals_section(self, black, white):
        return (black, white)

    def blackturn_section(self, name):
        return name

    def problem(self, *parts):
        board, init, depth, goals = parts[:4]
        black_turn = parts[4] if len(parts) > 4 else "first"
        width, height = board
        black_init, white_init = [], []
        for pred, x, y in init:
            if pred is Predicate.BLACK:
                black_init.append((x, y))
            elif pred is Predicate.WHITE:
                white_init.append((x, y))
        black_goals, white_goals = goals
        return Problem(
            width=width,
            height=height,
            depth=depth,
            black_init=tuple(black_init),
            white_init=tuple(white_init),
            black_goals=black_goals,
            white_goals=white_goals,
            black_turn=black_turn,
        )

    def start(self, item):
        return item


def _parse(text: str):
    return _ToAst().transform(_parser_cached().parse(strip_comments(text)))


def parse_domain(source: str | Path) -> Domain:
    text, path = load_text(source)
    try:
        result = _parse(text)
    except LarkError as e:
        raise ParseError(f"domain parse failed ({path}): {e}") from e
    if not isinstance(result, Domain):
        raise ParseError(f"expected a domain file, got {type(result).__name__}")
    return replace(result, source=path) if path else result


def parse_problem(source: str | Path) -> Problem:
    text, path = load_text(source)
    try:
        result = _parse(text)
    except LarkError as e:
        raise ParseError(f"problem parse failed ({path}): {e}") from e
    if not isinstance(result, Problem):
        raise ParseError(f"expected a problem file, got {type(result).__name__}")
    return replace(result, source=path) if path else result


def parse_bddl(domain: str | Path, problem: str | Path) -> tuple[Domain, Problem]:
    return parse_domain(domain), parse_problem(problem)
