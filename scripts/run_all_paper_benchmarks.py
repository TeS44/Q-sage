#!/usr/bin/env python3
"""
Parallel QuBi run on all paper goldens (bwnib + Hex pg).

Since ``qsage.encode`` QCIR matches goldens, solving goldens checks paper
SAT/UNSAT data. Optional ``--encode`` re-encodes via official API first.

    python3 scripts/run_all_paper_benchmarks.py --jobs 12 --timeout 3600
    python3 scripts/run_all_paper_benchmarks.py --jobs 12 --timeout 7200 --encode

Writes ``docs/PAPER_BENCHMARK_RESULTS.md`` and ``.json``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

# Paper labels (Table 2 + Hex sample) — from qsage.solve.paper_checks + docs
PAPER_EXPECT: dict[str, str] = {
    "httt/3x3_3_domino": "SAT",
    "httt/3x3_5_el": "SAT",
    "httt/3x3_9_tippy": "SAT",
    "httt/3x3_9_tic": "UNSAT",
    "httt/3x3_9_fatty": "UNSAT",
    "httt/3x3_9_knobby": "UNSAT",
    "httt/3x3_9_elly": "UNSAT",
    "B/2x4_13": "UNSAT",
    "B/2x6_15": "SAT",
    "BSP/2x4_8": "SAT",
    "BSP/2x5_10": "SAT",
    "C4/2x2_3_connect2": "SAT",
    "C4/3x3_3_connect2": "SAT",
    "D/2x2_2": "SAT",
    "hex/hein_04_3x3-03": "UNSAT",
    "hex/hein_04_3x3-05": "SAT",
    "hex/hein_07_4x4-07": "UNSAT",
    "hex/hein_09_4x4-05": "UNSAT",
    "hex/hein_09_4x4-07": "SAT",
    "hex/hein_12_4x4-05": "UNSAT",
    "hex/hein_12_4x4-07": "SAT",
    "hex/hein_06_4x4-11": "UNSAT",
    "hex/browne_5x5_07": "UNSAT",
}

# golden folder → model folder (for --encode)
_GOLD_TO_MODEL = {
    "httt": "httt",
    "B": "breakthrough",
    "BSP": "breakthrough-second-player",
    "C4": "connect-c",
    "D": "domineering",
    "EP": "evader_pursuer",
    "EP-dual": "evader_pursuer_dual",
    "hex": None,  # positional
}


@dataclass
class Row:
    key: str
    kind: str  # grid | hex
    paper_expect: str
    status: str
    seconds: float
    match_paper: str  # yes | no | n/a
    source: str  # golden | encode
    error: str


def _status(res) -> str:
    from qsage.solve.result import Status

    if res.status is Status.SAT:
        return "SAT"
    if res.status is Status.UNSAT:
        return "UNSAT"
    return res.status.value


def _worker(job: dict) -> dict:
    os.chdir(_REPO)
    sys.path.insert(0, str(_REPO))
    from qsage.solve.qubi import solve_qcir_qubi

    key = job["key"]
    timeout = float(job["timeout"])
    t0 = time.perf_counter()
    try:
        if job.get("encode"):
            if job["kind"] == "hex":
                from qsage.encode.positional import encode_positional

                qcir = encode_positional(job["path"], encoding="pg")
                src = "encode_pg"
            else:
                from qsage.encode.bwnib import encode_bwnib

                qcir = encode_bwnib(job["domain"], job["path"])
                src = "encode_bwnib"
        else:
            qcir = Path(job["golden"]).read_text(encoding="utf-8")
            src = "golden"
        res = solve_qcir_qubi(qcir, timeout=timeout)
        return {
            **job,
            "status": _status(res),
            "seconds": round(res.seconds, 3),
            "wall": round(time.perf_counter() - t0, 3),
            "source": src,
            "error": "",
        }
    except Exception as e:
        return {
            **job,
            "status": "ERROR",
            "seconds": 0.0,
            "wall": round(time.perf_counter() - t0, 3),
            "source": "error",
            "error": f"{type(e).__name__}: {e}",
        }


def _collect_jobs(timeout: float, do_encode: bool) -> list[dict]:
    jobs: list[dict] = []
    gold_root = _REPO / "Benchmarks" / "SAT2023_GDDL" / "QBF_instances"
    models = _REPO / "Benchmarks" / "SAT2023_GDDL" / "GDDL_models"

    for gfolder, model in sorted(_GOLD_TO_MODEL.items()):
        if gfolder == "hex":
            continue
        gdir = gold_root / gfolder
        if not gdir.is_dir():
            continue
        for gq in sorted(gdir.glob("*_bwnib.qcir")):
            stem = gq.name.replace("_bwnib.qcir", "")
            key = f"{gfolder}/{stem}"
            prob = models / model / f"{stem}.ig" if model else None
            dom = models / model / "domain.ig" if model else None
            jobs.append(
                {
                    "key": key,
                    "kind": "grid",
                    "golden": str(gq),
                    "path": str(prob) if prob and prob.is_file() else "",
                    "domain": str(dom) if dom and dom.is_file() else "",
                    "paper_expect": PAPER_EXPECT.get(key, ""),
                    "timeout": timeout,
                    "encode": bool(
                        do_encode and prob and prob.is_file() and dom and dom.is_file()
                    ),
                }
            )

    # Hex: all B-Hex boards with pg golden
    hex_dir = _REPO / "Benchmarks" / "B-Hex"
    gold_pg = _REPO / "Benchmarks" / "positional_goldens" / "pg"
    for pg in sorted(hex_dir.glob("*.pg")):
        key = f"hex/{pg.stem}"
        gq = gold_pg / f"{pg.stem}_pg.qcir"
        if not gq.is_file() and not do_encode:
            continue
        jobs.append(
            {
                "key": key,
                "kind": "hex",
                "golden": str(gq) if gq.is_file() else "",
                "path": str(pg),
                "domain": "",
                "paper_expect": PAPER_EXPECT.get(key, ""),
                "timeout": timeout,
                "encode": bool(do_encode or not gq.is_file()),
            }
        )
    return jobs


def _markdown(rows: list[Row], wall: float, jobs_n: int, workers: int, timeout: float) -> str:
    decided = [r for r in rows if r.status in ("SAT", "UNSAT")]
    paper_rows = [r for r in rows if r.paper_expect in ("SAT", "UNSAT")]
    paper_ok = sum(
        1 for r in paper_rows if r.status == r.paper_expect
    )
    paper_bad = [
        r
        for r in paper_rows
        if r.status in ("SAT", "UNSAT") and r.status != r.paper_expect
    ]
    paper_to = [
        r for r in paper_rows if r.status not in ("SAT", "UNSAT")
    ]

    lines = [
        "# Paper benchmark results (QuBi, parallel)",
        "",
        f"Generated by `scripts/run_all_paper_benchmarks.py`.",
        "",
        f"- Workers: **{workers}**  ·  timeout: **{timeout:.0f}s**  ·  wall: **{wall:.1f}s**",
        f"- Jobs: **{jobs_n}**  ·  decided: **{len(decided)}**  ·  "
        f"TIMEOUT/ERROR: **{sum(1 for r in rows if r.status not in ('SAT','UNSAT'))}**",
        f"- Paper-labeled: **{len(paper_rows)}**  ·  match: **{paper_ok}/{len(paper_rows)}** "
        f"(timeouts on labeled: {len(paper_to)}, hard mismatch: {len(paper_bad)})",
        "",
        "## Summary by family",
        "",
        "| Family | N | SAT | UNSAT | TIMEOUT | ERROR | Paper match |",
        "|--------|--:|----:|------:|--------:|------:|------------:|",
    ]
    fams = sorted({r.key.split("/")[0] for r in rows})
    for fam in fams:
        fr = [r for r in rows if r.key.startswith(fam + "/")]
        pr = [r for r in fr if r.paper_expect in ("SAT", "UNSAT")]
        pm = sum(1 for r in pr if r.status == r.paper_expect)
        lines.append(
            f"| {fam} | {len(fr)} | "
            f"{sum(1 for r in fr if r.status=='SAT')} | "
            f"{sum(1 for r in fr if r.status=='UNSAT')} | "
            f"{sum(1 for r in fr if r.status=='TIMEOUT')} | "
            f"{sum(1 for r in fr if r.status=='ERROR')} | "
            f"{pm}/{len(pr) if pr else 0} |"
        )

    lines += [
        "",
        "## Full table",
        "",
        "| Instance | Paper | Result | Match | Time (s) | Source |",
        "|----------|-------|--------|-------|---------:|--------|",
    ]
    for r in sorted(rows, key=lambda x: x.key):
        pe = r.paper_expect or "—"
        lines.append(
            f"| `{r.key}` | {pe} | {r.status} | {r.match_paper} | "
            f"{r.seconds:.3f} | {r.source} |"
        )

    if paper_bad:
        lines += ["", "## Paper mismatches (both decided)", ""]
        for r in paper_bad:
            lines.append(
                f"- `{r.key}`: paper={r.paper_expect} got={r.status} ({r.seconds:.3f}s)"
            )
    if paper_to:
        lines += ["", "## Paper-labeled timeouts / errors", ""]
        for r in paper_to:
            lines.append(
                f"- `{r.key}`: paper={r.paper_expect} got={r.status} {r.error}"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4)))
    ap.add_argument(
        "--timeout",
        type=float,
        default=3600.0,
        help="QuBi timeout per instance (default 3600 = 1h)",
    )
    ap.add_argument(
        "--encode",
        action="store_true",
        help="re-encode via qsage.encode instead of reading goldens",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=_REPO / "docs" / "PAPER_BENCHMARK_RESULTS.md",
    )
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument(
        "--keys-file",
        type=Path,
        default=None,
        help="JSON list of instance keys to run only (e.g. prior TIMEOUTs)",
    )
    ap.add_argument(
        "--merge-json",
        type=Path,
        default=None,
        help="existing results JSON to merge with (keys-file run overwrites)",
    )
    args = ap.parse_args()

    from qsage.solve.qubi import qubi_available

    if not qubi_available():
        print("QuBi missing", file=sys.stderr)
        return 2

    jobs = _collect_jobs(args.timeout, args.encode)
    if args.keys_file:
        want = set(json.loads(args.keys_file.read_text(encoding="utf-8")))
        jobs = [j for j in jobs if j["key"] in want]
        print(f"keys-file filter: {len(jobs)} jobs", flush=True)
    if args.limit:
        jobs = jobs[: args.limit]
    print(
        f"jobs={len(jobs)} workers={args.jobs} timeout={args.timeout:.0f}s "
        f"encode={args.encode} qubi=ok",
        flush=True,
    )
    t0 = time.perf_counter()
    results: list[dict] = []
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(_worker, j): j for j in jobs}
        done = 0
        for fut in as_completed(futs):
            done += 1
            r = fut.result()
            results.append(r)
            pe = r.get("paper_expect") or ""
            mark = r["status"]
            if pe in ("SAT", "UNSAT") and r["status"] in ("SAT", "UNSAT"):
                mark = "OK" if r["status"] == pe else "MISMATCH"
            print(
                f"[{done}/{len(jobs)}] {r['key']}: {r['status']} "
                f"paper={pe or '—'} {mark} ({r['seconds']:.2f}s) {r.get('source','')}",
                flush=True,
            )

    def _row_from_dict(r: dict) -> Row:
        pe = r.get("paper_expect") or ""
        s = r["status"]
        if pe in ("SAT", "UNSAT"):
            if s == pe:
                mp = "yes"
            elif s in ("SAT", "UNSAT"):
                mp = "no"
            else:
                mp = "timeout"
        else:
            mp = "n/a"
        return Row(
            key=r["key"],
            kind=r.get("kind") or ("hex" if str(r["key"]).startswith("hex/") else "grid"),
            paper_expect=pe,
            status=s,
            seconds=float(r["seconds"]),
            match_paper=mp,
            source=r.get("source") or "",
            error=r.get("error") or "",
        )

    by_key: dict[str, Row] = {}
    if args.merge_json and args.merge_json.is_file():
        for item in json.loads(args.merge_json.read_text(encoding="utf-8")):
            by_key[item["key"]] = _row_from_dict(item)
        print(f"merged prior rows: {len(by_key)}", flush=True)

    for r in results:
        by_key[r["key"]] = _row_from_dict(r)

    rows = list(by_key.values())

    wall = time.perf_counter() - t0
    md = _markdown(rows, wall, len(rows), args.jobs, args.timeout)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    json_path = args.out.with_suffix(".json")
    json_path.write_text(
        json.dumps([asdict(x) for x in sorted(rows, key=lambda z: z.key)], indent=2),
        encoding="utf-8",
    )

    paper_rows = [r for r in rows if r.paper_expect in ("SAT", "UNSAT")]
    paper_ok = sum(1 for r in paper_rows if r.match_paper == "yes")
    hard_bad = sum(1 for r in paper_rows if r.match_paper == "no")
    print(f"\nWrote {args.out}")
    print(f"Wrote {json_path}")
    print(
        f"paper match={paper_ok}/{len(paper_rows)} hard_mismatch={hard_bad} "
        f"wall={wall:.1f}s"
    )
    return 0 if hard_bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
