"""Deprecated: use ``qsage.encode.positional.encode_positional`` (official)."""

from __future__ import annotations

from pathlib import Path


def encode_hex_file(path: str | Path) -> str:
    from qsage.encode.positional import encode_positional

    return encode_positional(Path(path), encoding="pg")
