"""
Positional Hex encodings (paper arXiv:2301.07345).

Reuses legacy encoders under `legacy/` so QCIR matches saved goldens.
Supported: pg (path-based / LN-family), cp (compact / SN-family), ibign (nested implicit).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

from qsage.encode.normalize import normalize_qcir
from qsage.encode.qcir_io import encoding_to_qcir

_REPO = Path(__file__).resolve().parents[2]
_LEGACY = _REPO / "legacy"

POSITIONAL_ENCODINGS = frozenset({"pg", "cp", "ibign"})


def _legacy_args(problem: Path, encoding: str, work: Path) -> SimpleNamespace:
    """Defaults mirror legacy/Q-sage.py argparse (hex positional encode)."""
    work_out = work / f"pos_{encoding}.qcir"
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
        e=encoding,
        game_type="hex",
        goal_length=3,
        run=0,
        encoding_format=1,
        encoding_out=str(work_out),
        intermediate_encoding_out=str(work / f"pos_{encoding}.inter.qcir"),
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


def encode_positional(problem: str | Path, encoding: str = "pg") -> str:
    """Return QCIR for a positional Hex `.pg` problem."""
    if encoding not in POSITIONAL_ENCODINGS:
        raise ValueError(
            f"unsupported positional encoding {encoding!r}; "
            f"choose from {sorted(POSITIONAL_ENCODINGS)}"
        )
    problem = Path(problem).resolve()
    if not problem.is_file():
        raise FileNotFoundError(problem)

    prev_cwd = Path.cwd()
    prev_path = list(sys.path)
    try:
        os.chdir(_REPO)
        sys.path.insert(0, str(_LEGACY))
        from parse.parser import Parse  # type: ignore
        from q_encodings.encoder import generate_encoding  # type: ignore

        with tempfile.TemporaryDirectory(prefix="qsage_pos_") as td:
            work = Path(td)
            args = _legacy_args(problem, encoding, work)
            parsed = Parse(args)
            if getattr(parsed, "unsolvable", 0) == 1:
                raise RuntimeError("instance marked unsolvable")
            encoding_obj = generate_encoding(parsed)
            return encoding_to_qcir(
                encoding_obj.quantifier_block,
                encoding_obj.encoding,
                encoding_obj.final_output_gate,
            )
    finally:
        os.chdir(prev_cwd)
        sys.path[:] = prev_path


def encode_positional_normalized(problem: str | Path, encoding: str = "pg") -> str:
    return normalize_qcir(encode_positional(problem, encoding))
