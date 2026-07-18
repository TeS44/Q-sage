"""Bloqqer preprocessor + CAQE solver (paper main combination)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from qsage.solve.docker_run import docker_available, run_in_linux
from qsage.solve.result import SolveResult, Status

_REPO = Path(__file__).resolve().parents[2]
_CAQE = _REPO / "solvers" / "caqe" / "caqe"
_BLOQQER = _REPO / "tools" / "Bloqqer" / "bloqqer"


def _qcir_to_qdimacs_legacy(qcir_text: str, out_path: Path) -> None:
    """Use the repo's proven QCIR→QDIMACS script for solver reliability."""
    import sys

    qcir_path = out_path.with_suffix(".qcir")
    qcir_path.write_text(qcir_text, encoding="utf-8")
    script = _REPO / "legacy" / "utils" / "qcir_to_qdimacs_transformer.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--input_file",
            str(qcir_path),
            "--output_file",
            str(out_path),
        ],
        check=True,
        cwd=str(_REPO),
    )


def _parse_caqe_output(text: str) -> Status:
    low = text.lower()
    if "c unsatisfiable" in low or "s cnf 0" in low:
        return Status.UNSAT
    if "c satisfiable" in low or "s cnf 1" in low:
        return Status.SAT
    # exit codes sometimes only
    return Status.UNKNOWN


def solve_qcir_bloqqer_caqe(
    qcir_text: str,
    *,
    work_dir: Path | None = None,
    timeout: int = 60,
) -> SolveResult:
    """
    QCIR → QDIMACS → Bloqqer → CAQE.

    On macOS, solver binaries are Linux ELF; we run them via Docker when needed.
    Work dirs are unique by default so parallel pytest workers do not clash.
    """
    own_work = False
    if work_dir is None:
        base = _REPO / "intermediate_files"
        base.mkdir(parents=True, exist_ok=True)
        # Stay under the repo so Docker `-v repo:/work` relative paths work.
        work = Path(tempfile.mkdtemp(prefix="qsage_bc_", dir=str(base)))
        own_work = True
    else:
        work = work_dir
        work.mkdir(parents=True, exist_ok=True)

    qdimacs_path = work / "instance.qdimacs"
    bloqqer_path = work / "instance.bloqqer"
    out_path = work / "caqe.out"
    t0 = time.perf_counter()

    try:
        _qcir_to_qdimacs_legacy(qcir_text, qdimacs_path)

        # Prefer Docker on non-Linux or when local exec fails (ELF on macOS).
        use_docker = docker_available()

        if use_docker:
            rel_q = qdimacs_path.relative_to(_REPO)
            rel_b = bloqqer_path.relative_to(_REPO)
            rel_o = out_path.relative_to(_REPO)
            cmd = f"""
set +e
chmod +x tools/Bloqqer/bloqqer solvers/caqe/caqe
tools/Bloqqer/bloqqer {rel_q} > {rel_b} 2>/dev/null
solvers/caqe/caqe --qdo {rel_b} > {rel_o} 2>&1
echo EXIT:$?
"""
            try:
                proc = run_in_linux(cmd, timeout=timeout)
            except subprocess.TimeoutExpired:
                return SolveResult(
                    Status.TIMEOUT,
                    "bloqqer+caqe",
                    time.perf_counter() - t0,
                    "timeout",
                )
            raw = (
                out_path.read_text(encoding="utf-8", errors="replace")
                if out_path.exists()
                else ""
            ) + ("\n" + proc.stdout if proc.stdout else "")
            status = _parse_caqe_output(raw)
            if status is Status.UNKNOWN and "EXIT:10" in (proc.stdout or ""):
                status = Status.SAT
            if status is Status.UNKNOWN and "EXIT:20" in (proc.stdout or ""):
                status = Status.UNSAT
            return SolveResult(
                status,
                "bloqqer+caqe",
                time.perf_counter() - t0,
                message=f"docker exit={proc.returncode}",
                raw=raw[-4000:],
            )

        # Native Linux path
        try:
            with open(bloqqer_path, "w", encoding="utf-8") as bf:
                subprocess.run(
                    [str(_BLOQQER), str(qdimacs_path)],
                    stdout=bf,
                    stderr=subprocess.DEVNULL,
                    timeout=timeout,
                    check=False,
                )
            proc = subprocess.run(
                [str(_CAQE), "--qdo", str(bloqqer_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return SolveResult(
                Status.TIMEOUT,
                "bloqqer+caqe",
                time.perf_counter() - t0,
                "timeout",
            )
        except OSError as e:
            return SolveResult(
                Status.ERROR,
                "bloqqer+caqe",
                time.perf_counter() - t0,
                message=f"cannot exec solvers ({e}); start Docker Desktop on macOS",
            )

        raw = (proc.stdout or "") + (proc.stderr or "")
        status = _parse_caqe_output(raw)
        if status is Status.UNKNOWN:
            if proc.returncode == 10:
                status = Status.SAT
            elif proc.returncode == 20:
                status = Status.UNSAT
        return SolveResult(
            status, "bloqqer+caqe", time.perf_counter() - t0, raw=raw[-4000:]
        )
    finally:
        if own_work:
            shutil.rmtree(work, ignore_errors=True)
