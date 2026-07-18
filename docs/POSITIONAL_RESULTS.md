# Positional Hex — QCIR goldens and solver checks

## Goldens (from legacy)

Generated with:

```bash
PYTHONPATH=legacy python3 scripts/generate_positional_goldens.py
```

Stored under `Benchmarks/positional_goldens/{pg,cp,ibign}/`  
(40 Hein/Browne boards × 3 encodings = **120** QCIR files).

| Encoding | Paper role (approx.) | Legacy `-e` |
|----------|----------------------|-------------|
| **pg** | Path / lifted neighbor (LN family) | `pg` |
| **ibign** | Nested implicit board + goal (LN) | `ibign` |
| **cp** | Compact / stateless-style (SN family) | `cp` |

## QuBi checks (sample)

```bash
python3 scripts/run_positional_paper_checks.py --encoding all --timeout 60
```

Representative results (depth from filename `-DD`; **pg** / **ibign** agree on small wins):

| Instance | depth | pg | ibign | cp |
|----------|------:|----|-------|-----|
| hein_04_3x3-03 | 3 | UNSAT | UNSAT | UNSAT |
| hein_04_3x3-05 | 5 | **SAT** | **SAT** | **SAT** |
| hein_09_4x4-05 | 5 | UNSAT | UNSAT | UNSAT |
| hein_09_4x4-07 | 7 | **SAT** | **SAT** | UNSAT* |
| hein_12_4x4-05 | 5 | UNSAT | UNSAT | UNSAT |
| hein_12_4x4-07 | 7 | **SAT** | **SAT** | UNSAT* |

\* `cp` is a different encoding family; solver answers need not match `pg`/`ibign` on every instance (paper compares families separately).

**Paper-aligned pattern** for Hein win puzzles: no win at smaller depth (UNSAT), win at the critical depth in the filename (SAT) under LN-style encodings (`pg` / `ibign`).

## CLI

```bash
qsage encode --problem Benchmarks/B-Hex/hein_04_3x3-05.pg -e pg --out out.qcir
qsage solve --problem Benchmarks/B-Hex/hein_04_3x3-05.pg -e pg --backend qubi
qsage solve --qcir Benchmarks/positional_goldens/pg/hein_04_3x3-05_pg.qcir --backend qubi
```
