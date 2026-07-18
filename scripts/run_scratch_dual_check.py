#!/usr/bin/env python3
"""
Parallel dual-check: qsage.scratch vs previous encoders (pg / bwnib) on all
local benchmarks, using QuBi.

Timeouts: if Benchmarks/playable_qbf.json has a prior QuBi time for the
instance, use max(5, 10× that time + 2s) as hard kill; otherwise defaults.

    python3 scripts/run_scratch_dual_check.py
    python3 scripts/run_scratch_dual_check.py --jobs 12 --out docs/SCRATCH_DUAL_RESULTS.md

Also writes JSON next to the markdown.
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

# Paper Table 2 + positional sample expects (from qsage.solve.paper_checks + docs)
PAPER_EXPECT: dict[str, str] = {
    "httt/3x3_3_domino": "SAT",
    "httt/3x3_5_el": "SAT",
    "httt/3x3_9_tippy": "SAT",
    "httt/3x3_9_tic": "UNSAT",
    "httt/3x3_9_fatty": "UNSAT",
    "httt/3x3_9_knobby": "UNSAT",
    "httt/3x3_9_elly": "UNSAT",
    "breakthrough/2x4_13": "UNSAT",
    "breakthrough/2x6_15": "SAT",
    "breakthrough-second-player/2x4_8": "SAT",
    "breakthrough-second-player/2x5_10": "SAT",
    "connect-c/2x2_3_connect2": "SAT",
    "connect-c/3x3_3_connect2": "SAT",
    "domineering/2x2_2": "SAT",
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


@dataclass
class Row:
    family: str
    instance: str
    kind: str  # hex | grid
    paper_expect: str
    prev_status: str
    scratch_status: str
    prev_seconds: float
    scratch_seconds: float
    prior_scan_seconds: float | None
    timeout_used: float
    match_prev: bool
    match_paper: str  # yes | no | n/a
    note: str


def _status(res) -> str:
    from qsage.solve.result import Status

    if res.status is Status.SAT:
        return "SAT"
    if res.status is Status.UNSAT:
        return "UNSAT"
    return res.status.value


def _load_prior_times() -> dict[str, float]:
    """Map label/path stem → QuBi seconds from playable_qbf.json prior scan."""
    path = _REPO / "Benchmarks" / "playable_qbf.json"
    out: dict[str, float] = {}
    if not path.is_file():
        return out
    data = json.loads(path.read_text(encoding="utf-8"))
    for inst in data.get("instances") or []:
        sec = float(inst.get("seconds") or 0)
        label = inst.get("label") or ""
        p = inst.get("path") or ""
        out[label] = sec
        out[Path(p).stem] = sec
        # family/stem keys
        if "/" in label:
            out[label.replace(".ig", "").replace(".pg", "")] = sec
        game = inst.get("game") or ""
        if game and Path(p).stem:
            out[f"{game}/{Path(p).stem}"] = sec
    return out


def _timeout_for(
    key: str,
    prior: dict[str, float],
    default: float = 600.0,
    max_timeout: float = 3600.0,
) -> float:
    """Scale timeout from prior QuBi scan when available.

    Prior scan used a 3s catalog; dual-check needs much more headroom under
    parallel load. Cap at ``max_timeout`` (default 1 hour).
    """
    sec = prior.get(key)
    if sec is None:
        # try stem only
        sec = prior.get(key.split("/")[-1])
    if sec is None:
        return min(default, max_timeout)
    # Never go below ``default``: prior catalog times are for playable
    # encodings under light load; scratch/prev dual under parallel load
    # and harder scratch formulas need the same generous budget.
    return max(default, min(max_timeout, sec * 50.0 + 30.0))


def _worker(job: dict) -> dict:
    """Run one dual-check job in a worker process."""
    os.chdir(_REPO)
    sys.path.insert(0, str(_REPO))
    from qsage.solve.qubi import solve_qcir_qubi

    kind = job["kind"]
    timeout = float(job["timeout"])
    note = ""
    t0 = time.perf_counter()
    try:
        if kind == "hex":
            from qsage.scratch.hex import encode_hex_file
            from qsage.encode.positional import encode_positional

            path = Path(job["path"])
            gold = _REPO / "Benchmarks" / "positional_goldens" / "pg" / f"{path.stem}_pg.qcir"
            sq = encode_hex_file(path)
            if gold.is_file():
                pq = gold.read_text(encoding="utf-8")
                note = "prev=pg_golden"
            else:
                pq = encode_positional(path, encoding="pg")
                note = "prev=pg_live"
        else:
            from qsage.scratch.grid import encode_grid_files
            from qsage.encode.bwnib import encode_bwnib

            dom, prob = Path(job["domain"]), Path(job["path"])
            sq = encode_grid_files(dom, prob)
            pq = encode_bwnib(dom, prob)
            note = "prev=bwnib_live; scratch=bwnib"

        rs = solve_qcir_qubi(sq, timeout=timeout)
        rp = solve_qcir_qubi(pq, timeout=timeout)
        return {
            **job,
            "scratch_status": _status(rs),
            "prev_status": _status(rp),
            "scratch_seconds": round(rs.seconds, 3),
            "prev_seconds": round(rp.seconds, 3),
            "wall_seconds": round(time.perf_counter() - t0, 3),
            "note": note,
            "error": "",
        }
    except Exception as e:
        return {
            **job,
            "scratch_status": "ERROR",
            "prev_status": "ERROR",
            "scratch_seconds": 0.0,
            "prev_seconds": 0.0,
            "wall_seconds": round(time.perf_counter() - t0, 3),
            "note": note,
            "error": f"{type(e).__name__}: {e}",
        }


def _collect_jobs(
    prior: dict[str, float],
    default_timeout: float,
    max_timeout: float,
) -> list[dict]:
    jobs: list[dict] = []

    # Hex: all B-Hex
    hex_dir = _REPO / "Benchmarks" / "B-Hex"
    for pg in sorted(hex_dir.glob("*.pg")):
        key = f"hex/{pg.stem}"
        jobs.append(
            {
                "family": "hex",
                "instance": pg.stem,
                "kind": "hex",
                "path": str(pg),
                "domain": "",
                "paper_expect": PAPER_EXPECT.get(key, ""),
                "prior_scan_seconds": prior.get(key) or prior.get(pg.stem),
                "timeout": _timeout_for(key, prior, default_timeout, max_timeout),
            }
        )

    # Grid: all GDDL models
    models = _REPO / "Benchmarks" / "SAT2023_GDDL" / "GDDL_models"
    for dom in sorted(models.glob("*/domain.ig")):
        family = dom.parent.name
        if family == "hex":
            continue
        for prob in sorted(dom.parent.glob("*.ig")):
            if prob.name == "domain.ig":
                continue
            key = f"{family}/{prob.stem}"
            jobs.append(
                {
                    "family": family,
                    "instance": prob.stem,
                    "kind": "grid",
                    "path": str(prob),
                    "domain": str(dom),
                    "paper_expect": PAPER_EXPECT.get(key, ""),
                    "prior_scan_seconds": prior.get(key)
                    or prior.get(f"{family}/{prob.name}")
                    or prior.get(prob.stem),
                    "timeout": _timeout_for(
                        key, prior, default_timeout, max_timeout
                    ),
                }
            )
    return jobs


def _markdown_table(rows: list[Row]) -> str:
    lines = [
        "# Scratch dual-check results (QuBi)",
        "",
        f"Generated by `scripts/run_scratch_dual_check.py`.",
        "",
        "Columns: **prev** = previous encoder (`pg` golden/live or live `bwnib`); "
        "**scratch** = `qsage.scratch`; **prior_s** = QuBi time from "
        "`Benchmarks/playable_qbf.json` when available (used to scale timeouts).",
        "",
        "| Family | Instance | Paper | Prev | Scratch | Match prev | Match paper | "
        "Prev s | Scratch s | Prior s | Timeout | Note |",
        "|--------|----------|-------|------|---------|------------|-------------|"
        "--------|-----------|---------|---------|------|",
    ]
    for r in sorted(rows, key=lambda x: (x.family, x.instance)):
        prior = f"{r.prior_scan_seconds:.3f}" if r.prior_scan_seconds is not None else "—"
        lines.append(
            f"| {r.family} | `{r.instance}` | {r.paper_expect or '—'} | "
            f"{r.prev_status} | {r.scratch_status} | "
            f"{'✓' if r.match_prev else '✗'} | {r.match_paper} | "
            f"{r.prev_seconds:.3f} | {r.scratch_seconds:.3f} | {prior} | "
            f"{r.timeout_used:.0f} | {r.note} |"
        )

    # summary
    n = len(rows)
    mp = sum(1 for r in rows if r.match_prev)
    paper_rows = [r for r in rows if r.paper_expect in ("SAT", "UNSAT")]
    mpap = sum(1 for r in paper_rows if r.match_paper == "yes")
    both = [
        r
        for r in rows
        if r.scratch_status in ("SAT", "UNSAT") and r.prev_status in ("SAT", "UNSAT")
    ]
    agree = [r for r in both if r.scratch_status == r.prev_status]
    disagree = [r for r in both if r.scratch_status != r.prev_status]
    lines += [
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| Total instances | {n} |",
        f"| Both decided (SAT/UNSAT) | {len(both)} |",
        f"| Agree (both decided) | {len(agree)} / {len(both)} |",
        f"| Hard disagree (both decided) | {len(disagree)} |",
        f"| Match previous (incl. both-TO as fail) | {mp} / {n} |",
        f"| Paper-labeled subset | {len(paper_rows)} |",
        f"| Match paper (on labeled) | {mpap} / {len(paper_rows)} |",
        f"| TIMEOUT / ERROR (scratch) | "
        f"{sum(1 for r in rows if r.scratch_status not in ('SAT','UNSAT'))} |",
        f"| TIMEOUT / ERROR (prev) | "
        f"{sum(1 for r in rows if r.prev_status not in ('SAT','UNSAT'))} |",
        "",
        "### Timing (both decided only)",
        "",
        "QuBi wall-clock per encoding; ratio = scratch_s / prev_s. "
        "Correctness first — large ratios mean scratch is harder for the solver.",
        "",
    ]
    if both:
        ratios = [
            r.scratch_seconds / r.prev_seconds
            for r in both
            if r.prev_seconds > 1e-6
        ]
        ratios_s = sorted(ratios) if ratios else [0.0]
        mid = ratios_s[len(ratios_s) // 2]
        lines += [
            f"| Metric | Value |",
            f"|--------|------:|",
            f"| Total solve time scratch | {sum(r.scratch_seconds for r in both):.3f}s |",
            f"| Total solve time prev | {sum(r.prev_seconds for r in both):.3f}s |",
            f"| Ratio min / median / max | "
            f"{min(ratios_s):.2f} / {mid:.2f} / {max(ratios_s):.2f} |",
            f"| Scratch >3× slower | {sum(1 for x in ratios if x > 3)} |",
            f"| Scratch >3× faster | {sum(1 for x in ratios if x < 1/3)} |",
            "",
        ]
        slow = sorted(
            [r for r in both if r.prev_seconds > 1e-6 and r.scratch_seconds / r.prev_seconds > 3],
            key=lambda r: -(r.scratch_seconds / r.prev_seconds),
        )[:15]
        if slow:
            lines += ["Scratch much slower than prev (>3×):", ""]
            for r in slow:
                ratio = r.scratch_seconds / r.prev_seconds
                lines.append(
                    f"- `{r.family}/{r.instance}`: scratch={r.scratch_seconds:.3f}s "
                    f"prev={r.prev_seconds:.3f}s ({ratio:.1f}×)"
                )
            lines.append("")

    lines += [
        "### By family",
        "",
        "| Family | N | Both dec. | Agree | Disagree | Scratch TO | Prev TO |",
        "|--------|--:|----------:|------:|---------:|-----------:|--------:|",
    ]

    fams = sorted({r.family for r in rows})
    for fam in fams:
        fr = [r for r in rows if r.family == fam]
        b = [
            r
            for r in fr
            if r.scratch_status in ("SAT", "UNSAT")
            and r.prev_status in ("SAT", "UNSAT")
        ]
        ag = sum(1 for r in b if r.scratch_status == r.prev_status)
        di = len(b) - ag
        st = sum(1 for r in fr if r.scratch_status not in ("SAT", "UNSAT"))
        pt = sum(1 for r in fr if r.prev_status not in ("SAT", "UNSAT"))
        lines.append(
            f"| {fam} | {len(fr)} | {len(b)} | {ag} | {di} | {st} | {pt} |"
        )

    if disagree:
        lines += ["", "### Hard disagreements (both decided, different)", ""]
        for r in disagree:
            lines.append(
                f"- `{r.family}/{r.instance}`: scratch={r.scratch_status} "
                f"prev={r.prev_status} paper={r.paper_expect or '—'} "
                f"(s={r.scratch_seconds:.3f}s p={r.prev_seconds:.3f}s) ({r.note})"
            )

    mismatches = [r for r in rows if not r.match_prev]
    if mismatches:
        lines += ["", "### Mismatches / timeouts (match_prev false)", ""]
        for r in mismatches:
            lines.append(
                f"- `{r.family}/{r.instance}`: scratch={r.scratch_status} "
                f"prev={r.prev_status} paper={r.paper_expect or '—'} "
                f"s={r.scratch_seconds:.3f}s p={r.prev_seconds:.3f}s ({r.note})"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--jobs",
        type=int,
        default=max(1, (os.cpu_count() or 4) - 0),
        help="parallel workers (default: all cores)",
    )
    ap.add_argument(
        "--default-timeout",
        type=float,
        default=600.0,
        help="QuBi timeout when no prior scan time (s); default 600",
    )
    ap.add_argument(
        "--max-timeout",
        type=float,
        default=3600.0,
        help="hard cap per solve (s); default 3600 (1h)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=_REPO / "docs" / "SCRATCH_DUAL_RESULTS.md",
    )
    ap.add_argument("--limit", type=int, default=0, help="max jobs (0=all)")
    args = ap.parse_args()

    from qsage.solve.qubi import qubi_available

    if not qubi_available():
        print("QuBi missing (solvers/qubi/qubi)", file=sys.stderr)
        return 2

    prior = _load_prior_times()
    jobs = _collect_jobs(prior, args.default_timeout, args.max_timeout)
    if args.limit:
        jobs = jobs[: args.limit]

    tmax = max((j["timeout"] for j in jobs), default=0)
    tmin = min((j["timeout"] for j in jobs), default=0)
    print(
        f"jobs={len(jobs)} workers={args.jobs} "
        f"prior_times={len(prior)} qubi=ok "
        f"timeouts=[{tmin:.0f},{tmax:.0f}]s default={args.default_timeout:.0f}",
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
            mark = "OK" if r["scratch_status"] == r["prev_status"] and r[
                "scratch_status"
            ] in ("SAT", "UNSAT") else r["scratch_status"]
            print(
                f"[{done}/{len(jobs)}] {r['family']}/{r['instance']}: "
                f"s={r['scratch_status']} p={r['prev_status']} {mark} "
                f"solve_s={r['scratch_seconds']:.3f}s solve_p={r['prev_seconds']:.3f}s "
                f"wall={r['wall_seconds']:.1f}s",
                flush=True,
            )

    rows: list[Row] = []
    for r in results:
        pe = r.get("paper_expect") or ""
        s, p = r["scratch_status"], r["prev_status"]
        match_prev = s == p and s in ("SAT", "UNSAT")
        if pe in ("SAT", "UNSAT"):
            match_paper = "yes" if s == pe and p == pe else "no"
        else:
            match_paper = "n/a"
        note = r.get("note") or ""
        if r.get("error"):
            note = (note + " " + r["error"]).strip()
        rows.append(
            Row(
                family=r["family"],
                instance=r["instance"],
                kind=r["kind"],
                paper_expect=pe,
                prev_status=p,
                scratch_status=s,
                prev_seconds=float(r["prev_seconds"]),
                scratch_seconds=float(r["scratch_seconds"]),
                prior_scan_seconds=r.get("prior_scan_seconds"),
                timeout_used=float(r["timeout"]),
                match_prev=match_prev,
                match_paper=match_paper,
                note=note,
            )
        )

    md = _markdown_table(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    json_path = args.out.with_suffix(".json")
    json_path.write_text(
        json.dumps([asdict(r) for r in rows], indent=2),
        encoding="utf-8",
    )
    elapsed = time.perf_counter() - t0
    n = len(rows)
    mp = sum(1 for r in rows if r.match_prev)
    print(f"\nWrote {args.out}")
    print(f"Wrote {json_path}")
    print(f"match_prev={mp}/{n} wall={elapsed:.1f}s workers={args.jobs}")
    return 0 if mp == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
