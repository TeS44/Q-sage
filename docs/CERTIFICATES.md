# Certificates and validation (issue #9)

Full / partial winning-strategy certificates for interactive play and validation.

## Paper

- [Validation of QBF Encodings with Winning Strategies](https://drops.dagstuhl.de/storage/00lipics/lipics-vol271-sat2023/LIPIcs.SAT.2023.24/LIPIcs.SAT.2023.24.pdf)  
  (LIPIcs SAT 2023)

## Preferred tool: SQval

Upstream tool for **scalable QBF validation** and **winning-strategy equivalence** (full and partial):

**https://github.com/irfansha/SQval**

Features relevant to Q-sage:

1. **Interactive validation** with a QBF solver or an AIGER certificate  
   ```bash
   python3 interactive_validation.py \
     --certificate path/to/certificate.aag \
     --instance path/to/qbf.qcir
   # or dynamic play with a solver:
   python3 interactive_validation.py \
     --instance path/to/qbf.qcir --status 1 --player user --validation dynamic
   ```

2. **Partial / full strategy equivalence** between two QDIMACS instances sharing variables  
   ```bash
   python3 winning_strategy_equivalence.py \
     --instance1 Q1.qdimacs --instance2 Q2.qdimacs \
     --certificate cert.aag --shared_variables shared.txt
   ```

Dependencies: `pip install python-sat` (see SQval `requirements.txt`).

## In this repo today

| Piece | Location |
|-------|----------|
| Play from existing CNF certificate | `qsage play certificate` → `legacy/general_interactive_play.py` |
| Sample cert + meta | `testcases/index_general_certificates/` |
| Pedant / depqbf cert generation | still via `legacy/` solvers (not yet a first-class `qsage` API) |

## `qsage` integration (current)

```bash
bash scripts/setup_sqval.sh    # clones third_party/SQval + python-sat

# Winning-strategy equivalence (SQval + DepQBF; Docker on Mac/Windows)
qsage cert demo-equivalence
# or:
qsage cert equivalence --demo

# Full SQval CLI (interactive validation — needs Linux solvers / WSL for QBF)
qsage cert validate -- --instance path/to/qbf.qcir --status 1 --player user --validation dynamic
qsage cert validate -- --certificate path/to/cert.aag --instance path/to/qbf.qcir
```

On **macOS**, equivalence demos use **Docker** (`linux/amd64`) because SQval ships DepQBF as a Linux binary.

Still TODO: Pedant-based *generation* of AIGER certificates from our encodings; deeper mid-game cert play in the web UI.

Do **not** reimplement SQval’s algorithms here; call into that project.
