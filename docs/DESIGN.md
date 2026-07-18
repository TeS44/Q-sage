# Q-sage rewrite (student guide)

Target: **TeS44/Q-sage**. Legacy `Q-sage.py` stays as the reference until encodings are ported.

## Issues

| # | Goal |
|---|------|
| 1 | Grammar-based parsing of BDDL / `.pg` inputs |
| 2 | Modular rewrite: paper encodings, solvers, certificates |
| 3 | Simple local UI for interactive play |

## Decisions

- **New package** `qsage/` (Python 3.11+). Keep old code for golden tests.
- **Parsers:** Lark grammars under `qsage/parse/grammars/` (easy to edit when the input language changes).
- **Encodings:** only what the papers need. Minimum: **`bwnib`** (grid). Positional: `pg`, `cp`, `ibign` (confirm when porting).
- **Tests:** normalized QCIR vs legacy; later check solver answers against paper tables.
- **Solvers:** build QCIR in memory → QDIMACS → Bloqqer + CAQE; later Pedant / QuBi.
- **UI:** localhost, easy install (issue #3).

## Layout

```text
qsage/
  parse/      # grammars + AST  (issue #1 — done)
  games/      # board state, legal moves
  encode/     # QCIR builders (paper encodings only)
  solve/      # QDIMACS + solver wrappers
  strategy/   # winning-strategy certificates
  play/       # opponents: human / random / solver / cert
  cli/        # qsage encode | solve | play | …
tests/
docs/DESIGN.md
```

## Suggested work order

1. ~~Scaffold + design~~  
2. ~~Lark parsers + benchmark tests~~  
3. In-memory QCIR + QDIMACS  
4. Port `bwnib`, golden tests vs legacy  
5. Port positional encodings from the papers  
6. Solvers + certificates  
7. Play API + localhost UI  

Keep modules small. Prefer clear names over clever abstractions so later course projects can extend multi-piece games, new encodings, or UI without a rewrite.
