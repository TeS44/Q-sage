"""QuBi QBF circuit solver (https://github.com/jacopol/qubi).

QuBi itself has **no** ``-t`` wall-clock limit. We always enforce a hard
timeout via subprocess (process-group kill) so batch jobs and the web UI
cannot hang forever.
"""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from qsage.solve.result import SolveResult, Status

_REPO = Path(__file__).resolve().parents[2]
_QUBI_BIN = _REPO / "solvers" / "qubi" / "qubi"

# Interactive / catalog defaults (seconds). Callers can override.
DEFAULT_TIMEOUT = 3.0
# Batch / paper benchmarks may pass 1–2h; web/catalog use small defaults.
MAX_TIMEOUT = 7200.0


def qubi_available() -> bool:
    return _QUBI_BIN.is_file() and os.access(_QUBI_BIN, os.X_OK)


def _parse_qubi(text: str) -> Status:
    """Parse QuBi output (e.g. 'Result: TRUE' / 'Result: FALSE')."""
    up = text.upper()
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


def _run_qubi(qcir_path: Path, timeout: float) -> tuple[int, str]:
    """
    Run QuBi with a hard wall-clock limit.

    Uses a new session so we can SIGKILL the whole process group if QuBi
    spawns worker threads/processes and does not exit promptly.
    """
    timeout = float(timeout)
    if timeout <= 0:
        timeout = DEFAULT_TIMEOUT
    timeout = min(timeout, MAX_TIMEOUT)

    cmd = [str(_QUBI_BIN), "-v=0", "-w=1", str(qcir_path)]
    # -w=1: single worker — easier to kill cleanly under timeout
    popen_kwargs: dict = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    # POSIX: new process group for killpg
    if os.name == "posix":
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **popen_kwargs)
    try:
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode or 0, (out or "") + (err or "")
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        try:
            out, err = proc.communicate(timeout=1)
        except Exception:
            out, err = "", ""
        raise subprocess.TimeoutExpired(
            cmd=cmd, timeout=timeout, output=out, stderr=err
        ) from None


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Best-effort hard kill of QuBi and any children."""
    try:
        if os.name == "posix" and proc.pid:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                proc.kill()
        else:
            proc.kill()
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=2)
    except Exception:
        pass


def solve_qcir_qubi(
    qcir_text: str,
    *,
    work_dir: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> SolveResult:
    """
    Solve QCIR with QuBi.

    ``timeout`` is a hard wall-clock limit in seconds (default 3s). On
    expiry returns ``Status.TIMEOUT`` and the QuBi process is killed.
    """
    t0 = time.perf_counter()

    if not qubi_available():
        return SolveResult(
            Status.ERROR,
            "qubi",
            0.0,
            message="QuBi binary missing at solvers/qubi/qubi "
            "(see scripts/build_qubi_macos.sh)",
        )

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
            code, raw = _run_qubi(qcir_path, float(timeout))
        except subprocess.TimeoutExpired as e:
            elapsed = time.perf_counter() - t0
            return SolveResult(
                Status.TIMEOUT,
                "qubi",
                elapsed,
                message=f"timeout after {timeout}s (process killed)",
                raw=((e.output or "") + (getattr(e, "stderr", None) or ""))[-2000:],
            )
        except OSError as e:
            return SolveResult(
                Status.ERROR,
                "qubi",
                time.perf_counter() - t0,
                message=str(e),
            )
        return SolveResult(
            _parse_qubi(raw),
            "qubi",
            time.perf_counter() - t0,
            message=f"exit={code}",
            raw=raw[-4000:],
        )
    finally:
        if own_td is not None:
            own_td.cleanup()
