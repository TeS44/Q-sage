"""Map golden QCIR paths under QBF_instances/ to BDDL domain+problem files."""

from __future__ import annotations

from pathlib import Path

# Short folder name in QBF_instances → GDDL_models subdir
_FOLDER = {
    "httt": "httt",
    "B": "breakthrough",
    "BSP": "breakthrough-second-player",
    "C4": "connect-c",
    "D": "domineering",
    "EP": "evader_pursuer",
    "EP-dual": "evader_pursuer_dual",
    "hex": "hex",
}

_REPO = Path(__file__).resolve().parents[2]
_GOLDEN_ROOT = _REPO / "Benchmarks" / "SAT2023_GDDL" / "QBF_instances"
_MODEL_ROOT = _REPO / "Benchmarks" / "SAT2023_GDDL" / "GDDL_models"


def iter_bwnib_goldens() -> list[tuple[Path, Path, Path]]:
    """
    Yield (golden_qcir, domain_ig, problem_file) for every *_bwnib.qcir.
    """
    out: list[tuple[Path, Path, Path]] = []
    for golden in sorted(_GOLDEN_ROOT.rglob("*_bwnib.qcir")):
        folder = golden.parent.name  # e.g. httt, B, hex
        if folder not in _FOLDER:
            continue
        model_dir = _MODEL_ROOT / _FOLDER[folder]
        domain = model_dir / "domain.ig"
        stem = golden.name[: -len("_bwnib.qcir")]  # e.g. 3x3_3_domino
        # problem may be .ig or .pg
        problem = model_dir / f"{stem}.ig"
        if not problem.is_file():
            problem = model_dir / f"{stem}.pg"
        out.append((golden, domain, problem))
    return out
