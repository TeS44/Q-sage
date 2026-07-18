"""Parse every BDDL domain/problem under Benchmarks/SAT2023_GDDL."""

from __future__ import annotations

from pathlib import Path

import pytest

from qsage.parse.ast_nodes import Predicate
from qsage.parse.bddl import ParseError, parse_domain, parse_problem

REPO = Path(__file__).resolve().parents[2]
GDDL = REPO / "Benchmarks" / "SAT2023_GDDL" / "GDDL_models"


def domain_files():
    return sorted(GDDL.rglob("domain.ig"))


def problem_files():
    files = [p for p in GDDL.rglob("*.ig") if p.name != "domain.ig"]
    # Some hex instances are BDDL problems with a .pg suffix.
    for p in (GDDL / "hex").glob("*.pg"):
        if "#boardsize" in p.read_text(encoding="utf-8", errors="ignore"):
            files.append(p)
    return sorted(files)


@pytest.mark.parametrize("path", domain_files(), ids=lambda p: str(p.relative_to(REPO)))
def test_domain(path: Path) -> None:
    domain = parse_domain(path)
    assert domain.black_actions and domain.white_actions
    for action in (*domain.black_actions, *domain.white_actions):
        assert action.parameters == ("x", "y")
        assert action.precondition and action.effect


@pytest.mark.parametrize("path", problem_files(), ids=lambda p: str(p.relative_to(REPO)))
def test_problem(path: Path) -> None:
    problem = parse_problem(path)
    assert problem.width >= 1 and problem.height >= 1 and problem.depth >= 1


def test_breakthrough_not() -> None:
    domain = parse_domain(GDDL / "breakthrough" / "domain.ig")
    assert [a.name for a in domain.black_actions] == [
        "forward",
        "left-diagonal",
        "right-diagonal",
    ]
    assert any(s.negated for s in domain.black_actions[1].precondition)


def test_connect_c_nested_not() -> None:
    pre = parse_domain(GDDL / "connect-c" / "domain.ig").black_actions[0].precondition
    assert len(pre) == 2
    assert pre[1].negated and pre[1].predicate is Predicate.OPEN


def test_whitespace_ok() -> None:
    text = """
    #boardsize
    2   3
    #init
    black(1,1)   white(2,3)
    #depth
    5
    #blackgoal
    black(?x,ymin)
    #whitegoal
    white(?x,ymax)
    """
    p = parse_problem(text)
    assert p.width == 2 and p.height == 3
    assert p.black_init == ((1, 1),) and p.white_init == ((2, 3),)


def test_bad_input() -> None:
    with pytest.raises(ParseError):
        parse_problem("#boardsize\nnope\n")
