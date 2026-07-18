# Scratch encodings (`qsage.scratch`)

Readable package that emits **paper-identical QCIR** (same gates as previous
`qsage.encode` / goldens).  **No imports from `legacy/`.**

| API | Paper | Implementation |
|-----|--------|----------------|
| `encode_hex_file` | `pg` (arXiv:2301.07345) | `scratch.paper.path_based` |
| `encode_grid_files` | `bwnib` (arXiv:2303.16949) | `scratch.paper.bwnib_enc` |

## Why this structure

A looser pure rewrite used many more Tseitin gates → worse QuBi times.
The paper algorithms (variable order, gate reuse, nested matrix) are
re-homed under `qsage/scratch/paper/` so:

1. Code lives in the rewrite package (not `import legacy`)
2. **Normalized QCIR equals** previous / paper goldens
3. **Gate count equals** previous → same solver times

## Layout

```text
qsage/scratch/
  hex.py, grid.py          # public API
  paper/                   # paper-identical builders (self-contained)
    vars.py, gates.py      # id dispatch + gate reuse
    less_than.py, adder.py
    path_based.py          # Hex pg
    bwnib_enc.py           # grid bwnib
    parse/                 # domain/problem parser
  parse_bddl.py, parse_pg.py, circuit.py   # helpers / web
  experimental/            # non-identical pure experiments (more gates)
```

## Checks

```bash
pytest tests/scratch/test_qcir_match.py -q
pytest tests/scratch/ -q
```

`test_qcir_match.py` asserts `normalize_qcir(scratch) == normalize_qcir(prev)`
and equal gate counts.
