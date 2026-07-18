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
pytest tests/scratch/ -q
# paper tables (Hex + grid Table 2):
pytest tests/scratch/test_paper_tables.py -q
```

**Correctness (semantic, not QCIR text):**
- Soft single-hot placement (∀ multi-hot cannot falsify)
- Hex: paper Hein depth pairs (arXiv:2301.07345)
- Grid: HTTT / Connect-2 / Domineering / most of Table 2 (arXiv:2303.16949)
- Breakthrough B/BSP: 3 paper rows still xfail vs nested bwnib
