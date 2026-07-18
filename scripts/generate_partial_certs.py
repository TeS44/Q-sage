#!/usr/bin/env python3
"""
Build partial certificates (opening books) for hybrid web play.

For each Hex .pg benchmark:
  1. Time full QuBi solve (timeout --full-timeout, default 2s).
  2. If SAT (or unknown), greedily record Black opening moves for
     --hybrid-depth plies: try each open cell, keep first that leaves
     residual mid-game SAT (timeout --move-timeout).

Usage::

    python3 scripts/generate_partial_certs.py
    python3 scripts/generate_partial_certs.py --only B-Hex --jobs 8
    python3 scripts/generate_partial_certs.py --hybrid-depth 3 --full-timeout 2
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _one_board(args: tuple) -> dict:
    """Worker: process a single relative path."""
    rel, hybrid_depth, full_timeout, move_timeout, encoding = args
    # fresh imports in worker
    from qsage.encode.positional import encode_positional
    from qsage.solve.qubi import qubi_available, solve_qcir_qubi
    from qsage.web.hex_session import (
        apply_move,
        new_hex_session,
        open_cells,
        undo,
    )
    from qsage.web.partial_certs import board_key, save_partial
    from qsage.web.hex_session import solve_qbf

    if not qubi_available():
        return {"path": rel, "error": "no qubi"}

    result: dict = {
        "version": 1,
        "path": rel,
        "kind": "hex",
        "encoding": encoding,
        "hybrid_depth": hybrid_depth,
        "layers": [],
        "full_status": None,
        "full_seconds": None,
    }

    try:
        t0 = time.perf_counter()
        qcir = encode_positional(_REPO / rel, encoding)
        res = solve_qcir_qubi(qcir, timeout=full_timeout)
        result["full_status"] = res.status.value
        result["full_seconds"] = time.perf_counter() - t0
    except Exception as e:
        result["full_status"] = "ERROR"
        result["error"] = str(e)
        save_partial(result)
        return result

    # Only build openings for SAT (winning strategy exists) or UNKNOWN
    # (still useful to try openings)
    if result["full_status"] not in ("SAT", "UNKNOWN", "TIMEOUT"):
        # UNSAT: no Black strategy — store empty openings
        result["note"] = "UNSAT: no Black opening book"
        save_partial(result)
        return result

    sess = new_hex_session(rel)
    for ply in range(hybrid_depth):
        if sess["finished"] or sess["to_move"] != "B":
            break
        key = board_key(sess["cells"], "B")
        opens = open_cells(sess)
        chosen = None
        chosen_status = None
        chosen_sec = None
        # Prefer moves that keep residual SAT
        for pos in opens:
            apply_move(sess, pos, "B")
            try:
                r = solve_qbf(sess, midgame=True, encoding=encoding, timeout=move_timeout)
                st = r.get("status")
                sec = r.get("seconds")
            except Exception:
                st, sec = "ERROR", None
            undo(sess)
            if st == "SAT":
                chosen, chosen_status, chosen_sec = pos, st, sec
                break
            if chosen is None and st in ("UNKNOWN", "TIMEOUT", "ERROR"):
                # remember first non-failing as weak fallback later
                pass
        if chosen is None and opens:
            # fallback: first open (weak) if full was SAT
            if result["full_status"] == "SAT":
                chosen = opens[0]
                chosen_status = "FALLBACK"
            else:
                break

        if chosen is None:
            break

        result["layers"].append(
            {
                "ply": ply,
                "board_key": key,
                "move": chosen,
                "status_after": chosen_status,
                "seconds": chosen_sec,
            }
        )
        apply_move(sess, chosen, "B")
        # opponent reply: if white to move, take a random-ish first open for
        # continuing the main line book (deterministic: sorted)
        if not sess["finished"] and sess["to_move"] == "W":
            w_opens = sorted(open_cells(sess))
            if w_opens:
                # try to pick a white move that still leaves Black SAT if possible
                w_choice = w_opens[0]
                for wp in w_opens:
                    apply_move(sess, wp, "W")
                    try:
                        r = solve_qbf(
                            sess, midgame=True, encoding=encoding, timeout=move_timeout
                        )
                        ok = r.get("status") == "SAT"
                    except Exception:
                        ok = False
                    undo(sess)
                    if ok:
                        w_choice = wp
                        break
                apply_move(sess, w_choice, "W")
                result["layers"][-1]["sample_white"] = w_choice

    out = save_partial(result)
    result["file"] = str(out.relative_to(_REPO))
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", default="", help="substring filter on path")
    ap.add_argument("--hybrid-depth", type=int, default=2)
    ap.add_argument("--full-timeout", type=float, default=2.0)
    ap.add_argument("--move-timeout", type=float, default=3.0)
    ap.add_argument("--encoding", default="pg")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="max boards (0=all)")
    args = ap.parse_args()

    boards: list[str] = []
    for folder in (
        _REPO / "Benchmarks" / "B-Hex",
        _REPO / "Benchmarks" / "SAT2023_GDDL" / "GDDL_models" / "hex",
    ):
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.pg")):
            rel = str(p.relative_to(_REPO))
            if args.only and args.only not in rel:
                continue
            boards.append(rel)
    if args.limit:
        boards = boards[: args.limit]

    print(f"Generating partial certs for {len(boards)} boards "
          f"(hybrid_depth={args.hybrid_depth}, jobs={args.jobs})")

    work = [
        (rel, args.hybrid_depth, args.full_timeout, args.move_timeout, args.encoding)
        for rel in boards
    ]
    ok = 0
    # ProcessPool can be heavy with QuBi; use threads if jobs==1 sequential
    if args.jobs <= 1:
        results = [_one_board(w) for w in work]
    else:
        results = []
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            futs = {ex.submit(_one_board, w): w[0] for w in work}
            for fut in as_completed(futs):
                rel = futs[fut]
                try:
                    r = fut.result()
                except Exception as e:
                    r = {"path": rel, "error": str(e)}
                results.append(r)
                st = r.get("full_status")
                nlay = len(r.get("layers") or [])
                print(f"  {r.get('path')}: {st} layers={nlay} "
                      f"({r.get('full_seconds') and round(r['full_seconds'], 2)}s)")
                ok += 1

    if args.jobs <= 1:
        for r in results:
            st = r.get("full_status")
            nlay = len(r.get("layers") or [])
            print(f"  {r.get('path')}: {st} layers={nlay}")
            ok += 1

    index = {
        "generated": time_iso(),
        "count": len(results),
        "boards": [
            {
                "path": r.get("path"),
                "full_status": r.get("full_status"),
                "layers": len(r.get("layers") or []),
                "file": r.get("file"),
            }
            for r in results
        ],
    }
    idx_path = _REPO / "Benchmarks" / "partial_certs" / "index.json"
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"Done. Index: {idx_path}")
    return 0


def time_iso() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
