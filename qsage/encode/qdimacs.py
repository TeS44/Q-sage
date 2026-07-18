"""QCIR → QDIMACS (Tseitin), adapted from utils/qcir_to_qdimacs_transformer.py."""

from __future__ import annotations

from qsage.encode.normalize import normalize_qcir


def _neg(var: str) -> str:
    return var[1:] if var.startswith("-") else f"-{var}"


def qcir_to_qdimacs(qcir_text: str) -> str:
    """
    Convert a QCIR circuit to QDIMACS CNF with quantifier prefix.

    Intermediate gates become existential variables with Tseitin clauses.
    """
    # Work on non-comment lines; keep order of quantifier blocks.
    lines = [
        ln.strip()
        for ln in qcir_text.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]

    matrix: list[tuple[str, list[str]]] = []  # ('e'|'a', vars)
    output_gate: str | None = None
    gates: list[tuple[str, str, list[str]]] = []  # (and|or, name, inputs)
    level: dict[str, int] = {}

    prev_q = ""
    cur_level = 0
    for line in lines:
        low = line.replace(" ", "")
        if low.startswith("exists(") or low.startswith("forall("):
            if low.startswith("exists("):
                qtype, rest = "e", low[len("exists(") :]
            else:
                qtype, rest = "a", low[len("forall(") :]
            vars_ = [v for v in rest.rstrip(")").split(",") if v]
            if prev_q == qtype and matrix:
                matrix[-1][1].extend(vars_)
            else:
                cur_level += 1
                matrix.append((qtype, list(vars_)))
                prev_q = qtype
            for v in vars_:
                level[v] = cur_level
        elif low.startswith("output("):
            output_gate = low[len("output(") :].rstrip(")")
        elif "=" in low and ("or(" in low or "and(" in low):
            left, right = low.split("=", 1)
            if right.startswith("or("):
                gtype = "or"
                body = right[len("or(") :].rstrip(")")
            else:
                gtype = "and"
                body = right[len("and(") :].rstrip(")")
            inputs = [v for v in body.split(",") if v]
            gates.append((gtype, left, inputs))
            # level of gate = max level of inputs (approx; matches legacy spirit)
            mx = 1
            for v in inputs:
                key = v[1:] if v.startswith("-") else v
                mx = max(mx, level.get(key, 1))
            level[left] = mx

    if output_gate is None:
        raise ValueError("QCIR missing output(...)")

    clauses: list[list[str]] = []
    for gtype, name, inputs in gates:
        if gtype == "and":
            for v in inputs:
                clauses.append([v, _neg(name)])
            clauses.append([_neg(v) for v in inputs] + [name])
        else:  # or
            for v in inputs:
                clauses.append([_neg(v), name])
            clauses.append(list(inputs) + [_neg(name)])

    # unit clause: force output true
    clauses.append([output_gate])

    # count variables: max absolute integer id
    def abs_id(tok: str) -> int:
        return int(tok[1:] if tok.startswith("-") else tok)

    max_var = 0
    for _, vars_ in matrix:
        for v in vars_:
            max_var = max(max_var, abs_id(v))
    for _, name, inputs in gates:
        max_var = max(max_var, abs_id(name))
        for v in inputs:
            max_var = max(max_var, abs_id(v))

    # append gate vars as final existential block if not already quantified
    quantified = set()
    for _, vars_ in matrix:
        quantified.update(vars_)
    extra = [str(i) for i in range(1, max_var + 1) if str(i) not in quantified]
    # only gate ids typically missing — leave as-is; Tseitin names are already in level
    gate_names = [name for _, name, _ in gates if name not in quantified]
    if gate_names:
        if matrix and matrix[-1][0] == "e":
            matrix[-1][1].extend(gate_names)
        else:
            matrix.append(("e", gate_names))

    out: list[str] = [f"p cnf {max_var} {len(clauses)}"]
    for qtype, vars_ in matrix:
        if not vars_:
            continue
        out.append(f"{qtype} " + " ".join(vars_) + " 0")
    for cl in clauses:
        out.append(" ".join(cl) + " 0")
    return "\n".join(out) + "\n"


def qcir_file_to_qdimacs(path: str) -> str:
    from pathlib import Path

    return qcir_to_qdimacs(Path(path).read_text(encoding="utf-8"))
