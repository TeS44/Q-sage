"""Thin wrappers to launch interactive play scripts under legacy/."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_LEGACY = _REPO / "legacy"


def run_hex_interactive(extra_args: list[str] | None = None) -> int:
    """Hex positional play (legacy/interactive_play.py)."""
    script = _LEGACY / "interactive_play.py"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_LEGACY) + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [sys.executable, str(script)] + (extra_args or [])
    return subprocess.call(cmd, cwd=str(_REPO), env=env)


def run_certificate_play(extra_args: list[str] | None = None) -> int:
    """Grid certificate play (legacy/general_interactive_play.py)."""
    script = _LEGACY / "general_interactive_play.py"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_LEGACY) + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [sys.executable, str(script)] + (extra_args or [])
    return subprocess.call(cmd, cwd=str(_REPO), env=env)
