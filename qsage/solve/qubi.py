"""QuBi QBF circuit solver (https://github.com/jacopol/qubi)."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

from qsage.solve.result import SolveResult, Status

_REPO = Path(__file__).resolve().parents[2]
# Built binary location (docker build or local)
_QUBI_BIN = _REPO / "solvers" / "qubi" / "qubi"


def qubi_available() -> bool:
    return _QUBI_BIN.is_file() and os.access(_QUBI_BIN, os.X_OK)


def _parse_qubi(text: str) -> Status:
    """Parse QuBi output (e.g. 'Result: TRUE' / 'Result: FALSE')."""
    up = text.upper()
    # Prefer explicit Result: lines
    for line in text.splitlines():
        s = line.strip().upper()
        if "RESULT:" in s:
            if "TRUE" in s:
                return Status.SAT
            if "FALSE" in s:
                return Status.UNSAT
        if s in ("TRUE", "FALSE"):
            return Status.SAT if s == "TRUE" else Status.UNSAT
    if "RESULT: TRUE" in up or up.rstrip().endswith("TRUE"):
        return Status.SAT
    if "RESULT: FALSE" in up or up.rstrip().endswith("FALSE"):
        return Status.UNSAT
    return Status.UNKNOWN


def solve_qcir_qubi(
    qcir_text: str,
    *,
    work_dir: Path | None = None,
    timeout: int = 60,
) -> SolveResult:
    """Solve QCIR with QuBi natively (macOS/Linux). Reads QCIR directly."""
    t0 = time.perf_counter()

    if not qubi_available():
        return SolveResult(
            Status.ERROR,
            "qubi",
            0.0,
            message="QuBi binary missing at solvers/qubi/qubi (see scripts/build_qubi_macos.sh)",
        )

    # Per-call temp dir by default so parallel pytest workers do not clobber
    # a shared intermediate_files/solve/instance.qcir.
    own_td: tempfile.TemporaryDirectory[str] | None = None
    if work_dir is None:
        own_td = tempfile.TemporaryDirectory(prefix="qsage_qubi_")
        work = Path(own_td.name)
    else:
        work = work_dir
        work.mkdir(parents=True, exist_ok=True)

    try:
        qcir_path = work / "instance.qcir"
        qcir_path.write_text(qcir_text, encoding="utf-8")
        try:
            proc = subprocess.run(
                [str(_QUBI_BIN), "-v=0", "-w=1", str(qcir_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return SolveResult(
                Status.TIMEOUT, "qubi", time.perf_counter() - t0, "timeout"
            )
        except OSError as e:
            return SolveResult(
                Status.ERROR,
                "qubi",
                time.perf_counter() - t0,
                message=str(e),
            )
        raw = (proc.stdout or "") + (proc.stderr or "")
        return SolveResult(
            _parse_qubi(raw),
            "qubi",
            time.perf_counter() - t0,
            message=f"exit={proc.returncode}",
            raw=raw[-4000:],
        )
    finally:
        if own_td is not None:
            own_td.cleanup()
