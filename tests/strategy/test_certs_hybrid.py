"""Partial-cert / hybrid architecture smoke tests."""

from __future__ import annotations

import sys

import pytest

from qsage.strategy import depqbf
from qsage.strategy.sqval import (
    _docker_ok,
    demo_hybrid_paths,
    demo_partial_equivalence_paths,
    run_equivalence,
    run_hybrid_validation,
    sqval_available,
)


@pytest.mark.skipif(not sqval_available(), reason="run bash scripts/setup_sqval.sh")
def test_demo_partial_and_hybrid_paths_exist() -> None:
    partial = demo_partial_equivalence_paths()
    hybrid = demo_hybrid_paths()
    for k, p in partial.items():
        assert p.is_file(), f"partial {k}: {p}"
    for k, p in hybrid.items():
        if k == "qdimacs":
            continue
        assert p.is_file(), f"hybrid {k}: {p}"


@pytest.mark.skipif(not sqval_available(), reason="run bash scripts/setup_sqval.sh")
@pytest.mark.skipif(
    sys.platform != "linux" and not _docker_ok(),
    reason="DepQBF is Linux ELF; need Docker on macOS/Windows",
)
def test_hein12_partial_equivalence_direction() -> None:
    """BOW_0 cert transfers to BOW_1 on shared vars (SQval README)."""
    paths = demo_partial_equivalence_paths()
    res = run_equivalence(
        paths["instance1"],
        paths["instance2"],
        paths["certificate"],
        paths["shared_variables"],
    )
    assert res.equivalent, res.raw[-800:]


@pytest.mark.skipif(not sqval_available(), reason="run bash scripts/setup_sqval.sh")
@pytest.mark.skipif(
    sys.platform != "linux" and not _docker_ok(),
    reason="hybrid tail needs Linux DepQBF/QuAbs",
)
def test_hybrid_demo_depth2() -> None:
    paths = demo_hybrid_paths()
    res = run_hybrid_validation(
        paths["instance"],
        paths["certificate"],
        hybrid_depth=2,
        status="sat",
        player="random",
        seed=0,
        timeout=240,
    )
    assert res.ok, res.message + "\n" + res.raw[-1200:]


def test_pedant_path_reported() -> None:
    # Does not require running Pedant; just API presence
    assert hasattr(depqbf, "generate_certificate_pedant")
    assert hasattr(depqbf, "run_depqbf_partial")
