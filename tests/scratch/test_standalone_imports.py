"""Scratch paper package must not depend on the legacy/ tree."""

from __future__ import annotations

import ast
from pathlib import Path

SCRATCH = Path(__file__).resolve().parents[2] / "qsage" / "scratch"

# Public + paper code must not import the on-disk legacy tree or old package roots.
FORBIDDEN_PREFIXES = (
    "legacy",
    "q_encodings",
)


def test_no_legacy_tree_imports() -> None:
    for path in SCRATCH.rglob("*.py"):
        if "experimental" in path.parts:
            continue  # pure experiments may evolve freely
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                for bad in FORBIDDEN_PREFIXES:
                    assert not name.startswith(bad), f"{path}: import {name}"
                assert "/legacy" not in name and name != "legacy", path


def test_public_api() -> None:
    from qsage.scratch import encode_grid_files, encode_hex_file

    assert callable(encode_hex_file)
    assert callable(encode_grid_files)
