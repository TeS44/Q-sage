"""Parse positional Hex .pg files under Benchmarks/."""

from __future__ import annotations

from pathlib import Path

import pytest

from qsage.parse.positional import ParseError, parse_pg

REPO = Path(__file__).resolve().parents[2]


def is_positional(path: Path) -> bool:
    # GDDL hex/*.pg are BDDL problems, not positional boards.
    text = path.read_text(encoding="utf-8", errors="ignore")
    return "#positions" in text or "#neighbours" in text


def pg_files():
    return sorted(p for p in REPO.joinpath("Benchmarks").rglob("*.pg") if is_positional(p))


@pytest.mark.parametrize("path", pg_files(), ids=lambda p: str(p.relative_to(REPO)))
def test_pg(path: Path) -> None:
    game = parse_pg(path)
    assert game.positions and game.times
    assert game.depth == len(game.times)


def test_hein_sample() -> None:
    game = parse_pg(REPO / "Benchmarks" / "B-Hex" / "hein_04_3x3-05.pg")
    assert game.depth == 5
    assert game.neighbours["a1"]
    assert game.start_border and game.end_border


def test_whitespace_ok() -> None:
    text = """
    #blackinitials
    a1
    #whiteinitials
    b1
    #times
    t1 t2 t3
    #blackturns
    t1 t3
    #positions
    a1 a2 b1 b2
    #neighbours
    a1 b1 a2
    a2 a1 b2
    b1 a1 b2
    b2 a2 b1
    #startboarder
    a1 b1
    #endboarder
    a2 b2
    """
    game = parse_pg(text)
    assert game.black_initials == ("a1",) and game.depth == 3


def test_bad_input() -> None:
    with pytest.raises(ParseError):
        parse_pg("#positions\n!!!\n")
