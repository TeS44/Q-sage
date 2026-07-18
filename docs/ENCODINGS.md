# Encoding keep-list (issue #6)

Only encodings needed for paper reproduction stay in scope for the rewrite.

## Grid / BDDL — SAT 2023 (arXiv:2303.16949)

| Name | Legacy `-e` | Status in `qsage` |
|------|-------------|-------------------|
| Black–white nested index-based | `bwnib` | **Supported** (`qsage encode -e bwnib`) |
| Completed forced prop. variant | `cfbwnib` | Optional; not required for Table 2 |

Goldens: `Benchmarks/SAT2023_GDDL/QBF_instances/**/*_bwnib.qcir`

## Positional / Hex — arXiv:2301.07345

| Paper family | Likely legacy `-e` | Priority |
|--------------|--------------------|----------|
| Lifted neighbor / path (LN) | `pg`, `ibign` | High — next port |
| Compact / stateless neighbor (SN) | `cp`, `ntpg` | High |
| Explicit goal lifted (LA) | `eg` / related | Medium |
| Stateless explicit (SA) | various | Medium |

These still live only under `legacy/q_encodings/`. Port when working on issue #7.

## Do not port (unless a paper table needs them)

`dnib`, `ttt` spikes, experiment-only scripts under `legacy/other_scripts/`.

## How to regenerate goldens from legacy

```bash
export PYTHONPATH="$PWD/legacy${PYTHONPATH:+:$PYTHONPATH}"
python legacy/Q-sage.py --game_type general -e bwnib \
  --ib_domain … --ib_problem … \
  --encoding_format 1 --encoding_out path.qcir --run 0
```
