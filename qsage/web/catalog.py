"""Discover playable benchmarks for the web UI."""

from __future__ import annotations

import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_PLAYABLE = _REPO / "Benchmarks" / "playable_qbf.json"


def load_playable_qbf() -> dict | None:
    """Instances QuBi finishes under a hard timeout (see scripts/scan_playable_qbf.py)."""
    if not _PLAYABLE.is_file():
        return None
    try:
        return json.loads(_PLAYABLE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_all_problems(*, qbf_only: bool = True) -> list[dict]:
    """
    Return catalog entries: path, label, kind, group.

    If ``qbf_only`` and ``Benchmarks/playable_qbf.json`` exists, list only
    instances known to finish under the scan timeout (default 3s). Certificate
    packs are always included.
    """
    out: list[dict] = []
    playable = load_playable_qbf() if qbf_only else None

    if playable and playable.get("instances"):
        for e in playable["instances"]:
            kind = e.get("kind") or "grid"
            game = e.get("game") or "other"
            if kind == "hex":
                group = "Hex (B-Hex)" if game == "hex" else "Hex (GDDL)"
            else:
                group = f"Grid ({game})"
            entry = {
                "path": e["path"],
                "label": e.get("label") or Path(e["path"]).name,
                "kind": kind,
                "group": group,
                "qbf_status": e.get("status"),
                "qbf_seconds": e.get("seconds"),
                "playable": True,
            }
            if e.get("domain"):
                entry["domain"] = e["domain"]
            if e.get("encoding"):
                entry["encoding"] = e["encoding"]
            out.append(entry)
    else:
        # Fallback: full tree (may include slow instances)
        for folder, group in (
            (_REPO / "Benchmarks" / "B-Hex", "Hex (B-Hex)"),
            (
                _REPO / "Benchmarks" / "SAT2023_GDDL" / "GDDL_models" / "hex",
                "Hex (GDDL)",
            ),
        ):
            if not folder.is_dir():
                continue
            for p in sorted(folder.glob("*.pg")):
                out.append(
                    {
                        "path": str(p.relative_to(_REPO)),
                        "label": p.name,
                        "kind": "hex",
                        "group": group,
                    }
                )
        gddl = _REPO / "Benchmarks" / "SAT2023_GDDL" / "GDDL_models"
        if gddl.is_dir():
            for game_dir in sorted(gddl.iterdir()):
                if not game_dir.is_dir() or game_dir.name == "hex":
                    continue
                domain = game_dir / "domain.ig"
                if not domain.is_file():
                    continue
                for p in sorted(game_dir.glob("*.ig")):
                    if p.name == "domain.ig":
                        continue
                    out.append(
                        {
                            "path": str(p.relative_to(_REPO)),
                            "label": f"{game_dir.name}/{p.name}",
                            "kind": "grid",
                            "group": f"Grid ({game_dir.name})",
                            "domain": str(domain.relative_to(_REPO)),
                        }
                    )

    # Precomputed certificates (winning-strategy play)
    cert_root = _REPO / "testcases" / "index_general_certificates"
    if cert_root.is_dir():
        for d in sorted(cert_root.iterdir()):
            if not d.is_dir():
                continue
            cert = d / "certificate.cnf"
            meta = d / "viz_meta_out"
            if cert.is_file() and meta.is_file():
                out.append(
                    {
                        "path": str(d.relative_to(_REPO)),
                        "label": d.name,
                        "kind": "certificate",
                        "group": "Certificates (strategy)",
                        "certificate": str(cert.relative_to(_REPO)),
                        "meta": str(meta.relative_to(_REPO)),
                    }
                )

    return out
