"""Discover playable benchmarks for the web UI."""

from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def list_all_problems() -> list[dict]:
    """Return catalog entries: path, label, kind, group."""
    out: list[dict] = []

    # Positional Hex (main paper boards)
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

    # Grid GDDL problems (play via encode+solve check; board occupy if domain is occupy)
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
