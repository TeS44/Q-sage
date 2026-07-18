"""
Winning-strategy certificates (issue #9).

Architecture (scalable generation + hybrid interactive play):

  DepQBF-class tools  →  full *or partial* certificates (cheap outer layers)
  SQval hybrid play   →  cert for first n layers, DepQBF/QuAbs for the rest

Prefer external tools rather than reimplementing:

  https://github.com/irfansha/SQval

Paper:
  https://drops.dagstuhl.de/storage/00lipics/lipics-vol271-sat2023/LIPIcs.SAT.2023.24/LIPIcs.SAT.2023.24.pdf

See docs/CERTIFICATES.md.
"""

from qsage.strategy import depqbf, sqval

__all__ = ["sqval", "depqbf"]
