#!/usr/bin/env python3
# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : scripts/check_stub_parity.py
# DESCRIPTION  : B-06 — verify _stubs/*.py signatures match .pyx public API
# PYTHON       : 3.11.9
# ============================================================
"""
Verify that every public `def` in a .pyx file has an exact signature match
in its corresponding _stubs/*.py file (same function name + same param names
in the same order).

Exit code 0 = all matched.
Exit code 1 = at least one divergence found.

Usage:
    python scripts/check_stub_parity.py [--repo-root PATH]
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

# ------------------------------------------------------------------
# Pairs to check: (pyx_path, stub_path) — relative to repo root
# ------------------------------------------------------------------
PARITY_PAIRS = [
    (
        "alphaedge/core/momentum_detector.pyx",
        "alphaedge/core/_stubs/momentum_detector.py",
    ),
    (
        "alphaedge/core/order_manager.pyx",
        "alphaedge/core/_stubs/order_manager.py",
    ),
    (
        "alphaedge/core/risk_manager.pyx",
        "alphaedge/core/_stubs/risk_manager.py",
    ),
]


# ------------------------------------------------------------------
# .pyx parsing (regex-based — no Cython compiler required)
# ------------------------------------------------------------------
def _parse_params(params_str: str) -> list[str]:
    """
    Extract parameter names from a raw parameter list string.

    Handles both Cython C-style ('int direction', 'double price') and
    Python-style annotations ('bars: list', 'fast_period: int').
    Default values are stripped ('exchange_rate: float = 0.0' → 'exchange_rate').
    """
    params: list[str] = []
    for raw in params_str.split(","):
        raw = raw.strip()
        if not raw or raw.startswith("*"):
            continue
        # Strip inline comment
        raw = raw.split("#")[0].strip()
        if not raw:
            continue
        # Strip default value
        raw = raw.split("=")[0].strip()
        # Python-style annotation: 'name: type'
        if ":" in raw:
            name = raw.split(":")[0].strip()
        else:
            # Cython C-style: 'type name' OR bare 'name'
            parts = raw.split()
            name = parts[-1] if len(parts) >= 2 else (parts[0] if parts else "")
        # Accept only valid Python identifiers
        if name and re.match(r"^\w+$", name):
            params.append(name)
    return params


def extract_pyx_public_functions(pyx_text: str) -> dict[str, list[str]]:
    """
    Return {func_name: [param_names]} for every top-level `def` in .pyx source.

    Ignores `cdef` and `cpdef`; only lines where `def` starts at column 0 are
    considered public (Python-accessible) functions.
    """
    funcs: dict[str, list[str]] = {}
    for m in re.finditer(r"(?m)^def\s+(\w+)\s*\(", pyx_text):
        name = m.group(1)
        start = m.end()  # index right after opening '('
        depth = 1
        j = start
        while j < len(pyx_text) and depth > 0:
            ch = pyx_text[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            j += 1
        params_str = pyx_text[start : j - 1]
        funcs[name] = _parse_params(params_str)
    return funcs


# ------------------------------------------------------------------
# Stub parsing (ast-based)
# ------------------------------------------------------------------
def extract_stub_public_functions(
    stub_text: str, stub_path: str
) -> dict[str, list[str]]:
    """
    Return {func_name: [param_names]} for every public (non-underscore) `def`
    at module level in the stub Python file.
    """
    tree = ast.parse(stub_text, filename=stub_path)
    funcs: dict[str, list[str]] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            params = [arg.arg for arg in node.args.args]
            funcs[node.name] = params
    return funcs


# ------------------------------------------------------------------
# Parity check
# ------------------------------------------------------------------
def check_parity(
    pyx_path: Path,
    stub_path: Path,
) -> list[str]:
    """
    Compare public function signatures between a .pyx and its stub.

    Returns a list of human-readable divergence messages.
    An empty list means full parity.
    """
    pyx_text = pyx_path.read_text(encoding="utf-8")
    stub_text = stub_path.read_text(encoding="utf-8")

    pyx_funcs = extract_pyx_public_functions(pyx_text)
    stub_funcs = extract_stub_public_functions(stub_text, str(stub_path))

    issues: list[str] = []

    # Check for functions in .pyx missing from stub
    for name, pyx_params in pyx_funcs.items():
        if name not in stub_funcs:
            issues.append(f"  MISSING in stub: {name}({', '.join(pyx_params)})")
            continue
        stub_params = stub_funcs[name]
        if pyx_params != stub_params:
            issues.append(
                f"  PARAM MISMATCH: {name}\n"
                f"    .pyx  : ({', '.join(pyx_params)})\n"
                f"    stub  : ({', '.join(stub_params)})"
            )

    # Check for functions in stub not present in .pyx (extra stubs)
    for name in stub_funcs:
        if name not in pyx_funcs:
            issues.append(f"  EXTRA in stub (not in .pyx): {name}")

    return issues


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
def run(repo_root: Path) -> int:
    """Execute parity checks for all configured pairs. Returns exit code."""
    any_divergence = False

    for pyx_rel, stub_rel in PARITY_PAIRS:
        pyx_path = repo_root / pyx_rel
        stub_path = repo_root / stub_rel

        if not pyx_path.exists():
            print(f"ERROR: .pyx not found: {pyx_path}", file=sys.stderr)
            any_divergence = True
            continue
        if not stub_path.exists():
            print(f"ERROR: stub not found: {stub_path}", file=sys.stderr)
            any_divergence = True
            continue

        issues = check_parity(pyx_path, stub_path)
        label = pyx_path.name

        if issues:
            print(f"❌ {label} — {len(issues)} divergence(s):")
            for issue in issues:
                print(issue)
            any_divergence = True
        else:
            pyx_funcs = extract_pyx_public_functions(
                pyx_path.read_text(encoding="utf-8")
            )
            print(f"✅ {label} — {len(pyx_funcs)} function(s) in parity")

    return 1 if any_divergence else 0


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Check .pyx ↔ _stubs/ signature parity"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Root directory of the repository (default: cwd)",
    )
    args = parser.parse_args()
    sys.exit(run(args.repo_root))


if __name__ == "__main__":
    main()
