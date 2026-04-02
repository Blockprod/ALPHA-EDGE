# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/utils/state_persistence.py
# DESCRIPTION  : Daily state persistence to survive restarts
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — Persist daily trading state across bot restarts."""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from alphaedge.utils.logger import get_logger

logger = get_logger()

STATE_FILE = "alphaedge_daily_state.json"


@dataclass
class DailyState:
    """Persisted daily trading state."""

    date: str  # YYYY-MM-DD
    starting_equity: float
    trades_today: int
    shutdown_triggered: bool
    open_pairs: list[str] = field(default_factory=list)
    last_update_utc: str = ""

    def _set_timestamp(self) -> None:
        self.last_update_utc = datetime.now(UTC).isoformat()


def save_daily_state(state: DailyState) -> None:
    """Atomically persist daily state to disk (.tmp → rename)."""
    state._set_timestamp()
    tmp = STATE_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(asdict(state), f, indent=2)
        os.replace(tmp, STATE_FILE)  # Atomic on both POSIX and Windows
        logger.debug(
            f"ALPHAEDGE STATE: Persisted daily state (trades={state.trades_today})"
        )
    except Exception:
        logger.exception("ALPHAEDGE STATE: Failed to persist daily state")
        # Cleanup temp file on failure
        if Path(tmp).exists():
            try:
                os.remove(tmp)
            except OSError:
                pass


def load_daily_state() -> DailyState | None:
    """Load today's persisted state. Returns None if absent or different day."""
    path = Path(STATE_FILE)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = _validate_daily_state_payload(data)
        if state.date != date.today().isoformat():
            logger.info("ALPHAEDGE STATE: State file is from a previous day — reset")
            return None
        return state
    except (json.JSONDecodeError, TypeError, KeyError, ValueError):
        logger.warning("ALPHAEDGE STATE: Corrupt state file — ignoring")
        return None


def _validate_daily_state_payload(data: object) -> DailyState:
    """Validate the persisted JSON payload before instantiating DailyState."""
    if not isinstance(data, dict):
        raise TypeError("Daily state payload must be a JSON object")

    raw_date = data.get("date")
    raw_starting_equity = data.get("starting_equity")
    raw_trades_today = data.get("trades_today")
    raw_shutdown = data.get("shutdown_triggered")
    raw_open_pairs = data.get("open_pairs", [])
    raw_last_update = data.get("last_update_utc", "")

    if not isinstance(raw_date, str):
        raise TypeError("date must be a string")
    date.fromisoformat(raw_date)

    if not isinstance(raw_starting_equity, (int, float)) or isinstance(
        raw_starting_equity, bool
    ):
        raise TypeError("starting_equity must be numeric")
    starting_equity = float(raw_starting_equity)
    if not math.isfinite(starting_equity) or starting_equity <= 0.0:
        raise ValueError("starting_equity must be a positive finite number")

    if not isinstance(raw_trades_today, int) or isinstance(raw_trades_today, bool):
        raise TypeError("trades_today must be an integer")
    if raw_trades_today < 0:
        raise ValueError("trades_today must be >= 0")

    if not isinstance(raw_shutdown, bool):
        raise TypeError("shutdown_triggered must be a bool")

    if not isinstance(raw_open_pairs, list) or not all(
        isinstance(pair, str) for pair in raw_open_pairs
    ):
        raise TypeError("open_pairs must be a list of strings")

    if not isinstance(raw_last_update, str):
        raise TypeError("last_update_utc must be a string")
    if raw_last_update:
        datetime.fromisoformat(raw_last_update)

    return DailyState(
        date=raw_date,
        starting_equity=starting_equity,
        trades_today=raw_trades_today,
        shutdown_triggered=raw_shutdown,
        open_pairs=list(raw_open_pairs),
        last_update_utc=raw_last_update,
    )


def clear_daily_state() -> None:
    """Remove the state file (e.g., for testing)."""
    path = Path(STATE_FILE)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
