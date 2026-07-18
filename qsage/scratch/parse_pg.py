"""
Minimal positional / Hex ``.pg`` reader (no Lark, no qsage.parse).

Recognises the benchmark format used under ``Benchmarks/B-Hex/``::

    #blackinitials
    a1
    #whiteinitials
    b1
    #times
    t1 t2 t3
    #blackturns
    t1 t3
    #positions
    a1 a2 ...
    #neighbours
    a1 b1 a2
    #startboarder
    a1 b1
    #endboarder
    a3 b3
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HexGame:
    positions: list[str]
    black_initials: list[str]
    white_initials: list[str]
    times: list[str]
    black_turns: list[str]
    neighbours: dict[str, list[str]] = field(default_factory=dict)
    start_border: list[str] = field(default_factory=list)
    end_border: list[str] = field(default_factory=list)
    path: str | None = None

    @property
    def depth(self) -> int:
        return len(self.times)


def load_pg(path: str | Path) -> HexGame:
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    sections: dict[str, list[str]] = {}
    cur: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        if line.startswith("#"):
            cur = line.split()[0].lower()
            sections.setdefault(cur, [])
            rest = line[len(line.split()[0]) :].strip()
            if rest:
                sections[cur].extend(rest.split())
            continue
        if cur is None:
            continue
        sections[cur].extend(line.split())

    def block(key: str) -> list[str]:
        for k, v in sections.items():
            if k.replace("#", "") == key.replace("#", ""):
                return list(v)
        return []

    # neighbours: lines were flattened — re-read for multi-token lines
    neighbours: dict[str, list[str]] = {}
    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        if line.startswith("#"):
            cur = line.split()[0].lower()
            continue
        if cur in ("#neighbours", "neighbours"):
            parts = line.split()
            if parts:
                neighbours[parts[0]] = parts[1:]

    positions = block("positions")
    if not positions:
        raise ValueError(f"{path}: missing #positions")

    return HexGame(
        positions=positions,
        black_initials=block("blackinitials"),
        white_initials=block("whiteinitials"),
        times=block("times"),
        black_turns=block("blackturns"),
        neighbours=neighbours,
        start_border=block("startboarder") or block("startborder"),
        end_border=block("endboarder") or block("endborder"),
        path=str(path),
    )
