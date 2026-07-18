"""qsage command-line entry (more subcommands later: solve, play)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from qsage import __version__
from qsage.parse import parse_bddl, parse_domain, parse_pg, parse_problem


def _looks_like_positional(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return "#positions" in text or "#neighbours" in text


def cmd_play(args: argparse.Namespace) -> int:
    from qsage.play import run_certificate_play, run_hex_interactive

    # Remaining argv after known flags — forward to legacy scripts
    extra = list(args.legacy_args or [])
    if args.mode == "hex":
        if args.problem:
            extra = ["--problem", args.problem] + extra
        return run_hex_interactive(extra)
    if args.mode == "certificate":
        return run_certificate_play(extra)
    print("play mode must be hex or certificate", file=sys.stderr)
    return 2


def cmd_solve(args: argparse.Namespace) -> int:
    from qsage.encode import POSITIONAL_ENCODINGS, encode_bwnib, encode_positional
    from qsage.solve import solve_qcir_bloqqer_caqe, solve_qcir_qubi
    from qsage.solve.result import Status

    if args.qcir:
        qcir = Path(args.qcir).read_text(encoding="utf-8")
    elif args.encoding in POSITIONAL_ENCODINGS and args.problem:
        qcir = encode_positional(args.problem, args.encoding)
    elif args.encoding == "bwnib" and args.domain and args.problem:
        qcir = encode_bwnib(args.domain, args.problem)
    else:
        print(
            "solve needs --qcir, or (--domain/--problem for bwnib), "
            "or (--problem for pg|cp|ibign)",
            file=sys.stderr,
        )
        return 2

    if args.backend == "qubi":
        res = solve_qcir_qubi(qcir, timeout=args.timeout)
    elif args.backend == "bloqqer+caqe":
        res = solve_qcir_bloqqer_caqe(qcir, timeout=args.timeout)
    else:
        print(f"unknown backend {args.backend}", file=sys.stderr)
        return 2

    print(f"{res.backend}: {res.status.value} ({res.seconds:.2f}s) {res.message}")
    if res.status is Status.ERROR:
        return 2
    if res.status is Status.TIMEOUT:
        return 3
    return 0 if res.status in (Status.SAT, Status.UNSAT) else 1


def cmd_encode(args: argparse.Namespace) -> int:
    from qsage.encode import (
        POSITIONAL_ENCODINGS,
        encode_bwnib,
        encode_positional,
        normalize_qcir,
        qcir_to_qdimacs,
    )

    if args.encoding == "bwnib":
        if not args.domain or not args.problem:
            print("bwnib encode needs --domain and --problem", file=sys.stderr)
            return 2
        qcir = encode_bwnib(args.domain, args.problem)
    elif args.encoding in POSITIONAL_ENCODINGS:
        if not args.problem:
            print(f"{args.encoding} encode needs --problem (.pg)", file=sys.stderr)
            return 2
        qcir = encode_positional(args.problem, args.encoding)
    else:
        print(
            f"unsupported encoding {args.encoding!r} "
            f"(bwnib | {' | '.join(sorted(POSITIONAL_ENCODINGS))})",
            file=sys.stderr,
        )
        return 2

    if args.format == "qdimacs":
        text = qcir_to_qdimacs(qcir)
    else:
        text = normalize_qcir(qcir) if args.normalize else qcir

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    if args.domain and args.problem:
        domain, problem = parse_bddl(args.domain, args.problem)
        print(
            f"domain: {len(domain.black_actions)} black / "
            f"{len(domain.white_actions)} white actions"
        )
        print(
            f"problem: {problem.width}x{problem.height} depth={problem.depth} "
            f"goals B/W={len(problem.black_goals)}/{len(problem.white_goals)}"
        )
        return 0

    if args.domain:
        domain = parse_domain(args.domain)
        print("black:", [a.name for a in domain.black_actions])
        print("white:", [a.name for a in domain.white_actions])
        return 0

    if args.problem:
        path = Path(args.problem)
        if path.suffix == ".pg" and _looks_like_positional(path):
            game = parse_pg(path)
            print(
                f"positional: {len(game.positions)} cells, depth={game.depth}, "
                f"B0={list(game.black_initials)} W0={list(game.white_initials)}"
            )
        else:
            problem = parse_problem(path)
            print(f"problem: {problem.width}x{problem.height} depth={problem.depth}")
        return 0

    print("need --domain and/or --problem", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="qsage", description="QBF board-game encodings")
    parser.add_argument("-V", "--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("parse", help="Parse BDDL or positional input files")
    p.add_argument("--domain", help="BDDL domain (.ig)")
    p.add_argument("--problem", help="BDDL problem (.ig) or positional (.pg)")
    p.set_defaults(func=cmd_parse)

    e = sub.add_parser("encode", help="Generate QCIR/QDIMACS (paper encodings)")
    e.add_argument("--domain", help="BDDL domain (.ig) — required for bwnib")
    e.add_argument(
        "--problem",
        help="BDDL problem (.ig) or positional Hex (.pg)",
    )
    e.add_argument(
        "-e",
        "--encoding",
        default="bwnib",
        help="bwnib (grid) | pg | cp | ibign (Hex positional)",
    )
    e.add_argument(
        "--format",
        choices=("qcir", "qdimacs"),
        default="qcir",
        help="output format (default: qcir)",
    )
    e.add_argument("--out", help="write to file instead of stdout")
    e.add_argument(
        "--normalize",
        action="store_true",
        help="strip QCIR comments/blank lines (for comparing goldens)",
    )
    e.set_defaults(func=cmd_encode)

    s = sub.add_parser("solve", help="Solve QCIR with QuBi or Bloqqer+CAQE")
    s.add_argument("--qcir", help="existing QCIR file (e.g. golden)")
    s.add_argument("--domain", help="BDDL domain (bwnib encode then solve)")
    s.add_argument("--problem", help="BDDL problem or Hex .pg")
    s.add_argument(
        "-e",
        "--encoding",
        default="bwnib",
        help="bwnib | pg | cp | ibign when encoding from files",
    )
    s.add_argument(
        "--backend",
        default="qubi",
        choices=("qubi", "bloqqer+caqe"),
        help="qubi runs natively on macOS; bloqqer+caqe uses Docker on Mac",
    )
    s.add_argument("--timeout", type=int, default=120)
    s.set_defaults(func=cmd_solve)

    pl = sub.add_parser(
        "play",
        help="Interactive play (Hex vs solver, or certificate demo)",
    )
    pl.add_argument(
        "mode",
        choices=("hex", "certificate"),
        help="hex = positional Hex vs QBF; certificate = grid certificate play",
    )
    pl.add_argument(
        "--problem",
        help="for hex mode: path to .pg board (default inside legacy script)",
    )
    pl.add_argument(
        "legacy_args",
        nargs=argparse.REMAINDER,
        help="extra args passed to the legacy play script (use -- before flags)",
    )
    pl.set_defaults(func=cmd_play)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        raise SystemExit(0)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
