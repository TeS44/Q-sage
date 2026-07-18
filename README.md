# Q-sage

QBF encodings for **2-player board games** (Hex, Harary’s Tic-Tac-Toe, Breakthrough, Connect-c, Domineering, Evader–Pursuer, …).

- **Encode** the existence of a bounded-depth winning strategy as QCIR / QDIMACS  
- **Solve** with QuBi or Bloqqer+CAQE  
- **Play** interactively (terminal) against a solver or from a certificate  

Research papers (encodings / certificates):

- [Concise QBF Encodings for Games on a Grid](https://arxiv.org/abs/2303.16949) (SAT 2023)  
- [Implicit State and Goals in QBF Encodings for Positional Games](https://arxiv.org/abs/2301.07345)  
- Certificates: [doi:10.4230/LIPIcs.SAT.2023.24](https://doi.org/10.4230/LIPIcs.SAT.2023.24)  

Design / issue backlog: [`docs/DESIGN.md`](docs/DESIGN.md), [`docs/ISSUES.md`](docs/ISSUES.md).

---

## Requirements

| | Minimum |
|--|---------|
| **Python** | 3.11+ |
| **OS** | macOS, Linux, or Windows (see platform notes below) |
| **pip** | recent |

Optional:

| Tool | Purpose |
|------|---------|
| **QuBi** | Fast QCIR solver (works well on **macOS** and **Linux**) |
| **Bloqqer + CAQE** | Paper’s main CNF pipeline (**Linux** binaries; on Mac use **Docker**) |
| **Docker** | Run Linux solvers on macOS / Windows |
| **networkx** | Used by the legacy encoder path (installed with the package) |
| **pyvis** | Only if you visualize QCIR circuits (`--qcir_viz 1`) |
| **python-sat** | Needed by `general_interactive_play.py` (certificate play) |

---

## Install

### 1. Get the code

```bash
git clone https://github.com/TeS44/Q-sage.git
cd Q-sage
```

### 2. Create a virtual environment (recommended)

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows (cmd):**

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate.bat
```

### 3. Install the package

```bash
pip install -e ".[dev]"
```

This installs the `qsage` CLI and dependencies (`lark`, `networkx`, `pytest`, …).

### 4. Solvers (optional but recommended)

#### QuBi (preferred on Mac / Linux)

QuBi reads **QCIR** directly and is usually the easiest option on a laptop.

**macOS:**

```bash
bash scripts/build_qubi_macos.sh
# installs solvers/qubi/qubi
```

Needs: Xcode CLT / `clang++`, CMake, GMP (e.g. `brew install gmp cmake` if missing).  
The script builds [Sylvan](https://github.com/trolando/sylvan) into `~/.local` and patches QuBi for current Lace APIs.

**Linux:**

```bash
# Same idea as the macOS script, or build QuBi + Sylvan from source:
#   https://github.com/jacopol/qubi
# Place the binary at: solvers/qubi/qubi
bash scripts/build_qubi_macos.sh   # works on Linux too if g++/cmake/gmp are available
```

**Windows:**

- **WSL2 (recommended):** clone the repo inside WSL and follow the **Linux** steps.  
- Or use **Docker** for solvers (see below). Native MSVC builds of QuBi/Sylvan are not documented yet.

Check:

```bash
solvers/qubi/qubi -h          # macOS / Linux
# Windows WSL: same path
```

#### Bloqqer + CAQE

Binaries under `tools/Bloqqer/bloqqer` and `solvers/caqe/caqe` are **Linux x86_64 ELF**.

| Platform | How to run |
|----------|------------|
| **Linux x86_64** | Run natively |
| **macOS / Windows** | Install [Docker Desktop](https://www.docker.com/products/docker-desktop/), start it, then use `--backend bloqqer+caqe` (qsage launches `linux/amd64` containers) |

---

## Quick start (`qsage` CLI)

```bash
qsage -h
qsage parse -h
qsage encode -h
qsage solve -h
```

### Parse inputs

**BDDL / GDDL domain + problem (grid games):**

```bash
qsage parse \
  --domain Benchmarks/SAT2023_GDDL/GDDL_models/httt/domain.ig \
  --problem Benchmarks/SAT2023_GDDL/GDDL_models/httt/3x3_3_domino.ig
```

**Positional Hex (`.pg` board + neighbours):**

```bash
qsage parse --problem Benchmarks/B-Hex/hein_04_3x3-05.pg
```

### Encode (bwnib — paper grid encoding)

```bash
qsage encode \
  --domain Benchmarks/SAT2023_GDDL/GDDL_models/httt/domain.ig \
  --problem Benchmarks/SAT2023_GDDL/GDDL_models/httt/3x3_3_domino.ig \
  -e bwnib \
  --normalize \
  --out out.qcir
```

- `--format qcir` (default) or `qdimacs`  
- `--normalize` strips comments for golden comparison  

### Solve

**With QuBi (QCIR file):**

```bash
qsage solve \
  --qcir Benchmarks/SAT2023_GDDL/QBF_instances/httt/3x3_3_domino_bwnib.qcir \
  --backend qubi
```

**Encode then solve:**

```bash
qsage solve \
  --domain Benchmarks/SAT2023_GDDL/GDDL_models/httt/domain.ig \
  --problem Benchmarks/SAT2023_GDDL/GDDL_models/httt/3x3_3_domino.ig \
  --backend qubi
```

**Bloqqer + CAQE** (Docker on Mac/Windows if needed):

```bash
qsage solve \
  --qcir Benchmarks/SAT2023_GDDL/QBF_instances/httt/3x3_3_domino_bwnib.qcir \
  --backend bloqqer+caqe \
  --timeout 120
```

Output is `SAT` (first player has a winning strategy of that depth) or `UNSAT` (no such strategy).

### Paper Table 2 sample checks

```bash
python scripts/run_paper_checks.py --backend qubi
```

Compares a set of SAT 2023 Table 2 instances (bold = win / SAT, plain = no win / UNSAT).

---

## Interactive play

There are **two** terminal players today. A browser UI is planned ([issue #3](https://github.com/TeS44/Q-sage/issues/3)).

### 1. Hex (positional) — play vs QBF solver

Uses the **legacy** pipeline: re-encodes after each move and calls a solver.

```bash
# from repo root, with venv active
python interactive_play.py --problem Benchmarks/B-Hex/hein_04_3x3-05.pg
```

Useful options:

| Flag | Meaning |
|------|---------|
| `--problem` | Hex `.pg` file |
| `--player user` | You type moves (default) |
| `--player random` | Random legal moves |
| `--depth` | Override search depth if needed |
| `-e` | Encoding for the backend (see `python interactive_play.py -h`) |

**Platform notes:**

- Needs a working **QBF solve path** via the legacy `Q-sage.py` stack (CAQE under `solvers/`, etc.). On **macOS/Windows**, prefer **WSL2** or ensure Docker-based solving is available if you only have Linux ELF solvers.  
- Enter moves as indicated by the prompt (board positions such as `a1`).

Sample (old terminal UI):

![sample_play](https://user-images.githubusercontent.com/37924323/215714804-6fff96c3-21b7-44c1-951f-15587202581f.png)

### 2. Grid games — play from a **certificate**

Validates / plays against a precomputed winning strategy (CNF certificate + meta file). Does **not** re-run a QBF solver each move.

```bash
pip install python-sat

python general_interactive_play.py \
  --certificate_path testcases/index_general_certificates/httt_4_4_tic/certificate.cnf \
  --meta_path testcases/index_general_certificates/httt_4_4_tic/viz_meta_out \
  --player user
```

| Flag | Meaning |
|------|---------|
| `--certificate_path` | Certificate (CNF / AIGER as supported) |
| `--meta_path` | Board / variable meta from encoding |
| `--player user` | Interactive white moves (default) |
| `--player random` | Random white replies |
| `--seed` | RNG seed for random player |

**Demo defaults** already point at a 4×4 HTTT Tic certificate under `testcases/index_general_certificates/`.

```bash
python general_interactive_play.py
# then type white moves when prompted, e.g. occupy(2,3) style as printed
```

Works the same on **macOS, Linux, and Windows** as long as `python-sat` installs (use 64-bit Python).

### 3. Future web UI

Local browser play (grid + Hex boards, opponents: human / random / QBF / certificate) is tracked in [issue #3](https://github.com/TeS44/Q-sage/issues/3). Until then, use the scripts above.

---

## Legacy encoder (`Q-sage.py`)

Still available for full encoding flags and paper reproduction.

**Grid / BDDL (bwnib):**

```bash
python Q-sage.py \
  --game_type general -e bwnib \
  --ib_domain Benchmarks/SAT2023_GDDL/GDDL_models/breakthrough/domain.ig \
  --ib_problem Benchmarks/SAT2023_GDDL/GDDL_models/breakthrough/2x4_13.ig \
  --encoding_format 1 \
  --encoding_out intermediate_files/encoding.qcir \
  --run 0
```

**Hex positional:**

```bash
python Q-sage.py -e pg \
  --problem Benchmarks/B-Hex/hein_04_3x3-05.pg \
  --run 0 \
  --encoding_out intermediate_files/hex.qcir
```

```bash
python Q-sage.py -h   # all flags
```

- `--run 0` encode only · `1` existence · `2` extract first move  
- Circuit visualization needs `pip install pyvis` and `--qcir_viz 1`  

---

## Tests

```bash
pytest tests/ -q
```

Includes:

- Parse all BDDL / positional benchmarks  
- **bwnib** QCIR vs goldens under `Benchmarks/SAT2023_GDDL/QBF_instances/**/*_bwnib.qcir`  
- QuBi paper checks (skipped if `solvers/qubi/qubi` is missing)  

---

## Platform cheat sheet

| Task | macOS | Linux | Windows |
|------|-------|-------|---------|
| `pip install -e ".[dev]"` | ✓ | ✓ | ✓ (use `py -3.11`) |
| `qsage parse / encode` | ✓ | ✓ | ✓ |
| QuBi solve | ✓ build script | ✓ build / binary | WSL2 or Docker |
| Bloqqer+CAQE | Docker Desktop | native ELF | Docker Desktop or WSL2 |
| `interactive_play.py` (Hex) | ✓ if solvers work | ✓ | WSL2 recommended |
| `general_interactive_play.py` | ✓ + `python-sat` | ✓ | ✓ + `python-sat` |

**Windows tip:** For solvers and Hex interactive play, [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) with Ubuntu is the least painful path: install Python + deps inside WSL and use the Linux instructions.

**macOS tip:** QuBi first (`build_qubi_macos.sh`). Start Docker only if you need Bloqqer+CAQE.

---

## Repository layout (short)

```text
qsage/           # new package: parse, encode, solve, CLI
scripts/         # build QuBi, paper checks
Benchmarks/      # games + golden QCIR/QDIMACS
solvers/         # CAQE, QuBi, … (some Linux-only)
tools/           # Bloqqer, converters
Q-sage.py        # legacy encoder CLI
interactive_play.py
general_interactive_play.py
docs/            # DESIGN.md, ISSUES.md
tests/
```

---

## Authors

```text
Irfansha Shaik
Aarhus
```

Contributors: see GitHub. License: MIT (see `LICENSE`).
