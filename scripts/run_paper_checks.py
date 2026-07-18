#!/usr/bin/env python3
"""Run Bloqqer+CAQE (and QuBi if available) on paper Table 2 sample instances."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# repo root on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qsage.solve.bloqqer_caqe import solve_qcir_bloqqer_caqe
from qsage.solve.paper_checks import paper_cases
from qsage.solve.qubi import qubi_available, solve_qcir_qubi
from qsage.solve.result import Status


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--backend", choices=("bloqqer+caqe", "qubi", "both"), default="both")
    ap.add_argument("--limit", type=int, default=0, help="max cases (0=all)")
    args = ap.parse_args()

    cases = paper_cases()
    if args.limit:
        cases = cases[: args.limit]

    print(f"paper cases: {len(cases)}")
    print(f"qubi binary: {qubi_available()}")
    ok = fail = skip = 0

    for case in cases:
        qcir = case.golden_qcir.read_text(encoding="utf-8")
        print(f"\n=== {case.name}  expect={case.expect} ===")
        print(f"    {case.paper_note}")

        backends = []
        if args.backend in ("bloqqer+caqe", "both"):
            backends.append("bloqqer+caqe")
        if args.backend in ("qubi", "both"):
            backends.append("qubi")

        for be in backends:
            if be == "bloqqer+caqe":
                res = solve_qcir_bloqqer_caqe(qcir, timeout=args.timeout)
            else:
                if not qubi_available():
                    print(f"  qubi: SKIP (not built)")
                    skip += 1
                    continue
                res = solve_qcir_qubi(qcir, timeout=args.timeout)

            match = res.status.value == case.expect
            mark = "OK" if match else "MISMATCH"
            if res.status in (Status.ERROR, Status.TIMEOUT, Status.UNKNOWN):
                mark = res.status.value
                fail += 1
            elif match:
                ok += 1
            else:
                fail += 1
            print(
                f"  {be:14} {res.status.value:8} {res.seconds:6.2f}s  [{mark}]  {res.message}"
            )

    print(f"\nsummary: ok={ok} fail={fail} skip={skip}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
