#!/usr/bin/env python3
"""
Solve positional Hex goldens with QuBi and report SAT/UNSAT.

Paper (arXiv:2301.07345) evaluates Hein Hex puzzles with lifted encodings
(LN≈pg/ibign, SN≈cp). We record solver answers for the depth in each .pg file
(filename suffix -DD is the depth bound).

Small instances are expected to finish quickly; larger boards may timeout.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qsage.solve.qubi import qubi_available, solve_qcir_qubi
from qsage.solve.result import Status

# Representative Hein set used in paper discussions (small + medium)
DEFAULT_STEMS = [
    "hein_04_3x3-03",
    "hein_04_3x3-05",
    "hein_09_4x4-05",
    "hein_09_4x4-07",
    "hein_12_4x4-05",
    "hein_12_4x4-07",
    "hein_07_4x4-07",
    "hein_06_4x4-11",
    "browne_5x5_07",
]


def depth_from_stem(stem: str) -> int | None:
    m = re.search(r"-(\d+)$", stem)
    return int(m.group(1)) if m else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--encoding", default="pg", choices=("pg", "cp", "ibign", "all"))
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--all-boards", action="store_true", help="all B-Hex boards")
    args = ap.parse_args()

    if not qubi_available():
        print("QuBi not built; run bash scripts/build_qubi_macos.sh", file=sys.stderr)
        return 2

    encs = ("pg", "cp", "ibign") if args.encoding == "all" else (args.encoding,)
    gold_root = ROOT / "Benchmarks" / "positional_goldens"

    stems = (
        [p.stem for p in sorted((ROOT / "Benchmarks" / "B-Hex").glob("*.pg"))]
        if args.all_boards
        else DEFAULT_STEMS
    )

    print(f"{'instance':40} {'enc':6} {'depth':5} {'result':8} time")
    print("-" * 72)
    rows = []
    for enc in encs:
        for stem in stems:
            q = gold_root / enc / f"{stem}_{enc}.qcir"
            if not q.is_file():
                print(f"{stem:40} {enc:6} {'?':5} MISSING")
                continue
            d = depth_from_stem(stem)
            res = solve_qcir_qubi(q.read_text(encoding="utf-8"), timeout=args.timeout)
            mark = res.status.value
            if res.status is Status.TIMEOUT:
                mark = "TIMEOUT"
            print(
                f"{stem:40} {enc:6} {str(d or '-'):5} {mark:8} {res.seconds:6.2f}s"
            )
            rows.append((stem, enc, d, mark, res.seconds))

    sat = sum(1 for r in rows if r[3] == "SAT")
    unsat = sum(1 for r in rows if r[3] == "UNSAT")
    other = len(rows) - sat - unsat
    print(f"\nsummary: sat={sat} unsat={unsat} other={other} total={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
