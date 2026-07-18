"""Parse positional / Hex .pg files with a Lark grammar."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from lark import Transformer, v_args
from lark.exceptions import LarkError

from qsage.parse.ast_nodes import PositionalGame
from qsage.parse.util import load_text, make_lark, strip_comments

_GRAMMAR = Path(__file__).parent / "grammars" / "positional.lark"
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
    def POS(self, t):
        return str(t)

    def TIME(self, t):
        return str(t)

    def pos_id(self, p):
        return p

    def time_id(self, t):
        return t

    def id_line(self, *ids):
        return tuple(ids)

    def time_line(self, *ids):
        return tuple(ids)

    def neigh_line(self, first, *rest):
        return (first, tuple(rest))

    def id_block(self, *lines):
        return tuple(p for line in lines for p in line)

    def time_block(self, *lines):
        return tuple(t for line in lines for t in line)

    def win_block(self, *lines):
        return tuple(lines)

    def neigh_block(self, *lines):
        return dict(lines)

    def black_initials(self, ids):
        return ("black_initials", ids)

    def white_initials(self, ids):
        return ("white_initials", ids)

    def times(self, ids):
        return ("times", ids)

    def black_turns(self, ids):
        return ("black_turns", ids)

    def positions(self, ids):
        return ("positions", ids)

    def black_wins(self, lines):
        return ("black_wins", lines)

    def neighbours(self, graph):
        return ("neighbours", graph)

    def start_border(self, ids):
        return ("start_border", ids)

    def end_border(self, ids):
        return ("end_border", ids)

    def section(self, item):
        return item

    def positional(self, *sections):
        fields = {
            "positions": (),
            "black_initials": (),
            "white_initials": (),
            "times": (),
            "black_turns": (),
            "neighbours": {},
            "start_border": (),
            "end_border": (),
            "black_wins": (),
        }
        for key, value in sections:
            fields[key] = value
        return PositionalGame(**fields)

    def start(self, game):
        return game


def parse_pg(source: str | Path) -> PositionalGame:
    text, path = load_text(source)
    try:
        game = _ToAst().transform(_parser_cached().parse(strip_comments(text)))
    except LarkError as e:
        raise ParseError(f".pg parse failed ({path}): {e}") from e
    return replace(game, source=path) if path else game
