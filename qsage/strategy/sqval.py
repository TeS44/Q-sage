"""
Thin wrappers around SQval (https://github.com/irfansha/SQval).

SQval provides full/partial certificate validation and winning-strategy
equivalence (LIPIcs SAT 2023). We do not reimplement those algorithms.

On macOS/Windows, SQval's bundled DepQBF is Linux ELF — we run the demo
via Docker when needed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SQVAL = _REPO / "third_party" / "SQval"


@dataclass
class EquivalenceResult:
    equivalent: bool
    message: str
    raw: str


def sqval_root() -> Path:
    return _SQVAL


def sqval_available() -> bool:
    return (_SQVAL / "winning_strategy_equivalence.py").is_file()


def ensure_sqval() -> Path:
    if sqval_available():
        return _SQVAL
    raise FileNotFoundError(
        "SQval not found. Run: bash scripts/setup_sqval.sh\n"
        f"Expected at {_SQVAL}"
    )


def _docker_ok() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=10,
        )
        return True
    except Exception:
        return False


def run_equivalence(
    instance1: str | Path,
    instance2: str | Path,
    certificate: str | Path,
    shared_variables: str | Path,
    *,
    status: str = "sat",
) -> EquivalenceResult:
    """
    Check if a certificate for instance1 also wins for instance2 (shared vars).

    Uses SQval's winning_strategy_equivalence.py (DepQBF). On non-Linux hosts,
    runs that script inside a linux/amd64 Docker container with SQval mounted.
    """
    root = ensure_sqval()
    i1 = Path(instance1).resolve()
    i2 = Path(instance2).resolve()
    cert = Path(certificate).resolve()
    shared = Path(shared_variables).resolve()

    # Paths relative to SQval root when files live under third_party/SQval
    def rel_to_sqval(p: Path) -> str:
        try:
            return str(p.relative_to(root))
        except ValueError:
            # copy outside files into SQval intermediate for docker access
            raise ValueError(
                f"{p} must be under {root} for Docker-based SQval runs"
            ) from None

    script_args = [
        "--instance1",
        rel_to_sqval(i1) if _docker_ok() and sys.platform != "linux" else str(i1),
        "--instance2",
        rel_to_sqval(i2) if _docker_ok() and sys.platform != "linux" else str(i2),
        "--certificate",
        rel_to_sqval(cert) if _docker_ok() and sys.platform != "linux" else str(cert),
        "--shared_variables",
        rel_to_sqval(shared)
        if _docker_ok() and sys.platform != "linux"
        else str(shared),
        "--status",
        status,
    ]

    use_docker = sys.platform != "linux" and _docker_ok()

    if use_docker:
        # Ensure paths are under SQval mount
        for p in (i1, i2, cert, shared):
            rel_to_sqval(p)
        inner = (
            "export DEBIAN_FRONTEND=noninteractive; "
            "apt-get update -qq >/dev/null 2>&1; "
            "apt-get install -y -qq python3 python3-pip libgomp1 >/dev/null 2>&1; "
            "pip3 install -q python-sat >/dev/null 2>&1; "
            "chmod +x solvers/depqbf/depqbf solvers/quabs/quabs 2>/dev/null; "
            "python3 winning_strategy_equivalence.py "
            + " ".join(script_args)
        )
        proc = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--platform",
                "linux/amd64",
                "-v",
                f"{root}:/work",
                "-w",
                "/work",
                "ubuntu:22.04",
                "bash",
                "-c",
                inner,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
    else:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [sys.executable, str(root / "winning_strategy_equivalence.py")]
            + [
                "--instance1",
                str(i1),
                "--instance2",
                str(i2),
                "--certificate",
                str(cert),
                "--shared_variables",
                str(shared),
                "--status",
                status,
            ],
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )

    raw = (proc.stdout or "") + (proc.stderr or "")
    low = raw.lower()
    if "not equivalent" in low:
        return EquivalenceResult(False, "winning strategy NOT equivalent", raw)
    if "equivalent" in low and "not equivalent" not in low:
        return EquivalenceResult(True, "winning strategy equivalent", raw)
    if "error: status change" in low:
        return EquivalenceResult(False, "winning strategy NOT equivalent", raw)
    return EquivalenceResult(
        False,
        f"could not parse SQval output (exit={proc.returncode})",
        raw,
    )


def launch_interactive_validation(extra_args: list[str] | None = None) -> int:
    """Run SQval interactive_validation.py (terminal UI)."""
    root = ensure_sqval()
    script = root / "interactive_validation.py"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [sys.executable, str(script)] + (extra_args or [])
    if sys.platform != "linux" and _docker_ok():
        print(
            "Note: interactive SQval may need Linux solvers; "
            "prefer `qsage cert equivalence --demo` on macOS, "
            "or run inside WSL/Docker.",
            file=sys.stderr,
        )
    return subprocess.call(cmd, cwd=str(root), env=env)


def demo_equivalence_paths() -> dict[str, Path]:
    """Built-in SQval demo files for Hein_04 equivalence (if present)."""
    base = _SQVAL / "intermediate_files" / "hein_04_05_equivalence"
    return {
        "instance1": base / "LN.qdimacs",
        "instance2": base / "SN.qdimacs",
        "certificate": base / "LN_certificate.aag",
        "shared_variables": base / "shared_variables.txt",
    }
