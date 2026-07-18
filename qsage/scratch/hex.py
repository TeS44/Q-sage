"""
Path-based Hex (``pg`` / LN — arXiv:2301.07345).

From-scratch package under ``qsage.scratch.paper`` (no ``legacy/`` imports).
QCIR matches paper goldens / previous ``encode_positional(..., "pg")``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from qsage.scratch.paper.parse.parser import Parse
from qsage.scratch.paper.path_based import PathBasedGoal
from qsage.scratch.paper.qcir_io import encoding_to_qcir

_REPO = Path(__file__).resolve().parents[2]


def _args(problem: Path, work: Path) -> SimpleNamespace:
    """Flags expected by the paper Hex parser/encoder (same defaults as previous)."""
    return SimpleNamespace(
        version=False,
        ib_domain="testcases/index_separate_inputs/domain.ig",
        ib_problem="testcases/index_separate_inputs/problem.ig",
        problem=str(problem),
        planner_path=str(_REPO),
        depth=3,
        xmax=4,
        ymax=4,
        ignore_file_depth=0,
        ignore_file_boardsize=0,
        e="pg",
        game_type="hex",
        goal_length=3,
        run=0,
        encoding_format=1,
        encoding_out=str(work / "pos_pg.qcir"),
        intermediate_encoding_out=str(work / "pos_pg.inter.qcir"),
        certificate_out=str(work / "certificate"),
        solver=2,
        solver_out=str(work / "solver_output"),
        debug=-1,
        run_tests=0,
        qcir_viz=0,
        viz_testing=0,
        viz_meta_data_out=str(work / "viz_meta_out"),
        seed=0,
        renumber_positions=0,
        restricted_position_constraints=0,
        black_move_restrictions=1,
        black_overwriting_black_enable=1,
        forall_move_restrictions="none",
        remove_unreachable_nodes=0,
        tight_neighbour_pruning=0,
        tight_neighbours_with_distances=0,
        force_black_player_stop=0,
        force_white_player_stop=0,
        force_white_player_invalid_or_stop=0,
        sort_internal_gates=0,
        preprocessing=2,
        preprocessed_encoding_out=str(work / "preprocessed_encoding"),
        time_limit=1800,
        preprocessing_time_limit=900,
    )


def encode_hex_file(path: str | Path) -> str:
    """Return paper ``pg`` QCIR for a ``.pg`` board (gate-identical to previous)."""
    problem = Path(path).resolve()
    if not problem.is_file():
        raise FileNotFoundError(problem)

    prev = Path.cwd()
    try:
        os.chdir(_REPO)
        with tempfile.TemporaryDirectory(prefix="qsage_scratch_hex_") as td:
            work = Path(td)
            args = _args(problem, work)
            parsed = Parse(args)
            if getattr(parsed, "unsolvable", 0) == 1:
                raise RuntimeError("instance marked unsolvable")
            enc = PathBasedGoal(parsed)
            return encoding_to_qcir(
                enc.quantifier_block,
                enc.encoding,
                enc.final_output_gate,
            )
    finally:
        os.chdir(prev)
