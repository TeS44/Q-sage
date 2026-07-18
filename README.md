# Q-sage

QBF encodings for **2-player board games** (Hex, Harary’s Tic-Tac-Toe, Breakthrough, Connect-c, Domineering, Evader–Pursuer, …).

| What | Command |
|------|---------|
| Parse BDDL / Hex inputs | `qsage parse …` |
| Encode winning strategy (bwnib) | `qsage encode -e bwnib …` |
| Solve with QuBi / Bloqqer+CAQE | `qsage solve …` |
| Interactive play | see [Interactive play](#interactive-play) |

Papers: [arXiv:2303.16949](https://arxiv.org/abs/2303.16949) · [arXiv:2301.07345](https://arxiv.org/abs/2301.07345) · [certificates](https://doi.org/10.4230/LIPIcs.SAT.2023.24)

Docs: [`docs/DESIGN.md`](docs/DESIGN.md) · [`docs/ISSUES.md`](docs/ISSUES.md) · [`docs/ENCODINGS.md`](docs/ENCODINGS.md) · [`legacy/README.md`](legacy/README.md)

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

### Hex vs QBF solver (terminal)

```bash
qsage play hex --problem Benchmarks/B-Hex/hein_04_3x3-05.pg
# equivalent:
#   PYTHONPATH=legacy python legacy/interactive_play.py --problem …
```

| Flag | Meaning |
|------|---------|
| `--problem` | Hex `.pg` file |
| `--player user` | You play White (default) |
| `--player random` | Random White |
| `-e` | Encoding for the backend (see `-h`) |

Needs a working solver via the legacy stack (CAQE under `solvers/`). On Mac/Windows prefer **WSL2** or ensure Linux solvers can run (Docker).

![sample_play](https://user-images.githubusercontent.com/37924323/215714804-6fff96c3-21b7-44c1-951f-15587202581f.png)

### Grid games from a certificate (terminal)

No QBF solve each turn — uses a precomputed certificate + meta file. Works on **Mac, Linux, Windows** with `python-sat`.

```bash
pip install -e ".[play]"   # or: pip install python-sat

qsage play certificate
# defaults to the 4×4 HTTT Tic certificate under testcases/
# extra flags after -- :
qsage play certificate -- --certificate_path path/to/certificate.cnf --player user
```

### Browser UI

Planned local web UI: [issue #3](https://github.com/TeS44/Q-sage/issues/3).

### Certificates (full / partial)

For scalable QBF validation and winning-strategy equivalence, use **[SQval](https://github.com/irfansha/SQval)** (recommended over reimplementing cert logic here). See [`docs/CERTIFICATES.md`](docs/CERTIFICATES.md) and the SAT 2023 paper [LIPIcs SAT.2023.24](https://drops.dagstuhl.de/storage/00lipics/lipics-vol271-sat2023/LIPIcs.SAT.2023.24/LIPIcs.SAT.2023.24.pdf).

---

## Layout

```text
qsage/          # supported package (parse, encode, solve, CLI)
scripts/        # build QuBi, paper checks
tests/          # pytest
docs/           # design, issues, encoding keep-list
Benchmarks/     # games + golden QCIR
solvers/        # CAQE, QuBi, …
tools/          # Bloqqer, converters
testcases/      # certificates / extra inputs
legacy/         # original code (reference only — see legacy/README.md)
```

---

## Tests

```bash
pytest tests/ -q
```

---

## Platform cheat sheet

| | macOS | Linux | Windows |
|--|-------|-------|---------|
| Install `qsage` | ✓ | ✓ | ✓ (`py -3.11`) |
| parse / encode | ✓ | ✓ | ✓ |
| QuBi | build script | build / binary | **WSL2** |
| Bloqqer+CAQE | Docker | native | Docker or WSL2 |
| Hex interactive | solvers via WSL/Docker if needed | ✓ | WSL2 |
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
