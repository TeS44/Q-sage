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


def cmd_solve(args: argparse.Namespace) -> int:
    from qsage.encode import encode_bwnib
    from qsage.solve import solve_qcir_bloqqer_caqe, solve_qcir_qubi
    from qsage.solve.result import Status

    if args.qcir:
        qcir = Path(args.qcir).read_text(encoding="utf-8")
    elif args.domain and args.problem:
        if args.encoding != "bwnib":
            print("only -e bwnib supported for encode+solve", file=sys.stderr)
            return 2
        qcir = encode_bwnib(args.domain, args.problem)
    else:
        print("solve needs --qcir or (--domain and --problem)", file=sys.stderr)
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
    from qsage.encode import encode_bwnib, normalize_qcir, qcir_to_qdimacs

    if args.encoding != "bwnib":
        print(f"unsupported encoding {args.encoding!r} (only bwnib for now)", file=sys.stderr)
        return 2
    if not args.domain or not args.problem:
        print("encode needs --domain and --problem", file=sys.stderr)
        return 2

    qcir = encode_bwnib(args.domain, args.problem)
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
    e.add_argument("--domain", required=True, help="BDDL domain (.ig)")
    e.add_argument("--problem", required=True, help="BDDL problem (.ig or hex .pg)")
    e.add_argument("-e", "--encoding", default="bwnib", help="encoding (default: bwnib)")
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
    s.add_argument("--domain", help="BDDL domain (encode then solve)")
    s.add_argument("--problem", help="BDDL problem")
    s.add_argument("-e", "--encoding", default="bwnib")
    s.add_argument(
        "--backend",
        default="qubi",
        choices=("qubi", "bloqqer+caqe"),
        help="qubi runs natively on macOS; bloqqer+caqe uses Docker on Mac",
    )
    s.add_argument("--timeout", type=int, default=120)
    s.set_defaults(func=cmd_solve)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        raise SystemExit(0)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
