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

**Paper (arXiv:2301.07345 §3):** every encoding is True **iff** Black has a bounded-depth winning strategy — so **pg, cp, and ibign must agree** on SAT/UNSAT for the same `.pg` + depth.

### Ground truth from the paper + re-run of old code

**Hein puzzle 9** (paper §4.1, Fig. 1 caption):

> “Black has a winning strategy of depth **7** starting with \(c_3\).”

Board file `hein_09_4x4-07.pg` has depth 7 and **non-empty** initials (`black: c4,d2`; `white: a1,b4,d1`).

| Encoding | Depth 5 (`…-05.pg`) | Depth 7 (`…-07.pg`) | Matches paper? |
|----------|---------------------|---------------------|----------------|
| **pg** (path / LN-family) | FALSE / UNSAT | TRUE / SAT | yes |
| **ibign** | UNSAT | SAT | yes |
| **cp before fix** (git `b483816^`) | — | **FALSE / UNSAT** | **no** (missed the win) |
| **cp after fix** | FALSE / UNSAT | TRUE / SAT | yes |

Reproduction:

```bash
# broken behaviour (pre-fix file):
git show 'b483816^:legacy/q_encodings/compact_positional.py' \
  > legacy/q_encodings/compact_positional.py
PYTHONPATH=legacy python3 legacy/Q-sage.py -e cp --game_type hex \
  --problem Benchmarks/B-Hex/hein_09_4x4-07.pg \
  --encoding_format 1 --encoding_out /tmp/old_cp.qcir --run 0 --debug -1
solvers/qubi/qubi -v=0 /tmp/old_cp.qcir   # → Result: FALSE  (wrong)

# restore fixed code from main, then:
solvers/qubi/qubi -v=0 …                 # → Result: TRUE   (correct)
```

Also checked with **Bloqqer+CAQE** (Docker): old/wrong `cp` UNSAT, `pg` SAT on the same instance.

### Root cause in the code

Legacy `compact_positional.py` said *“For now assuming the empty board”*:

- path length = only \(\lceil(d+1)/2\rceil\) black **moves** (ignored black **initials**)
- witness cells ∈ black moves only  

On Hein boards with pre-placed stones, a winning path can use initials; the formula became too strong → false **UNSAT**.

**Fix:** path length and witness membership include black initials (same idea as `path_based_goal` / `pg`). Also forbid black moves onto white initials.

**Paper-aligned pattern** for Hein win puzzles: no win at smaller depth (UNSAT), win at the critical depth in the filename (SAT) for **all** of `pg` / `cp` / `ibign`.

## CLI

```bash
qsage encode --problem Benchmarks/B-Hex/hein_04_3x3-05.pg -e pg --out out.qcir
qsage solve --problem Benchmarks/B-Hex/hein_04_3x3-05.pg -e pg --backend qubi
qsage solve --qcir Benchmarks/positional_goldens/pg/hein_04_3x3-05_pg.qcir --backend qubi
```
