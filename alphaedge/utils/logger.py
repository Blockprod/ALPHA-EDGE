# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/utils/logger.py
# DESCRIPTION  : Loguru-based logging with UTC + Paris timestamps
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: structured logging configuration."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from alphaedge.config.constants import (
    LOG_DIR,
    LOG_RETENTION,
    LOG_ROTATION,
    PROJECT_NAME,
)
from alphaedge.utils.timezone import format_dual_time, now_utc

if TYPE_CHECKING:
    from loguru import Record

# Loguru Logger type alias for mypy
_LoggerType = Any


# ------------------------------------------------------------------
# Custom log format with dual timezone display
# ------------------------------------------------------------------
def _alphaedge_format(record: Record) -> str:
    """
    Build a custom log format line with UTC + Paris time.

    Parameters
    ----------
    record : dict
        Loguru record dict.

    Returns
    -------
    str
        Formatted log line.
    """
    dt_utc = now_utc()
    dual = format_dual_time(dt_utc)
    level = record["level"].name
    location = f"{record['name']}:{record['function']}:{record['line']}"
    message = record["message"]
    return f"[{PROJECT_NAME}] {dual} | {level:<8} | {location} | {message}\n"


# ------------------------------------------------------------------
# Set up file and console logging
# ------------------------------------------------------------------
def setup_logging(
    log_level: str = "INFO",
    log_dir: str = LOG_DIR,
) -> None:
    """
    Configure loguru with file rotation and console output.

    Parameters
    ----------
    log_level : str
        Minimum log level ('DEBUG', 'INFO', 'WARNING', 'ERROR').
    log_dir : str
        Directory path for log files.
    """
    # Remove default loguru handler
    logger.remove()

    # Ensure log directory exists
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Console handler
    logger.add(
        sys.stderr,
        format=_alphaedge_format,
        level=log_level,
        colorize=True,
    )

    # File handler with daily rotation
    log_path = Path(log_dir) / "alphaedge_{time:YYYY-MM-DD}.log"
    logger.add(
        str(log_path),
        format=_alphaedge_format,
        level=log_level,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        encoding="utf-8",
    )


# ------------------------------------------------------------------
# Get the configured logger instance
# ------------------------------------------------------------------
def get_logger() -> _LoggerType:
    """
    Return the loguru logger instance.

    Returns
    -------
    loguru.Logger
        Configured logger.
    """
    return logger


if __name__ == "__main__":
    setup_logging(log_level="DEBUG")
    log = get_logger()
    log.info("ALPHAEDGE logger initialized — standalone test")
    log.debug("Debug message test")
    log.warning("Warning message test")
    log.error("Error message test")
    print("ALPHAEDGE — Logger test complete. Check alphaedge/logs/")
