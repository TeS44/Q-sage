# Encoding keep-list (issue #6)

Only encodings needed for paper reproduction stay in scope for the rewrite.

## Grid / BDDL — SAT 2023 (arXiv:2303.16949)

| Name | Legacy `-e` | Status in `qsage` |
|------|-------------|-------------------|
| Black–white nested index-based | `bwnib` | **Supported** (`qsage encode -e bwnib`) |
| Completed forced prop. variant | `cfbwnib` | Optional; not required for Table 2 |

Goldens: `Benchmarks/SAT2023_GDDL/QBF_instances/**/*_bwnib.qcir`

## Positional / Hex — arXiv:2301.07345

| Paper family | Legacy `-e` | `qsage` status |
|--------------|-------------|----------------|
| Lifted neighbor / path (LN) | `pg`, `ibign` | **Supported** + goldens |
| Compact / stateless (SN) | `cp` | **Supported** + goldens |
| Explicit goal / other | `eg`, `ntpg`, … | Still only in `legacy/` |

Goldens: `Benchmarks/positional_goldens/{pg,cp,ibign}/` (regenerate: `scripts/generate_positional_goldens.py`).  
Solver notes: `docs/POSITIONAL_RESULTS.md`.

## Do not port (unless a paper table needs them)

`dnib`, `ttt` spikes, experiment-only scripts under `legacy/other_scripts/`.

## How to regenerate goldens from legacy

```bash
export PYTHONPATH="$PWD/legacy${PYTHONPATH:+:$PYTHONPATH}"
python legacy/Q-sage.py --game_type general -e bwnib \
  --ib_domain … --ib_problem … \
  --encoding_format 1 --encoding_out path.qcir --run 0
```
