"""Small helpers shared by BDDL and positional parsers."""

from __future__ import annotations

from pathlib import Path

from lark import Lark


def strip_comments(text: str) -> str:
    """Drop blank lines and % comments; keep one trailing newline."""
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        lines.append(line)
    body = "\n".join(lines)
    return body + "\n" if body else ""


def load_text(source: str | Path) -> tuple[str, str | None]:
    """Load file text, or treat a multi-line string as the body."""
    if isinstance(source, Path):
        return source.read_text(encoding="utf-8"), str(source)
    if isinstance(source, str) and "\n" not in source:
        path = Path(source)
        if path.is_file():
            return path.read_text(encoding="utf-8"), str(path)
    return str(source), None


def make_lark(grammar_path: Path) -> Lark:
    return Lark(
        grammar_path.read_text(encoding="utf-8"),
        start="start",
        parser="lalr",
        maybe_placeholders=False,
    )
