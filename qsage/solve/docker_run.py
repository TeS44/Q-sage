"""Run Linux x86_64 solver binaries via Docker (macOS host)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def docker_available() -> bool:
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
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False


def run_in_linux(
    cmd: str,
    *,
    timeout: int = 120,
    workdir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """
    Execute a bash command in ubuntu:22.04 linux/amd64 with the repo mounted at /work.
    """
    root = workdir or _REPO
    full = (
        "export DEBIAN_FRONTEND=noninteractive; "
        "apt-get update -qq >/dev/null 2>&1; "
        "apt-get install -y -qq libgomp1 libgcc-s1 >/dev/null 2>&1; "
        + cmd
    )
    return subprocess.run(
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
            full,
        ],
        capture_output=True,
        text=True,
        timeout=timeout + 60,  # allow apt overhead
    )
