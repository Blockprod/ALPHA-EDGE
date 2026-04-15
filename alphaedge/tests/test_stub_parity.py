# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_stub_parity.py
# DESCRIPTION  : B-06-C — verify _stubs/*.py signatures match .pyx public API
# SCENARIO     : all 3 core modules (momentum, order, risk) in parity
# ============================================================
"""B-06 — CI gate: .pyx public function signatures match _stubs/ counterparts."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.check_stub_parity import PARITY_PAIRS, check_parity

# Repo root is two levels above this test file (tests/ → alphaedge/ → repo root)
REPO_ROOT = Path(__file__).parent.parent.parent


@pytest.mark.parametrize("pyx_rel,stub_rel", PARITY_PAIRS)
def test_pyx_stub_parity(pyx_rel: str, stub_rel: str) -> None:
    """Every public .pyx function must have identical params in its stub."""
    pyx_path = REPO_ROOT / pyx_rel
    stub_path = REPO_ROOT / stub_rel

    assert pyx_path.exists(), f".pyx not found: {pyx_path}"
    assert stub_path.exists(), f"stub not found: {stub_path}"

    issues = check_parity(pyx_path, stub_path)
    assert issues == [], f"Stub parity failure for {pyx_path.name}:\n" + "\n".join(
        issues
    )
