"""
Paper board-game QBF encodings — readable package, **gate-identical QCIR**.

* ``encode_hex_file`` — path-based Hex ``pg`` (arXiv:2301.07345)
* ``encode_grid_files`` — nested ``bwnib`` (arXiv:2303.16949)

Implementation lives in ``qsage.scratch.paper`` (self-contained algorithm;
**no imports from ``legacy/``**).  Output matches paper goldens and
``qsage.encode`` (same gate count ⇒ same solver times).

``experimental/`` holds alternate pure builders that are *not* gate-identical.
"""

from qsage.scratch.grid import encode_grid_files
from qsage.scratch.hex import encode_hex_file

__all__ = ["encode_hex_file", "encode_grid_files"]
