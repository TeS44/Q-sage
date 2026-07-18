"""
Partial certificates (opening books) for hybrid interactive play.

When full QuBi is slow, we store winning Black replies for the first
``hybrid_depth`` Black plies (board-keyed). Later plies fall back to QBF
or random.

Layout::

    Benchmarks/partial_certs/<safe_path>.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_ROOT = _REPO / "Benchmarks" / "partial_certs"


def _safe_name(rel_path: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", rel_path.replace("\\", "/"))


def cert_path_for(rel_path: str) -> Path:
    return _ROOT / f"{_safe_name(rel_path)}.json"


def board_key(cells: dict[str, str], to_move: str) -> str:
    """Canonical key for a position (order-independent)."""
    b = sorted(p for p, v in cells.items() if v == "B")
    w = sorted(p for p, v in cells.items() if v == "W")
    return f"B:{','.join(b)}|W:{','.join(w)}|to:{to_move}"


def load_partial(rel_path: str) -> dict | None:
    p = cert_path_for(rel_path)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_partial(data: dict) -> Path:
    _ROOT.mkdir(parents=True, exist_ok=True)
    rel = data["path"]
    out = cert_path_for(rel)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return out


def lookup_move(rel_path: str, cells: dict[str, str], to_move: str = "B") -> dict | None:
    """
    Return {"move": pos, "ply": int, "source": "partial_cert"} or None.
    """
    book = load_partial(rel_path)
    if not book:
        return None
    key = board_key(cells, to_move)
    for layer in book.get("layers") or []:
        if layer.get("board_key") == key and layer.get("move"):
            return {
                "move": layer["move"],
                "ply": layer.get("ply"),
                "source": "partial_cert",
                "hybrid_depth": book.get("hybrid_depth"),
                "full_status": book.get("full_status"),
            }
    # also try layers keyed only by ply 0 default opening
    return None


def list_partial_certs() -> list[dict]:
    if not _ROOT.is_dir():
        return []
    out = []
    for p in sorted(_ROOT.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out.append(
                {
                    "path": d.get("path"),
                    "full_status": d.get("full_status"),
                    "hybrid_depth": d.get("hybrid_depth"),
                    "layers": len(d.get("layers") or []),
                    "file": str(p.relative_to(_REPO)),
                }
            )
        except (OSError, json.JSONDecodeError):
            continue
    return out


def has_partial(rel_path: str) -> bool:
    return cert_path_for(rel_path).is_file()
