"""SQval integration smoke test (skips if SQval or Docker unavailable)."""

from __future__ import annotations

import sys

import pytest

from qsage.strategy.sqval import (
    _docker_ok,
    demo_equivalence_paths,
    run_equivalence,
    sqval_available,
)


@pytest.mark.skipif(not sqval_available(), reason="run bash scripts/setup_sqval.sh")
@pytest.mark.skipif(
    sys.platform != "linux" and not _docker_ok(),
    reason="DepQBF is Linux ELF; need Docker on macOS/Windows",
)
def test_hein04_ln_sn_equivalence_demo() -> None:
    paths = demo_equivalence_paths()
    for k, p in paths.items():
        assert p.is_file(), k
    # LN certificate should transfer to SN (paper / SQval demo)
    res = run_equivalence(
        paths["instance1"],
        paths["instance2"],
        paths["certificate"],
        paths["shared_variables"],
    )
    assert res.equivalent, res.raw[-800:]
