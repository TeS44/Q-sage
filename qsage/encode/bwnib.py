"""
bwnib encoding entry point.

Currently reuses the proven legacy encoder so output matches paper goldens.
Students can replace the body with a clean rewrite; tests pin the QCIR shape.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from qsage.encode.normalize import normalize_qcir
from qsage.encode.qcir_io import encoding_to_qcir

# Repo root (…/Q-sage), so legacy imports resolve.
_REPO = Path(__file__).resolve().parents[2]


def _legacy_args(domain: Path, problem: Path, work: Path) -> SimpleNamespace:
    """Namespace with the flags legacy Parse/bwnib expect."""
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
    Return QCIR text for the black–white nested index-based encoding.

    domain/problem: BDDL .ig paths (problem may be a BDDL-style .pg under hex/).
    """
    domain = Path(domain).resolve()
    problem = Path(problem).resolve()
    if not domain.is_file():
        raise FileNotFoundError(domain)
    if not problem.is_file():
        raise FileNotFoundError(problem)

    # Legacy modules import as top-level `parse`, `q_encodings`, `utils`.
    prev_cwd = Path.cwd()
    prev_path = list(os.sys.path)
    try:
        os.chdir(_REPO)
        if str(_REPO) not in os.sys.path:
            os.sys.path.insert(0, str(_REPO))

        from parse.parser import Parse  # type: ignore
        from q_encodings.encoder import generate_encoding  # type: ignore

        with tempfile.TemporaryDirectory(prefix="qsage_bwnib_") as td:
            work = Path(td)
            # Legacy Parse overwrites args.problem with a fixed relative path:
            # intermediate_files/combined_input.ig — keep that writable.
            inter = _REPO / "intermediate_files"
            inter.mkdir(exist_ok=True)
            args = _legacy_args(domain, problem, work)
            args.problem = str(inter / "combined_input.ig")

            parsed = Parse(args)
            if getattr(parsed, "unsolvable", 0) == 1:
                raise RuntimeError("instance marked unsolvable by legacy parser")

            encoding = generate_encoding(parsed)
            return encoding_to_qcir(
                encoding.quantifier_block,
                encoding.encoding,
                encoding.final_output_gate,
            )
    finally:
        os.chdir(prev_cwd)
        os.sys.path[:] = prev_path


def encode_bwnib_normalized(domain: str | Path, problem: str | Path) -> str:
    """QCIR after normalize_qcir (for tests)."""
    return normalize_qcir(encode_bwnib(domain, problem))
