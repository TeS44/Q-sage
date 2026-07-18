"""
Paper checks against SAT 2023 grid paper Table 2 (arXiv:2303.16949, main.tex).

Convention (paper §5):
  - \\textbf{depth}: winning strategy exists → solver SAT at that depth
  - plain depth: no winning strategy; depth bound complete → UNSAT
  - \\textit{depth}: only max refuted (incomplete) — we skip or note loosely
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_GOLD = _REPO / "Benchmarks" / "SAT2023_GDDL" / "QBF_instances"
_MODELS = _REPO / "Benchmarks" / "SAT2023_GDDL" / "GDDL_models"


@dataclass(frozen=True)
class PaperCase:
    name: str
    golden_qcir: Path
    expect: str  # "SAT" or "UNSAT"
    paper_note: str


def _case(folder: str, stem: str, expect: str, note: str) -> PaperCase | None:
    q = _GOLD / folder / f"{stem}_bwnib.qcir"
    if not q.is_file():
        return None
    return PaperCase(name=f"{folder}/{stem}", golden_qcir=q, expect=expect, paper_note=note)


def paper_cases() -> list[PaperCase]:
    """Table 2 samples where bold/plain is clear in the LaTeX source."""
    raw: list[PaperCase | None] = [
        # (a) HTTT 3x3: D E Ey F K S T Tp
        # \textbf{3} \textbf{5} 9 9 9 - 9 \textbf{9}
        _case("httt", "3x3_3_domino", "SAT", "Table 2(a) Domino 3x3 bold 3 → win"),
        _case("httt", "3x3_5_el", "SAT", "Table 2(a) El 3x3 bold 5 → win"),
        _case("httt", "3x3_9_tippy", "SAT", "Table 2(a) Tippy 3x3 bold 9 → win"),
        _case("httt", "3x3_9_tic", "UNSAT", "Table 2(a) Tic 3x3 plain 9 → no win (complete)"),
        _case("httt", "3x3_9_fatty", "UNSAT", "Table 2(a) Fatty 3x3 plain 9 → no win"),
        _case("httt", "3x3_9_knobby", "UNSAT", "Table 2(a) Knobby 3x3 plain 9 → no win"),
        _case("httt", "3x3_9_elly", "UNSAT", "Table 2(a) Elly 3x3 plain 9 → no win"),
        # (b) Breakthrough first player: 2×4 plain 13, 2×6 bold 15
        _case("B", "2x4_13", "UNSAT", "Table 2(b) Breakthrough 2x4 first player plain 13"),
        _case("B", "2x6_15", "SAT", "Table 2(b) Breakthrough 2x6 first player bold 15"),
        # second player: 2×4 bold 8, 2×5 bold 10
        _case("BSP", "2x4_8", "SAT", "Table 2(b) Breakthrough-SP 2x4 bold 8"),
        _case("BSP", "2x5_10", "SAT", "Table 2(b) Breakthrough-SP 2x5 bold 10"),
        # (c) Connect-2: 2x2 and 3x3 bold 3
        _case("C4", "2x2_3_connect2", "SAT", "Table 2(c) Connect-2 2x2 bold 3"),
        _case("C4", "3x3_3_connect2", "SAT", "Table 2(c) Connect-2 3x3 bold 3"),
        # (d) Domineering 2x2 bold 2, 2x3 bold 2 (file may be deeper)
        _case("D", "2x2_2", "SAT", "Table 2(d) Domineering 2x2 bold 2"),
        # Hex Hein (suite; hein_04_3x3-05 is a standard small win puzzle)
        _case("hex", "hein_04_3x3-05", "SAT", "Hex Hein suite (small win puzzle)"),
    ]
    return [c for c in raw if c is not None]
