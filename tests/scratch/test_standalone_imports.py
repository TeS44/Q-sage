"""Official encode.paper must not import legacy/."""

from __future__ import annotations

import ast
from pathlib import Path

PAPER = Path(__file__).resolve().parents[2] / "qsage" / "encode" / "paper"


def test_paper_no_legacy_imports() -> None:
    for path in PAPER.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                assert not name.startswith("legacy"), f"{path}: {name}"
                assert not name.startswith("q_encodings"), f"{path}: {name}"


def test_public_encode_api() -> None:
    from qsage.encode import encode_bwnib, encode_positional

    assert callable(encode_bwnib)
    assert callable(encode_positional)
