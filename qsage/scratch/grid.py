"""Deprecated: use ``qsage.encode.bwnib.encode_bwnib`` (official)."""

from __future__ import annotations

from pathlib import Path


def encode_grid_files(domain: str | Path, problem: str | Path) -> str:
    from qsage.encode.bwnib import encode_bwnib

    return encode_bwnib(Path(domain), Path(problem))
