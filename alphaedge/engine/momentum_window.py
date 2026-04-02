"""Helpers to build momentum detection windows consistently across engines."""

from __future__ import annotations

from typing import Any


def slice_momentum_window(
    bars: list[dict[str, Any]],
    lookback: int,
    *,
    end_index: int | None = None,
) -> list[dict[str, Any]]:
    """Return a right-aligned momentum window of at most ``lookback + 1`` bars."""
    if not bars:
        return []

    if end_index is None:
        end = len(bars) - 1
    else:
        end = max(0, min(end_index, len(bars) - 1))

    if lookback <= 0:
        return bars[: end + 1]

    start = max(0, end - lookback)
    return bars[start : end + 1]
