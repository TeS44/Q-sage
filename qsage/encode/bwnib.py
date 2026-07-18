"""
bwnib encoding (arXiv:2303.16949) — official Q-sage entry point.

Implementation: ``qsage.encode.paper`` (self-contained, no ``legacy/`` imports).
QCIR matches paper goldens under ``Benchmarks/SAT2023_GDDL/QBF_instances/``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from qsage.encode.normalize import normalize_qcir
from qsage.encode.paper.bwnib_enc import BlackWhiteNestedIndexBased
from qsage.encode.paper.parse.parser import Parse
from qsage.encode.paper.qcir_io import encoding_to_qcir

_REPO = Path(__file__).resolve().parents[2]


def _args(domain: Path, problem: Path, work: Path) -> SimpleNamespace:
    return SimpleNamespace(
        ib_domain=str(domain),
        ib_problem=str(problem),
        problem=str(work / "combined_input.ig"),
        e="bwnib",
        game_type="general",
        encoding_format=1,
        encoding_out=str(work / "out.qcir"),
        intermediate_encoding_out=str(work / "intermediate.qcir"),
        planner_path=str(_REPO),
        depth=3,
        xmax=4,
        ymax=4,
        ignore_file_depth=0,
        ignore_file_boardsize=0,
        debug=-1,
        run=0,
        sort_internal_gates=0,
        force_black_player_stop=0,
        force_white_player_stop=0,
        viz_meta_data_out=str(work / "viz_meta"),
        remove_unreachable_nodes=0,
        renumber_positions=0,
        tight_neighbour_pruning=0,
        goal_length=3,
        preprocessing=0,
        certificate_out=str(work / "cert"),
        solver=2,
        solver_out=str(work / "solver_out"),
        qcir_viz=0,
        viz_testing=0,
        seed=0,
        run_tests=0,
        version=False,
    )


def encode_bwnib(domain: str | Path, problem: str | Path) -> str:
    """
    Return QCIR for the black–white nested index-based encoding.

    domain/problem: BDDL ``.ig`` paths.
    """
    domain = Path(domain).resolve()
    problem = Path(problem).resolve()
    if not domain.is_file():
        raise FileNotFoundError(domain)
    if not problem.is_file():
        raise FileNotFoundError(problem)

    prev = Path.cwd()
    try:
        os.chdir(_REPO)
        with tempfile.TemporaryDirectory(prefix="qsage_bwnib_") as td:
            work = Path(td)
            args = _args(domain, problem, work)
            parsed = Parse(args)
            if getattr(parsed, "unsolvable", 0) == 1:
                raise RuntimeError("instance marked unsolvable by parser")
            enc = BlackWhiteNestedIndexBased(parsed)
            return encoding_to_qcir(
                enc.quantifier_block,
                enc.encoding,
                enc.final_output_gate,
            )
    finally:
        os.chdir(prev)


def encode_bwnib_normalized(domain: str | Path, problem: str | Path) -> str:
    """QCIR after normalize_qcir (for tests)."""
    return normalize_qcir(encode_bwnib(domain, problem))
