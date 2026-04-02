"""Shared USD exposure helpers for live and backtest multi-pair filtering."""

from __future__ import annotations


def usd_direction(pair: str, direction: int) -> int:
    """Map a trade direction to net USD direction (+1 long USD, -1 short USD)."""
    if direction == 0 or len(pair) < 6:
        return 0
    base = pair[:3]
    quote = pair[3:6]
    if base == "USD":
        return 1 if direction > 0 else -1
    if quote == "USD":
        return -1 if direction > 0 else 1
    return 0


def would_amplify_usd_exposure(
    open_positions: list[tuple[str, int]],
    pair: str,
    direction: int,
) -> bool:
    """Return True when a new signal increases existing net USD directional risk."""
    incoming = usd_direction(pair, direction)
    if incoming == 0:
        return False

    net_usd = 0
    for open_pair, open_dir in open_positions:
        net_usd += usd_direction(open_pair, open_dir)

    return net_usd != 0 and incoming == net_usd
