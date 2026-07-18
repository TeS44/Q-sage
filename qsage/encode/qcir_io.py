"""Read/write QCIR from legacy gate lists or files."""

from __future__ import annotations

from typing import Any, Iterable, Sequence


def format_gate(gate: Sequence[Any]) -> str:
    """One quantifier or circuit line as printed by legacy encoders."""
    if len(gate) == 1:
        return str(gate[0])
    # ['or'|'and', gate_id, [inputs...]]
    op, gid, inputs = gate[0], gate[1], gate[2]
    return f"{gid} = {op}({', '.join(str(x) for x in inputs)})"


def encoding_to_qcir(
    quantifier_block: Iterable[Sequence[Any]],
    encoding_gates: Iterable[Sequence[Any]],
    output_gate: int,
    *,
    header: str | None = "#QCIR-G14",
) -> str:
    """Build a QCIR string from legacy encoding object fields."""
    parts: list[str] = []
    if header:
        parts.append(header)
    for g in quantifier_block:
        parts.append(format_gate(g))
    parts.append(f"output({output_gate})")
    for g in encoding_gates:
        parts.append(format_gate(g))
    return "\n".join(parts) + "\n"
