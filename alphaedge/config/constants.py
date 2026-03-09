# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/config/constants.py
# DESCRIPTION  : Project-wide constants and default values
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: global constants and defaults."""

from __future__ import annotations

# ------------------------------------------------------------------
# Project identity
# ------------------------------------------------------------------
PROJECT_NAME: str = "ALPHAEDGE"
PROJECT_TITLE: str = "⚡ ALPHAEDGE — FCR Forex Trading Bot"
PROJECT_VERSION: str = "1.0.0"

# ------------------------------------------------------------------
# Timezone identifiers (zoneinfo keys)
# ------------------------------------------------------------------
TZ_UTC: str = "UTC"
TZ_NEW_YORK: str = "America/New_York"
TZ_PARIS: str = "Europe/Paris"

# ------------------------------------------------------------------
# Session window (NYSE open, in local EST/EDT)
# ------------------------------------------------------------------
SESSION_START_HOUR: int = 9
SESSION_START_MINUTE: int = 30
SESSION_END_HOUR: int = 10
SESSION_END_MINUTE: int = 30

# ------------------------------------------------------------------
# London Open session window (in UTC)
# ------------------------------------------------------------------
LONDON_START_HOUR: int = 8
LONDON_START_MINUTE: int = 0
LONDON_END_HOUR: int = 9
LONDON_END_MINUTE: int = 0
LONDON_TZ: str = "UTC"

# ------------------------------------------------------------------
# Timeframes
# ------------------------------------------------------------------
TF_M5: str = "5 mins"
TF_M1: str = "1 min"

# ------------------------------------------------------------------
# Default trading parameters
# ------------------------------------------------------------------
DEFAULT_RR_RATIO: float = 3.0
DEFAULT_RISK_PCT: float = 1.0
DEFAULT_MAX_DAILY_LOSS_PCT: float = 3.0
DEFAULT_MAX_TRADES_PER_SESSION: int = 2
DEFAULT_MAX_SPREAD_PIPS: float = 2.0

# ------------------------------------------------------------------
# Pip sizes per pair type
# ------------------------------------------------------------------
PIP_SIZES: dict[str, float] = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "AUDUSD": 0.0001,
    "USDCAD": 0.0001,
    "USDCHF": 0.0001,
    "NZDUSD": 0.0001,
    "EURJPY": 0.01,
    "GBPJPY": 0.01,
}

# ------------------------------------------------------------------
# IB Gateway defaults
# ------------------------------------------------------------------
IB_HOST: str = "127.0.0.1"
IB_LIVE_PORT: int = 4001
IB_PAPER_PORT: int = 4002
IB_CLIENT_ID: int = 1

# ------------------------------------------------------------------
# ATR / Gap detection defaults
# ------------------------------------------------------------------
DEFAULT_ATR_PERIOD: int = 14
DEFAULT_MIN_ATR_RATIO: float = 1.5
DEFAULT_GAP_TOLERANCE_PIPS: float = 5.0

# ------------------------------------------------------------------
# Volatility regime filter
# ------------------------------------------------------------------
REGIME_ATR_LOOKBACK_DAYS: int = 20
REGIME_ATR_LOW_MULTIPLIER: float = 0.5
REGIME_ATR_HIGH_MULTIPLIER: float = 2.0

# ------------------------------------------------------------------
# Volume confirmation defaults
# ------------------------------------------------------------------
DEFAULT_VOLUME_PERIOD: int = 20
DEFAULT_MIN_VOLUME_RATIO: float = 1.2

# ------------------------------------------------------------------
# FCR detection defaults
# ------------------------------------------------------------------
DEFAULT_MIN_RANGE_PIPS: float = 5.0
DEFAULT_FCR_LOOKBACK: int = 6

# ------------------------------------------------------------------
# Engulfing quality filter defaults
# ------------------------------------------------------------------
DEFAULT_MIN_BODY_RATIO: float = 0.3
DEFAULT_MAX_WICK_RATIO: float = 2.0

# ------------------------------------------------------------------
# News filter defaults
# ------------------------------------------------------------------
DEFAULT_BLACKOUT_MINUTES: int = 15
DEFAULT_IMPACT_LEVELS: tuple[str, ...] = ("high",)

# ------------------------------------------------------------------
# Spread monitoring
# ------------------------------------------------------------------
DEFAULT_SPREAD_SPIKE_MULTIPLIER: float = 3.0

# ------------------------------------------------------------------
# Risk check intervals (seconds)
# ------------------------------------------------------------------
RISK_CHECK_INTERVAL_IDLE: int = 30
RISK_CHECK_INTERVAL_POSITION: int = 5

# ------------------------------------------------------------------
# Lot sizing bounds
# ------------------------------------------------------------------
DEFAULT_LOT_TYPE: str = "micro"
MIN_LOTS: float = 0.01
MAX_LOTS: float = 10.0

# ------------------------------------------------------------------
# Slippage
# ------------------------------------------------------------------
DEFAULT_SLIPPAGE_PIPS: float = 0.5
DEFAULT_MARKET_SLIPPAGE_PIPS: float = 0.3

# Variable slippage model
BASE_SLIPPAGE_PIPS: float = 0.3
NYSE_OPEN_SLIPPAGE_MULTIPLIER: float = 2.0  # 0.6 pips during NYSE open
NEWS_SLIPPAGE_MULTIPLIER: float = 5.0  # 1.5 pips during news events

# Variable spread model
BASE_SPREAD_PIPS: float = 0.8  # Normal conditions (EUR/USD)
NYSE_OPEN_SPREAD_PIPS: float = 1.5  # NYSE open window
NEWS_SPREAD_PIPS: float = 3.0  # High-impact news events

# Per-pair base spread in pips (normal market conditions)
BASE_SPREAD_BY_PAIR: dict[str, float] = {
    "EURUSD": 0.8,
    "GBPUSD": 1.2,
    "USDJPY": 0.9,
    "AUDUSD": 1.0,
    "USDCAD": 1.2,
    "USDCHF": 1.2,
    "NZDUSD": 1.5,
    "EURJPY": 2.0,
    "GBPJPY": 3.0,
}

# NYSE open window for slippage (first 5 minutes)
NYSE_OPEN_WINDOW_MINUTES: int = 5

# ------------------------------------------------------------------
# Pair correlation
# ------------------------------------------------------------------
DEFAULT_MAX_CORRELATION: float = 0.7
CORRELATION_RISK_DECAY: float = 0.5
CORRELATION_LOOKBACK_BARS: int = 100

# ------------------------------------------------------------------
# IB pacing limits
# ------------------------------------------------------------------
IB_MAX_REQUESTS_PER_10S: int = 50
IB_PACING_WINDOW_SECONDS: float = 10.0
IB_TIMEOUT_SECONDS: float = 15.0         # connection / order timeouts
IB_HIST_TIMEOUT_SECONDS: float = 60.0   # historical data requests (IB can be slow)

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
LOG_DIR: str = "alphaedge/logs"
LOG_ROTATION: str = "1 day"
LOG_RETENTION: str = "30 days"

if __name__ == "__main__":
    print(f"{PROJECT_TITLE} — Constants loaded successfully")
    print(f"  Pairs with pip sizes: {list(PIP_SIZES.keys())}")
    print(f"  Default RR: {DEFAULT_RR_RATIO}:1")
    print(f"  Default risk: {DEFAULT_RISK_PCT}%")
