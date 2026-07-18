"""Normalize QCIR text for comparison (comments/whitespace ignored)."""

from __future__ import annotations


def normalize_qcir(text: str) -> str:
    """
    Canonical form for golden tests.

    - drop blank lines and # comments (including #QCIR-G14)
    - strip surrounding whitespace per line
    """
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines) + ("\n" if lines else "")
