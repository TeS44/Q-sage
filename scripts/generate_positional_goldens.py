#!/usr/bin/env python3
"""
Generate positional QCIR goldens from the legacy encoder.

Writes:
  Benchmarks/positional_goldens/{pg,cp,ibign}/<stem>_<enc>.qcir

Run from repo root:
  PYTHONPATH=legacy python3 scripts/generate_positional_goldens.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "legacy"
BENCH = ROOT / "Benchmarks" / "B-Hex"
OUT = ROOT / "Benchmarks" / "positional_goldens"
ENCODINGS = ("pg", "cp", "ibign")


def main() -> int:
    os.chdir(ROOT)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(LEGACY) + os.pathsep + env.get("PYTHONPATH", "")

    problems = sorted(BENCH.glob("*.pg"))
    if not problems:
        print("no .pg under Benchmarks/B-Hex", file=sys.stderr)
        return 1

    ok = fail = 0
    for enc in ENCODINGS:
        dest = OUT / enc
        dest.mkdir(parents=True, exist_ok=True)
        for prob in problems:
            out = dest / f"{prob.stem}_{enc}.qcir"
            cmd = [
                sys.executable,
                str(LEGACY / "Q-sage.py"),
                "-e",
                enc,
                "--game_type",
                "hex",
                "--problem",
                str(prob),
                "--encoding_format",
                "1",
                "--encoding_out",
                str(out),
                "--run",
                "0",
                "--debug",
                "-1",
                "--planner_path",
                str(ROOT),
            ]
            print(f"encode {enc} {prob.name} …", flush=True)
            r = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if r.returncode != 0 or not out.is_file() or out.stat().st_size < 20:
                print(f"  FAIL {prob.name}: {r.stderr[-400:] or r.stdout[-400:]}")
                fail += 1
                if out.is_file():
                    out.unlink()
            else:
                print(f"  ok → {out.relative_to(ROOT)} ({out.stat().st_size} bytes)")
                ok += 1

    print(f"\ndone ok={ok} fail={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
