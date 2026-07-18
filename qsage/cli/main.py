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


def cmd_cert_equivalence(args: argparse.Namespace) -> int:
    from qsage.strategy import sqval

    if args.demo or args.cert_cmd == "demo-equivalence":
        paths = sqval.demo_equivalence_paths()
        missing = [k for k, p in paths.items() if not p.is_file()]
        if missing:
            print(
                "SQval demo files missing:",
                ", ".join(missing),
                "\nRun: bash scripts/setup_sqval.sh",
                file=sys.stderr,
            )
            return 2
        res = sqval.run_equivalence(
            paths["instance1"],
            paths["instance2"],
            paths["certificate"],
            paths["shared_variables"],
        )
    else:
        if not all(
            [
                args.instance1,
                args.instance2,
                args.certificate,
                args.shared_variables,
            ]
        ):
            print(
                "need --instance1 --instance2 --certificate --shared-variables "
                "(or --demo)",
                file=sys.stderr,
            )
            return 2
        res = sqval.run_equivalence(
            args.instance1,
            args.instance2,
            args.certificate,
            args.shared_variables,
        )
    print(res.message)
    if res.raw.strip():
        # show last non-empty lines
        lines = [ln for ln in res.raw.strip().splitlines() if ln.strip()]
        for ln in lines[-8:]:
            print(ln)
    return 0 if res.equivalent else 1


def cmd_cert_demo(args: argparse.Namespace) -> int:
    args.demo = True
    args.cert_cmd = "demo-equivalence"
    args.instance1 = args.instance2 = args.certificate = args.shared_variables = None
    return cmd_cert_equivalence(args)


def cmd_cert_validate(args: argparse.Namespace) -> int:
    from qsage.strategy import sqval

    extra = list(args.sqval_args or [])
    if extra and extra[0] == "--":
        extra = extra[1:]
    try:
        return sqval.launch_interactive_validation(extra)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2


def cmd_cert_demo_partial(args: argparse.Namespace) -> int:
    """Partial shared-strategy equivalence (Hein_12 BOW)."""
    from qsage.strategy import sqval

    paths = sqval.demo_partial_equivalence_paths()
    missing = [k for k, p in paths.items() if not p.is_file()]
    if missing:
        print(
            "SQval partial demo files missing:",
            ", ".join(missing),
            "\nRun: bash scripts/setup_sqval.sh",
            file=sys.stderr,
        )
        return 2
    # Direction that holds: BOW_0 cert → BOW_1 (see SQval README)
    res = sqval.run_equivalence(
        paths["instance1"],
        paths["instance2"],
        paths["certificate"],
        paths["shared_variables"],
    )
    print(res.message)
    print(
        "(partial shared vars: cert for BOW_0 applied to BOW_1 — "
        "scalable partial-strategy transfer)"
    )
    if res.raw.strip():
        lines = [ln for ln in res.raw.strip().splitlines() if ln.strip()]
        for ln in lines[-8:]:
            print(ln)
    return 0 if res.equivalent else 1


def cmd_cert_hybrid(args: argparse.Namespace) -> int:
    """Hybrid interactive validation: partial cert + DepQBF tail."""
    from qsage.strategy import sqval

    depth = args.depth
    if depth is None:
        print("need --depth N (cert layers before solver)", file=sys.stderr)
        return 2
    if args.demo:
        paths = sqval.demo_hybrid_paths()
        missing = [k for k, p in paths.items() if k != "qdimacs" and not p.is_file()]
        if missing:
            print(
                "SQval hybrid demo files missing:",
                ", ".join(missing),
                "\nRun: bash scripts/setup_sqval.sh",
                file=sys.stderr,
            )
            return 2
        instance = paths["instance"]
        certificate = paths["certificate"]
        status = "sat"
    else:
        if not args.instance or not args.certificate:
            print(
                "need --instance and --certificate (or --demo)",
                file=sys.stderr,
            )
            return 2
        instance = args.instance
        certificate = args.certificate
        status = args.status or "sat"

    player = args.player or "random"
    if player == "user":
        # Interactive: hand off to SQval TTY
        extra = [
            "--instance",
            str(instance),
            "--certificate",
            str(certificate),
            "--validation",
            "hybrid",
            "--hybrid_depth",
            str(depth),
            "--status",
            status,
            "--player",
            "user",
        ]
        return sqval.launch_interactive_validation(extra)

    res = sqval.run_hybrid_validation(
        instance,
        certificate,
        depth,
        status=status,
        player=player,
        seed=args.seed,
    )
    print(res.message)
    if res.raw.strip():
        lines = [ln for ln in res.raw.strip().splitlines() if ln.strip()]
        for ln in lines[-20:]:
            print(ln)
    return 0 if res.ok else 1


def cmd_cert_generate(args: argparse.Namespace) -> int:
    """Generate a strategy certificate (Pedant CNF or DepQBF+qrpcert AIGER)."""
    from qsage.strategy import depqbf

    if not args.qdimacs:
        print("need --qdimacs", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else Path("certificate.cnf")
    backend = args.backend or "pedant"
    if backend == "pedant":
        res = depqbf.generate_certificate_pedant(
            args.qdimacs, out, timeout=args.timeout
        )
    elif backend in ("depqbf", "qrpcert", "depqbf+qrpcert"):
        if out.suffix not in (".aag", ".aig"):
            out = out.with_suffix(".aag")
        res = depqbf.generate_certificate_depqbf_qrp(
            args.qdimacs, out, timeout=args.timeout
        )
    else:
        print(f"unknown backend {backend!r} (pedant|depqbf)", file=sys.stderr)
        return 2
    print(res.message)
    if res.raw and args.verbose:
        print(res.raw[-2000:])
    return 0 if res.ok else 1


def cmd_web(args: argparse.Namespace) -> int:
    from qsage.web.server import serve

    print(f"Open http://{args.host}:{args.port}/  (Ctrl+C to stop)")
    serve(args.host, args.port)
    return 0


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

    c = sub.add_parser(
        "cert",
        help="Certificate validation via SQval (issue #9)",
    )
    c_sub = c.add_subparsers(dest="cert_cmd")
    c_eq = c_sub.add_parser(
        "equivalence",
        help="Winning-strategy equivalence (two QDIMACS + AIGER cert)",
    )
    c_eq.add_argument("--instance1", help="QDIMACS instance 1")
    c_eq.add_argument("--instance2", help="QDIMACS instance 2")
    c_eq.add_argument("--certificate", help="AIGER certificate for instance1")
    c_eq.add_argument("--shared-variables", help="shared variables file")
    c_eq.add_argument(
        "--demo",
        action="store_true",
        help="run SQval hein_04_05 LN→SN demo if present",
    )
    c_eq.set_defaults(func=cmd_cert_equivalence)

    c_val = c_sub.add_parser(
        "validate",
        help="Launch SQval interactive_validation.py",
    )
    c_val.add_argument(
        "sqval_args",
        nargs=argparse.REMAINDER,
        help="args for SQval (use -- before flags)",
    )
    c_val.set_defaults(func=cmd_cert_validate)

    c_demo = c_sub.add_parser(
        "demo-equivalence",
        help="Shortcut: SQval Hein_04 LN vs SN equivalence demo",
    )
    c_demo.set_defaults(func=cmd_cert_demo)

    c_partial = c_sub.add_parser(
        "demo-partial",
        help="Partial shared-strategy equivalence (Hein_12 BOW)",
    )
    c_partial.set_defaults(func=cmd_cert_demo_partial)

    c_hyb = c_sub.add_parser(
        "hybrid",
        help=(
            "Hybrid play: cert for first --depth layers, DepQBF/QuAbs after "
            "(partial certs → scalable interactive validation)"
        ),
    )
    c_hyb.add_argument(
        "--depth",
        type=int,
        required=True,
        help="hybrid_depth: use certificate for layers k < depth",
    )
    c_hyb.add_argument("--demo", action="store_true", help="Hein_04 SAT demo files")
    c_hyb.add_argument("--instance", help="QCIR or QDIMACS")
    c_hyb.add_argument("--certificate", help="AIGER or CNF certificate")
    c_hyb.add_argument("--status", default="sat", choices=("sat", "unsat"))
    c_hyb.add_argument(
        "--player",
        default="random",
        choices=("random", "user"),
        help="random = non-interactive (CI/Docker); user = terminal",
    )
    c_hyb.add_argument("--seed", type=int, default=0)
    c_hyb.set_defaults(func=cmd_cert_hybrid)

    c_gen = c_sub.add_parser(
        "generate",
        help="Generate strategy cert (Pedant CNF or DepQBF+qrpcert AIGER)",
    )
    c_gen.add_argument("--qdimacs", required=True, help="input QDIMACS")
    c_gen.add_argument(
        "--out",
        default="certificate.cnf",
        help="output path (default certificate.cnf)",
    )
    c_gen.add_argument(
        "--backend",
        default="pedant",
        choices=("pedant", "depqbf", "depqbf+qrpcert"),
        help="pedant → CNF; depqbf → AIGER via qrpcert (optional install)",
    )
    c_gen.add_argument("--timeout", type=int, default=300)
    c_gen.add_argument("-v", "--verbose", action="store_true")
    c_gen.set_defaults(func=cmd_cert_generate)

    w = sub.add_parser(
        "web",
        help="Local web UI for board play (issue #3 MVP)",
    )
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--port", type=int, default=8765)
    w.set_defaults(func=cmd_web)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        raise SystemExit(0)
    if args.command == "cert" and not getattr(args, "func", None):
        c.print_help()
        raise SystemExit(0)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
