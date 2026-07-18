#!/usr/bin/env python3
"""
Scan Hex + GDDL for instances QuBi solves within a hard timeout.

QuBi has no built-in clock; each call uses qsage.solve.qubi's process-group
kill. Default timeout 3s — safe for interactive play catalogs.

    python3 scripts/scan_playable_qbf.py
    python3 scripts/scan_playable_qbf.py --timeout 3 --out Benchmarks/playable_qbf.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeout", type=float, default=3.0, help="hard QuBi kill (s)")
    ap.add_argument(
        "--out",
        type=Path,
        default=_REPO / "Benchmarks" / "playable_qbf.json",
    )
    ap.add_argument("--max-per-game", type=int, default=0, help="0 = no cap")
    args = ap.parse_args()

    from qsage.encode.bwnib import encode_bwnib
    from qsage.encode.positional import encode_positional
    from qsage.solve.qubi import qubi_available, solve_qcir_qubi

    if not qubi_available():
        print("QuBi not available", file=sys.stderr)
        return 2

    timeout = float(args.timeout)
    out: list[dict] = []
    t_scan = time.perf_counter()

    gddl = _REPO / "Benchmarks" / "SAT2023_GDDL" / "GDDL_models"
    for game_dir in sorted(gddl.iterdir()):
        if not game_dir.is_dir() or game_dir.name == "hex":
            continue
        domain = game_dir / "domain.ig"
        if not domain.is_file():
            continue
        n_game = 0
        for prob in sorted(game_dir.glob("*.ig")):
            if prob.name == "domain.ig":
                continue
            if args.max_per_game and n_game >= args.max_per_game:
                break
            rel = str(prob.relative_to(_REPO))
            try:
                t0 = time.perf_counter()
                qcir = encode_bwnib(domain, prob)
                enc_t = time.perf_counter() - t0
                # also bound encode phase: skip huge encodes that already took > timeout
                if enc_t > timeout * 2:
                    print(f"SKIP encode-slow {rel} ({enc_t:.1f}s)")
                    continue
                res = solve_qcir_qubi(qcir, timeout=timeout)
            except Exception as e:
                print(f"ERR {rel}: {e}")
                continue
            if res.status.value not in ("SAT", "UNSAT"):
                print(f"  {rel}: {res.status.value} ({res.seconds:.2f}s)")
                continue
            entry = {
                "game": game_dir.name,
                "kind": "grid",
                "path": rel,
                "domain": str(domain.relative_to(_REPO)),
                "label": f"{game_dir.name}/{prob.name}",
                "status": res.status.value,
                "seconds": round(res.seconds, 3),
                "encode_seconds": round(enc_t, 3),
            }
            out.append(entry)
            n_game += 1
            print(f"OK {rel}: {res.status.value} {res.seconds:.2f}s")

    for folder, game in (
        (_REPO / "Benchmarks" / "B-Hex", "hex"),
        (gddl / "hex", "hex-gddl"),
    ):
        if not folder.is_dir():
            continue
        n_game = 0
        for p in sorted(folder.glob("*.pg")):
            if args.max_per_game and n_game >= args.max_per_game:
                break
            rel = str(p.relative_to(_REPO))
            try:
                t0 = time.perf_counter()
                qcir = encode_positional(p, "pg")
                enc_t = time.perf_counter() - t0
                res = solve_qcir_qubi(qcir, timeout=timeout)
            except Exception as e:
                print(f"ERR hex {rel}: {e}")
                continue
            if res.status.value not in ("SAT", "UNSAT"):
                print(f"  hex {rel}: {res.status.value} ({res.seconds:.2f}s)")
                continue
            out.append(
                {
                    "game": game,
                    "kind": "hex",
                    "path": rel,
                    "label": p.name if game == "hex" else f"gddl-hex/{p.name}",
                    "status": res.status.value,
                    "seconds": round(res.seconds, 3),
                    "encode_seconds": round(enc_t, 3),
                    "encoding": "pg",
                }
            )
            n_game += 1
            print(f"OK hex {rel}: {res.status.value} {res.seconds:.2f}s")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timeout_seconds": timeout,
        "count": len(out),
        "scan_seconds": round(time.perf_counter() - t_scan, 2),
        "by_game": dict(Counter(e["game"] for e in out)),
        "instances": out,
    }
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("--- by game ---")
    for k, v in sorted(payload["by_game"].items()):
        print(f"  {k}: {v}")
    print(f"wrote {args.out} n={len(out)} in {payload['scan_seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
