"""
bwnib encoding entry point.

Reuses the proven encoder under `legacy/` so QCIR matches paper goldens.
Replace this body with a pure rewrite later; tests pin the QCIR shape.
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
        # solvers/ and tools/ live at repo root
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
    if not _LEGACY.is_dir():
        raise RuntimeError(f"legacy encoder tree not found: {_LEGACY}")

    prev_cwd = Path.cwd()
    prev_path = list(sys.path)
    try:
        # Imports: parse, q_encodings, utils  (from legacy/)
        # Data/solvers: Benchmarks, solvers, intermediate_files (from repo root)
        os.chdir(_REPO)
        sys.path.insert(0, str(_LEGACY))

        from parse.parser import Parse  # type: ignore
        from q_encodings.encoder import generate_encoding  # type: ignore

        with tempfile.TemporaryDirectory(prefix="qsage_bwnib_") as td:
            work = Path(td)
            args = _legacy_args(domain, problem, work)
            # Per-call work dir (safe under pytest-xdist); never share
            # intermediate_files/combined_input.ig across parallel workers.
            args.problem = str(work / "combined_input.ig")

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
        sys.path[:] = prev_path


def encode_bwnib_normalized(domain: str | Path, problem: str | Path) -> str:
    """QCIR after normalize_qcir (for tests)."""
    return normalize_qcir(encode_bwnib(domain, problem))
