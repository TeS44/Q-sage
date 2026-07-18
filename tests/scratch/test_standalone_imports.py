"""scratch must not import encode/parse/legacy."""

from __future__ import annotations

import ast
from pathlib import Path

SCRATCH = Path(__file__).resolve().parents[2] / "qsage" / "scratch"

FORBIDDEN = (
    "qsage.encode",
    "qsage.parse",
    "legacy",
    "q_encodings",
)


def test_no_forbidden_imports() -> None:
    for path in SCRATCH.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for bad in FORBIDDEN:
                        assert bad not in alias.name, f"{path}: import {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for bad in FORBIDDEN:
                    assert not mod.startswith(bad), f"{path}: from {mod}"
                    assert bad not in mod, f"{path}: from {mod}"


def test_public_api() -> None:
    from qsage.scratch import encode_grid_files, encode_hex_file

    assert callable(encode_hex_file)
    assert callable(encode_grid_files)
