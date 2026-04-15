# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/engine/live_journal.py
# DESCRIPTION  : Live trade journal — CSV append journalier
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-24
# ============================================================
"""ALPHAEDGE — Live trade journal: append one trade per close."""

from __future__ import annotations

import csv
import os
import tempfile
from datetime import datetime
from pathlib import Path

from alphaedge.engine.live_types import LiveTradeRecord
from alphaedge.utils.logger import get_logger
from alphaedge.utils.timezone import now_utc

logger = get_logger()

LIVE_JOURNAL_DIR = "reports"

CSV_HEADERS = [
    "pair",
    "direction",
    "entry_price",
    "fill_price",
    "exit_price",
    "stop_loss",
    "take_profit",
    "lot_size",
    "sl_pips",
    "spread_pips",
    "slippage_pips",
    "pnl_pips",
    "pnl_usd",
    "outcome",
    "exit_reason",
    "adx_at_entry",
    "strength_at_entry",
    "duration_s",
    "pnl_eur",
    "entry_time",
    "exit_time",
    "fill_status",
]


def _journal_path(trade_date: datetime | None = None) -> Path:
    """Return the CSV path for the given date (today if None)."""
    d = (trade_date or now_utc()).strftime("%Y-%m-%d")
    return Path(LIVE_JOURNAL_DIR) / f"live_trades_{d}.csv"


def append_live_trade_csv(record: LiveTradeRecord) -> None:
    """
    Append one completed trade to today's live journal CSV.

    Creates the file with headers if it does not exist.
    Writes atomically via tmp -> os.replace to prevent corruption on crash.
    """
    path = _journal_path(record.entry_time)
    os.makedirs(path.parent, exist_ok=True)
    existing_rows: list[dict[str, str]] = []
    if path.exists():
        with open(path, newline="", encoding="utf-8") as rf:
            existing_rows = list(csv.DictReader(rf))
    new_row = {
        "pair": record.pair,
        "direction": "LONG" if record.direction == 1 else "SHORT",
        "entry_price": record.entry_price,
        "fill_price": record.fill_price,
        "exit_price": record.exit_price,
        "stop_loss": record.stop_loss,
        "take_profit": record.take_profit,
        "lot_size": record.lot_size,
        "sl_pips": round(record.sl_pips, 2),
        "spread_pips": round(record.spread_pips, 2),
        "slippage_pips": round(record.slippage_pips, 4),
        "pnl_pips": round(record.pnl_pips, 2),
        "pnl_usd": round(record.pnl_usd, 2),
        "outcome": record.outcome,
        "exit_reason": record.exit_reason,
        "adx_at_entry": round(record.adx_at_entry, 2),
        "strength_at_entry": round(record.strength_at_entry, 4),
        "duration_s": round(record.duration_s, 1),
        "pnl_eur": round(record.pnl_eur, 2),
        "entry_time": (record.entry_time.isoformat() if record.entry_time else ""),
        "exit_time": (record.exit_time.isoformat() if record.exit_time else ""),
        "fill_status": record.fill_status,
    }
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, suffix=".tmp", prefix="live_journal_"
    )
    try:
        with os.fdopen(tmp_fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerows(existing_rows)
            writer.writerow(new_row)
        os.replace(tmp_path, path)
        logger.info(
            "TRADE_JOURNAL: {} {} — pnl_pips={:+.1f} — outcome={} — {}",
            record.pair,
            "LONG" if record.direction == 1 else "SHORT",
            record.pnl_pips,
            record.outcome,
            path.name,
        )
    except OSError:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        logger.exception("TRADE_JOURNAL: Failed to write live trade CSV — {}", path)
