# Q-sage

QBF encodings for **2-player board games** (Hex, Harary’s Tic-Tac-Toe, Breakthrough, Connect-c, Domineering, Evader–Pursuer, …).

| What | Command |
|------|---------|
| Parse BDDL / Hex inputs | `qsage parse …` |
| Encode winning strategy (bwnib) | `qsage encode -e bwnib …` |
| Solve with QuBi / Bloqqer+CAQE | `qsage solve …` |
| **Browser play (Hex + grid vs QBF)** | `qsage web` → [Interactive play](#interactive-play) |
| Terminal / certificate play | `qsage play …` |

Papers: [arXiv:2303.16949](https://arxiv.org/abs/2303.16949) · [arXiv:2301.07345](https://arxiv.org/abs/2301.07345) · [certificates](https://doi.org/10.4230/LIPIcs.SAT.2023.24)

Docs: [`docs/DESIGN.md`](docs/DESIGN.md) · [`docs/ISSUES.md`](docs/ISSUES.md) · [`docs/ENCODINGS.md`](docs/ENCODINGS.md) · [`docs/SCRATCH.md`](docs/SCRATCH.md) · [`legacy/README.md`](legacy/README.md)

---

## Requirements

- **Python 3.11+**
- **macOS, Linux, or Windows** (Windows: WSL2 recommended for solvers)

| Optional | Why |
|----------|-----|
| **QuBi** | Fast QCIR solver (native Mac/Linux) |
| **Bloqqer + CAQE** | Paper CNF pipeline (Linux binaries; Docker on Mac/Windows) |
| **Docker Desktop** | Run Linux solvers on Mac/Windows |
| **python-sat** | Certificate interactive play |
| **pyvis** | Optional circuit visualization (legacy only) |

---

## Install

```bash
git clone https://github.com/TeS44/Q-sage.git
cd Q-sage
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# interactive certificate play:
pip install -e ".[play]"
```

**Windows (PowerShell)**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pip install -e ".[play]"
```

### Solvers

**QuBi (recommended on Mac / Linux)**

```bash
bash scripts/build_qubi_macos.sh    # also works on many Linux setups
# → solvers/qubi/qubi
solvers/qubi/qubi -h
```

Needs a C++ compiler, CMake, and GMP (`brew install gmp cmake` on Mac if needed).

**Bloqqer + CAQE**

- **Linux x86_64:** binaries in `tools/Bloqqer/` and `solvers/caqe/`
- **macOS / Windows:** install [Docker Desktop](https://www.docker.com/products/docker-desktop/), start it; `qsage solve --backend bloqqer+caqe` runs them in a `linux/amd64` container

---

## Quick start

```bash
qsage -h
```

### Parse

```bash
# Grid game (BDDL domain + problem)
qsage parse \
  --domain Benchmarks/SAT2023_GDDL/GDDL_models/httt/domain.ig \
  --problem Benchmarks/SAT2023_GDDL/GDDL_models/httt/3x3_3_domino.ig

# Hex board
qsage parse --problem Benchmarks/B-Hex/hein_04_3x3-05.pg
```

### Encode

**Grid (bwnib):**

```bash
qsage encode \
  --domain Benchmarks/SAT2023_GDDL/GDDL_models/httt/domain.ig \
  --problem Benchmarks/SAT2023_GDDL/GDDL_models/httt/3x3_3_domino.ig \
  -e bwnib --normalize --out out.qcir
```

**Hex positional (pg / cp / ibign):**

```bash
qsage encode --problem Benchmarks/B-Hex/hein_04_3x3-05.pg -e pg --out hex.qcir
qsage encode --problem Benchmarks/B-Hex/hein_04_3x3-05.pg -e cp --out hex_cp.qcir
qsage encode --problem Benchmarks/B-Hex/hein_04_3x3-05.pg -e ibign --out hex_ibign.qcir
```

Goldens live under `Benchmarks/positional_goldens/`. Regenerate with  
`PYTHONPATH=legacy python3 scripts/generate_positional_goldens.py`.

### Solve

```bash
# QuBi on a golden QCIR
qsage solve \
  --qcir Benchmarks/SAT2023_GDDL/QBF_instances/httt/3x3_3_domino_bwnib.qcir \
  --backend qubi

# Encode then solve
qsage solve \
  --domain Benchmarks/SAT2023_GDDL/GDDL_models/httt/domain.ig \
  --problem Benchmarks/SAT2023_GDDL/GDDL_models/httt/3x3_3_domino.ig \
  --backend qubi

# Bloqqer + CAQE (Docker on Mac if needed)
qsage solve --qcir path/to/file.qcir --backend bloqqer+caqe --timeout 120
```

`SAT` = first player has a winning strategy of that depth; `UNSAT` = none.

### Paper checks

```bash
# Grid games (SAT 2023 Table 2)
python scripts/run_paper_checks.py --backend qubi

# Positional Hex (Hein sample × pg/cp/ibign)
python scripts/run_positional_paper_checks.py --encoding all
```

---

## Interactive play

### 1. Web UI (start here)

Play Hex and grid games in the browser against **Black (QBF / random)**. You are always **White**.

```bash
# setup (once)
bash scripts/build_qubi_macos.sh       # → solvers/qubi/qubi
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,play]"

# run
qsage web                              # http://127.0.0.1:8765/
# qsage web --port 8765
```

Hard-refresh the browser (`Cmd+Shift+R`) after UI updates.

| | |
|--|--|
| **You / opponent** | White / Black (QBF via QuBi, or random) |
| **Hex** | Honeycomb; Black must connect dark edges in the depth bound |
| **Grid** | HTTT, Domineering, Connect-c, Breakthrough, Evader–Pursuer, … |
| **Depth** | Total plies + your remaining moves on screen |
| **Black opens** | Server plays Black first when the instance requires it |
| **QBF move** | Mid-game residual encode + QuBi (hard timeout kill) |
| **Solve** | QuBi on the original `pg` / `bwnib` instance |
| **Catalog** | `Benchmarks/playable_qbf.json` — regenerate with `python scripts/scan_playable_qbf.py` |

Uses **`qsage.encode`** (paper/legacy parity). API: `/api/domains`, `/api/new`, `/api/move`, `/api/ai`, `/api/solve` (see `tests/web/`).

### 2. Terminal play (optional)

**Hex vs solver** (legacy solver stack — CAQE / Docker / WSL on Mac):

```bash
qsage play hex --problem Benchmarks/B-Hex/hein_04_3x3-05.pg
# qsage play hex -- --player user -e pg
```

![sample_play](https://user-images.githubusercontent.com/37924323/215714804-6fff96c3-21b7-44c1-951f-15587202581f.png)

**Certificate play** (no per-turn QBF; needs `python-sat`):

```bash
pip install -e ".[play]"
qsage play certificate
# qsage play certificate -- --certificate_path path/to/certificate.cnf --player user
```

### 3. Certificates & hybrid validation

Partial certs: first *n* layers from a cert, rest via QBF (DepQBF / QuAbs).

```bash
bash scripts/setup_sqval.sh
qsage cert demo-equivalence
qsage cert demo-partial
qsage cert hybrid --depth 2 --demo
qsage cert generate --qdimacs f.qdimacs --out cert.cnf
bash scripts/setup_depqbf_cert.sh   # optional AIGER path
qsage cert generate --backend depqbf --qdimacs f.qdimacs --out cert.aag
```

Details: [`docs/CERTIFICATES.md`](docs/CERTIFICATES.md) · [SQval](https://github.com/irfansha/SQval) · [DepQBF](https://github.com/lonsing/depqbf)

---

## Layout

```text
qsage/          # package: parse, encode, solve, web, scratch, CLI
  web/          # browser play server + static UI
  scratch/      # standalone rewrite (solver-checked; see docs/SCRATCH.md)
scripts/        # build QuBi, paper checks, playable scan
tests/          # pytest (encode, web, scratch, …)
docs/           # design, issues, encodings, scratch, certificates
Benchmarks/     # games, goldens, playable_qbf.json
solvers/        # QuBi, CAQE, …
tools/          # Bloqqer, converters
testcases/      # certificates / extra inputs
legacy/         # original code (reference — see legacy/README.md)
```

---

## Tests

```bash
pip install -e ".[dev]"   # includes pytest-xdist
pytest tests/ -q -n auto  # parallel
pytest tests/web/ -q      # browser API / play simulations
pytest tests/scratch/ -q  # rewrite vs previous encoders + paper tables
```

---

## Platform cheat sheet

| | macOS | Linux | Windows |
|--|-------|-------|---------|
| Install `qsage` | ✓ | ✓ | ✓ (`py -3.11`) |
| parse / encode | ✓ | ✓ | ✓ |
| QuBi | build script | build / binary | **WSL2** |
| Bloqqer+CAQE | Docker | native | Docker or WSL2 |
| **`qsage web` (browser play)** | ✓ + QuBi | ✓ + QuBi | ✓ + QuBi (WSL2 ok) |
| Terminal Hex play | solvers via WSL/Docker if needed | ✓ | WSL2 |
| Certificate play | ✓ + python-sat | ✓ | ✓ + python-sat |

---

## Legacy code

Everything that used to live at the repo root (`Q-sage.py`, old `parse/`, `q_encodings/`, interactive scripts, …) is under **`legacy/`**.

```bash
# Example: old encoder CLI
export PYTHONPATH="$PWD/legacy"
python legacy/Q-sage.py -h
```

See [`legacy/README.md`](legacy/README.md). Prefer `qsage` for new work.

---

## Authors

```text
Irfansha Shaik — Aarhus
```

License: MIT (`LICENSE`).
