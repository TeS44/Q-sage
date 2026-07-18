# `qsage.scratch` — standalone from-scratch encodings

**Self-contained.** Does not import `qsage.encode`, `qsage.parse`, or `legacy`.

| Tree | Purpose |
|------|---------|
| `qsage/encode/` | Legacy/paper QCIR match (normalize equality) — **kept** |
| `qsage/scratch/` | New simple encoders — **correctness via solvers** |

```text
scratch/
  circuit.py     # QCIR builder
  parse_pg.py    # Hex .pg files
  parse_bddl.py  # grid problem files
  hex.py         # path-win Hex QBF
  grid.py        # occupy + black-goal shapes
```

```bash
pytest tests/scratch/ -q -n auto
```
