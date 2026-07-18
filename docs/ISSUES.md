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

**Status:** Working on `main` via `legacy/` encoder. Pure rewrite later without changing tests.

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
- [x] Table in `docs/ENCODINGS.md`
- [x] Confirmed grid: **bwnib**; positional candidates listed for #7
- [x] Regenerate notes via `legacy/Q-sage.py`

**Parent:** #2

---

## P1 — remaining paper encodings (after bwnib)

### #7 Port positional paper encodings with golden tests

**Status:** Done — goldens + `pg`/`cp`/`ibign`, agreement tests, cp black-initial fix.

**Depends on:** #4, #5, #6

---

## P2 — solvers, certificates, CLI (after encodings match)

### #8 Solver backends: Bloqqer + CAQE, Pedant, QuBi

**Status:** QuBi + Bloqqer+CAQE done. Pedant still optional for cert generation.

**Depends on:** #5 · **Parent:** #2

---

### #9 Winning-strategy certificates (full + partial)

**Status:** Architecture centered on **partial certs + hybrid play**:
- SQval: equivalence, static/dynamic/hybrid validation
- `qsage cert hybrid --depth N` (cert prefix, DepQBF/QuAbs tail)
- `qsage cert demo-partial` (shared-var partial strategy)
- `qsage cert generate` (Pedant CNF; DepQBF+QRPcert AIGER)
- **DepQBF 6.03 + QRPcert 1.0.1 from official source:** `scripts/setup_depqbf_cert.sh`
  ([lonsing/depqbf](https://github.com/lonsing/depqbf), [JKU QRPcert](https://fmv.jku.at/qrpcert/))

Still open: truncated partial-AIGER export; web mid-game hybrid (#3).

**Depends on:** #8 · **Feeds:** #3

---

### #10 Split CLI by game type

**Status:** Done for current surface (`parse|encode|solve|play|cert|web`).

**Depends on:** #4, #7 · **Parent:** #2

---

## P3 — bugs / cleanup

### #11 pyvis optional

**Status:** Fixed in `legacy/Q-sage.py` (lazy import). `networkx` still required for legacy encode.

### #12 Dual `.pg` formats

**Status:** Done in `qsage parse` + README.

### #13 Explicit encode transforms

Still inside `legacy/` combine for bwnib parity; re-home on pure rewrite.

### #14 Domineering / `#blackturn second`

Lark parser + goldens cover these.

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
