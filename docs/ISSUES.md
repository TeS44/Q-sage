# Issue backlog (rewrite)

Priority rule: **encoding output parity first**; solver correctness and polish later.

All items below are open on GitHub: [TeS44/Q-sage issues](https://github.com/TeS44/Q-sage/issues).

---

## P0 — encoding same as legacy (do first)

### #4 Port `bwnib` and match golden QCIR (normalized)

**Why first:** Grid paper (arXiv:2303.16949) encoding; 102 ready goldens already in-repo.

**Goldens:** `Benchmarks/SAT2023_GDDL/QBF_instances/{httt,B,BSP,C4,D,EP,EP-dual,hex}/*_bwnib.qcir`

**Done when:**
- [x] `qsage encode --encoding bwnib …` matches goldens under **normalize**
- [x] Fast pytest suite over all `*_bwnib.qcir` (no solver) — **103 passed**
- [x] Small student-facing API (`qsage/encode/bwnib.py`); body still calls legacy for stability

**Status:** Working on `main`. Rewrite pure bwnib later without changing tests.

**Parent:** #2

---

### #5 In-memory QCIR builder + QDIMACS conversion

**Why:** Hot path must not write/read temp files; Bloqqer/CAQE need QDIMACS.

**Done when:**
- [x] QCIR string in process (`encoding_to_qcir` / `encode_bwnib` return value)
- [x] Pure-Python `qcir_to_qdimacs` (first cut; tighten vs legacy transformer later)
- [x] Shared `normalize_qcir` for #4 tests
- [ ] Drop leftover write of `intermediate_files/combined_input.ig` when native parse/encode lands

**Parent:** #2 · **Blocks:** #8 solvers

---

### #6 Freeze paper encoding keep-list + baseline harness

**Why:** Avoid porting unused `-e` variants.

**Done when:**
- Short table in this file or DESIGN: paper name → legacy `-e` → golden source.
- Confirmed list for positional paper (likely `pg`, `cp`, `ibign`; maybe `eg`/`ew`).
- Script or pytest that can regenerate goldens from legacy *once* (when pyvis optional) for non-bwnib encodings.

**Parent:** #2

---

## P1 — remaining paper encodings (after bwnib)

### #7 Port positional paper encodings with golden tests

Hex / HTTT positional encodings needed for arXiv:2301.07345 experiments.

**Candidates:** `pg`, `cp`, `ibign` (confirm in #6).

**Done when:** same normalized-QCIR approach as #4; small modules, little duplication.

**Depends on:** #4, #5, #6

---

## P2 — solvers, certificates, CLI (after encodings match)

### #8 Solver backends: Bloqqer + CAQE, Pedant, QuBi

Easy install story; wrap existing `tools/` binaries first if needed; PyQBF optional later.

**Depends on:** #5 · **Parent:** #2

---

### #9 Winning-strategy certificates (full + partial)

Certificate generation/use for interactive play without re-solving every move  
(ref: [SAT 2023 certificates](https://doi.org/10.4230/LIPIcs.SAT.2023.24)).

**Depends on:** #8 · **Feeds:** #3

---

### #10 Split CLI by game type

Separate simple interfaces: grid/BDDL vs positional Hex (no mega-flag soup).

**Depends on:** #4, #7 · **Parent:** #2

---

## P3 — bugs / cleanup (after parity; do not block encoding work)

### #11 Legacy soft-fail: `pyvis` import required for any run

`Q-sage.py` imports `utils.circuit_visualizer` → `pyvis` even when `--qcir_viz 0`.  
Makes golden regeneration and student setup harder.

**Fix later:** lazy import only when visualization is requested.

**Status (2026-07-18):** Partially fixed — `Q-sage.py` lazy-imports pyvis only for `--qcir_viz 1`. Still needs `networkx` via stuttering_bounds.

---

### #12 Dual `.pg` formats

- Real positional boards: `#positions`, `#neighbours`, … (`Benchmarks/B-Hex/`)
- GDDL-style problems misnamed `.pg` under `GDDL_models/hex/` (`#boardsize`, `#blackgoal`, …)

**Status:** parsers handle both; document and auto-detect in CLI (`qsage parse` already peeks at headers).

---

### #13 Encoding post-parse transforms as explicit steps

Legacy folds into parse:
- implicit index bounds (`compute_index_bounds`)
- white precondition padding to max length

New parse is clean AST only. Reimplement these as named transforms in `encode/` so students can see them (and so #4 parity holds).

---

### #14 Domineering / empty goals and `#blackturn second`

Handled in new parser; verify encoding (#4) treats `False` goals and second-player turn like legacy.

---

## Already open (keep as-is)

| # | Title | Priority relative to encoding |
|---|--------|-------------------------------|
| **#1** | Grammar-based parsing | Largely done in `qsage/parse/`; close when wired into encode path |
| **#2** | Modular rewrite | Parent epic; implement via #4–#10 |
| **#3** | Pretty interactive UI | **After** #4–#5 (and ideally #9) so UI is not built on slow file I/O |

---

## Suggested GitHub open order

1. Open **#4**, **#5**, **#6** now (P0).  
2. Open **#7** after bwnib green.  
3. Open **#8–#10** when encodings stable.  
4. Open **#11–#14** as cleanup tickets (P3).  
5. Leave **#3** for last among user-facing features.

---

## Working rule for contributors / students

```text
1. Match encoding (QCIR normalize tests)   ← current focus
2. Then QDIMACS + solvers
3. Then certificates + play API
4. Then UI / install polish / multi-piece
```

Do not expand scope with new encodings or UI polish until #4 is green.
