# From-scratch encodings (`qsage.scratch`)

## Why two encode trees?

| | `qsage.encode` | `qsage.scratch` |
|--|----------------|-----------------|
| Goal | Match paper/legacy **QCIR text** (normalize) | **Readable** rewrite |
| Correctness | Golden QCIR equality | QBF **SAT/UNSAT** on benchmarks |
| Dependencies | May use legacy | **Standalone** (stdlib only) |

Do not delete or “simplify” `qsage.encode` while developing scratch.

## Semantics (scratch)

### Hex (`encode_hex_file`)

Black (∃) vs White (∀) on a positional board. After `depth` plies, Black
wins if the final Black stones connect `start_border` to `end_border`
along `#neighbours`.

### Grid (`encode_grid_files`)

Occupy-only games (HTTT-style). Black wins if some `#blackgoal` shape is
filled with Black at the horizon.

## Tests

```bash
pytest tests/scratch/ -q -n auto
```

Heavy tests need QuBi (`solvers/qubi/qubi`).
