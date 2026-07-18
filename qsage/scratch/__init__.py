"""
Deprecated thin re-exports.

Official encodings live in ``qsage.encode`` (``encode_bwnib``,
``encode_positional``).  ``legacy/`` is kept for reference only.
"""

from qsage.encode.bwnib import encode_bwnib as encode_grid_files
from qsage.encode.positional import encode_positional


def encode_hex_file(path):  # type: ignore[no-untyped-def]
    return encode_positional(path, encoding="pg")


__all__ = ["encode_hex_file", "encode_grid_files"]
