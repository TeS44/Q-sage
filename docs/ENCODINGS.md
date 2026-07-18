# Encoding keep-list

Official implementations live under **`qsage.encode`** (`qsage/encode/paper/` for the builders).  
`legacy/` is reference only (except Hex `cp` / `ibign` until fully ported).

## Grid / BDDL — SAT 2023 (arXiv:2303.16949)

| Name | CLI `-e` | Implementation |
|------|----------|----------------|
| Black–white nested index-based | `bwnib` | **`qsage.encode.paper`** (no `legacy/` import) |

Goldens: `Benchmarks/SAT2023_GDDL/QBF_instances/**/*_bwnib.qcir`  
Tests: `tests/encode/test_bwnib_goldens.py`, `tests/scratch/test_qcir_match.py`

## Positional / Hex — arXiv:2301.07345

| Paper family | CLI `-e` | Implementation |
|--------------|----------|----------------|
| Path / LN | `pg` | **`qsage.encode.paper`** |
| Compact / SN | `cp` | `legacy/` (via `encode_positional`) |
| Nested implicit | `ibign` | `legacy/` (via `encode_positional`) |

Goldens: `Benchmarks/positional_goldens/{pg,cp,ibign}/`

## Web

`qsage web` encodes mid-game / solve with `encode_bwnib` and `encode_positional` — same official path as CLI.

## Regenerating goldens (reference)

```bash
export PYTHONPATH="$PWD/legacy${PYTHONPATH:+:$PYTHONPATH}"
python legacy/Q-sage.py --game_type general -e bwnib \
  --ib_domain … --ib_problem … \
  --encoding_format 1 --encoding_out path.qcir --run 0
```
