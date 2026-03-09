# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/utils/state_persistence.py
# DESCRIPTION  : Daily state persistence to survive restarts
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-08
# ============================================================
"""ALPHAEDGE — Persist daily trading state across bot restarts."""

from __future__ import annotations

import json
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
        if data.get("date") != date.today().isoformat():
            logger.info("ALPHAEDGE STATE: State file is from a previous day — reset")
            return None
        return DailyState(**data)
    except (json.JSONDecodeError, TypeError, KeyError):
        logger.warning("ALPHAEDGE STATE: Corrupt state file — ignoring")
        return None


def clear_daily_state() -> None:
    """Remove the state file (e.g., for testing)."""
    path = Path(STATE_FILE)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
