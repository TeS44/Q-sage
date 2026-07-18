"""
Standalone from-scratch QBF encodings for 2-player board games.

No imports from ``qsage.encode``, ``qsage.parse``, or ``legacy``.
Only stdlib (+ optional solver in tests).

Correctness is checked by QBF solvers (SAT/UNSAT), not by matching
legacy QCIR text. The golden-QCIR path lives in ``qsage.encode`` and is
untouched.
"""

from qsage.scratch.grid import encode_grid_files
from qsage.scratch.hex import encode_hex_file

__all__ = ["encode_hex_file", "encode_grid_files"]
