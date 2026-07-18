# Certificates and hybrid interactive play (issue #9)

Full **and partial** winning-strategy certificates are what make QBF game encodings
**scalable to play and validate** — not just solvable once offline.

Paper: [Validation of QBF Encodings with Winning Strategies](https://drops.dagstuhl.de/storage/00lipics/lipics-vol271-sat2023/LIPIcs.SAT.2023.24/LIPIcs.SAT.2023.24.pdf)  
(LIPIcs SAT 2023)

Tooling we wrap (do **not** reimplement): **[SQval](https://github.com/irfansha/SQval)** · DepQBF · Pedant · (optional) qrpcert.

---

## Why partial certificates matter

A full AIGER/CNF certificate encodes a winning strategy for **every** quantifier
block (every move layer). For deeper games that grows quickly.

| Artifact | What it gives you | Cost |
|----------|-------------------|------|
| **Full certificate** | Static play for the whole game without a QBF solver | Large; hard to generate for deep instances |
| **Partial certificate** | Correct strategy for the **first *n* layers** only | Much cheaper to generate and store |
| **DepQBF `--qdo` / QuAbs `--partial-assignment`** | One-layer responses on demand | No cert file; solver call each turn |

**Hybrid interactive play** combines them:

```text
layers 0 .. hybrid_depth-1  →  answer from (partial) certificate  (SAT assumptions)
layers hybrid_depth .. end  →  answer from DepQBF / QuAbs         (QBF solve with assumptions)
```

That is the path to **scalable generation + hybrid interactive play**:
generate only as much strategy as you need offline; fall back to a DepQBF-class
solver for the rest of the game tree.

SQval already wires this in `interactive_validation.py`
(`--validation hybrid --hybrid_depth N`). Use it via `qsage cert hybrid`.

---

## Architecture (generation → play)

```text
  QDIMACS / QCIR encoding
           │
           ▼
  ┌────────────────────────────────────────────────────┐
  │  Certificate generators (DepQBF-like stack)        │
  │                                                    │
  │  • DepQBF --trace + qrpcert  → full AIGER strategy │
  │  • Pedant --cnf              → CNF strategy        │
  │  • Partial: only outer blocks / truncated cert     │
  │  • DepQBF --qdo              → per-layer partial   │
  │    assignment (no cert file; hybrid tail)          │
  └────────────────────────────────────────────────────┘
           │
           ▼
  ┌────────────────────────────────────────────────────┐
  │  SQval play / validation                           │
  │                                                    │
  │  static   — cert only (full or partial)            │
  │  dynamic  — DepQBF / QuAbs every winning move      │
  │  hybrid   — cert for first n layers, solver rest   │
  │  equivalence — same winning strategy on shared vars │
  └────────────────────────────────────────────────────┘
           │
           ▼
  qsage play certificate · qsage cert · web (future)
```

### Generators in this repo

| Tool | Binary / path | Role |
|------|---------------|------|
| **DepQBF** (partial assign) | `third_party/SQval/solvers/depqbf/depqbf` (Linux ELF) | Dynamic / hybrid tail via `--qdo` |
| **QuAbs** | `third_party/SQval/solvers/quabs/quabs` | Same for QCIR (`--partial-assignment`) |
| **Pedant** | `solvers/pedant-solver/pedant` (Linux ELF) | CNF cert: `pedant inst.qdimacs --cnf out.cnf` |
| **DepQBF + qrpcert** | legacy path `solvers/depqbf_cert/` (if installed) | Trace → AIGER (`--aiger-ascii`) |

On **macOS / Windows**, Linux ELFs run under **Docker** (`linux/amd64`), same pattern as Bloqqer+CAQE and SQval equivalence demos.

---

## `qsage` commands

```bash
bash scripts/setup_sqval.sh    # third_party/SQval + python-sat

# --- Equivalence (full/partial shared strategy) ---
qsage cert demo-equivalence
# Hein_12 partial shared-var demo (BOW_0 ↔ BOW_1):
qsage cert demo-partial
qsage cert equivalence --instance1 … --instance2 … --certificate … --shared-variables …

# --- Interactive / hybrid validation (SQval) ---
# static: full cert only
qsage cert validate -- --certificate path.aag --instance path.qcir --status sat --player random

# hybrid: cert for first N quantifier layers, DepQBF/QuAbs after
qsage cert hybrid --depth 2 --demo          # uses SQval Hein_04 SAT demo files
qsage cert hybrid --depth 2 \
  --instance path.qcir --certificate path.aag --status sat --player random

# dynamic: solver every move (needs Linux DepQBF/QuAbs — Docker or WSL)
qsage cert validate -- --instance path.qcir --status sat --player user --validation dynamic

# --- Generate a certificate (Pedant CNF; Docker on Mac) ---
qsage cert generate --qdimacs path.qdimacs --out cert.cnf
# DepQBF+qrpcert AIGER path is documented; requires depqbf_cert install (see below)
```

### Grid play without SQval (legacy CNF cert)

```bash
qsage play certificate
# python-sat only; works natively on Mac/Linux/Windows
```

---

## Hybrid depth (practical tips)

- `hybrid_depth` is a **prefix quantifier-layer index** in the QBF (not board ply
  alone — one “time step” may be one or more blocks depending on encoding).
- Small depths (1–3) already give a big UX win: opening book from a small cert,
  mid/endgame from DepQBF.
- If hybrid tail calls fail on macOS, prefer:
  - static cert-only for demos, or
  - Docker/WSL so SQval’s bundled DepQBF/QuAbs can run.

SQval help still labels hybrid as “TODO” in places; the **layer switch is
implemented** (`k < hybrid_depth` → cert, else solver). Q-sage treats hybrid as
the supported scalable path.

---

## Equivalence and *partial* shared strategies

Winning-strategy **equivalence** (SQval) checks whether a certificate for Q1
also wins for Q2 on a set of **shared variables**. That models:

- two encodings of the same game (LN vs SN, etc.), or
- **partial** strategies that only fix an opening (shared outer vars) —
  see `Hein_12_07_partial_equivalence` under SQval’s `intermediate_files/`.

```bash
qsage cert demo-partial   # BOW_0 cert vs BOW_1 (and notes directionality)
```

---

## DepQBF + QRPcert (full AIGER) — build from source

Official sources (GPLv3) — this is the **right version** for QRP → AIGER certs:

| Component | Source | Notes |
|-----------|--------|--------|
| **DepQBF 6.03** | [github.com/lonsing/depqbf](https://github.com/lonsing/depqbf) · [lonsing.github.io/depqbf](https://lonsing.github.io/depqbf/) | `--trace` QRP + `--qdo` partial assign |
| **QRPcert 1.0.1** | [fmv.jku.at/qrpcert](https://fmv.jku.at/qrpcert/) (`qrpcert-1.0.1.tar.gz`) | QRP → AIGER Skolem/Herbrand |
| **PicoSAT / Nenofex** | pulled by DepQBF `compile.sh` | DepQBF 6.x oracles |
| **QBFcert 1.0** (optional) | [fmv.jku.at/qbfcert](https://fmv.jku.at/qbfcert/) | Linux ELF bundle of the whole toolchain |

One-shot install (native on **macOS arm64** and Linux):

```bash
bash scripts/setup_depqbf_cert.sh
# → solvers/depqbf_cert/{depqbf,qrpcert}
```

Pipeline (DepQBF 6.x needs the extra flags for valid traces):

```bash
depqbf --trace --dep-man=simple --no-lazy-qpup instance.qdimacs > trace.qrp
qrpcert --aiger-ascii --simplify trace.qrp > certificate.aag

# or:
qsage cert generate --backend depqbf --qdimacs instance.qdimacs --out cert.aag
```

Legacy runner: `legacy/run/run_depqbf_cert.py` (same binary layout under
`solvers/depqbf_cert/`). Pedant remains an alternative CNF path
(`qsage cert generate --backend pedant`).

Paper: Niemetz, Preiner, Lonsing, Seidl, Biere — *Resolution-Based Certificate
Extraction for QBF* (SAT 2012); framework page [QBFcert](https://fmv.jku.at/qbfcert/).

---

## Repo map

| Piece | Location |
|-------|----------|
| SQval wrappers | `qsage/strategy/sqval.py` |
| DepQBF / Pedant cert gen | `qsage/strategy/depqbf.py` |
| Build DepQBF+QRPcert | `scripts/setup_depqbf_cert.sh` |
| Binaries (after setup) | `solvers/depqbf_cert/` |
| CLI | `qsage cert …` |
| Sample grid CNF certs | `testcases/index_general_certificates/` |
| SQval demos (AIGER + QDIMACS) | `third_party/SQval/intermediate_files/` |
| Legacy DepQBF cert runner | `legacy/run/run_depqbf_cert.py` |
| Legacy Pedant cert runner | `legacy/run/run_pedant.py` |

---

## Still open

- First-class **partial AIGER** export (truncate quantifier depth at generation time).
- Web UI mid-game hybrid play (issue #3) — reuse the same hybrid_depth model.
