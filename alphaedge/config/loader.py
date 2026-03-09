# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/config/loader.py
# DESCRIPTION  : YAML config and .env loader with validation
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: configuration file loader."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from alphaedge.config.constants import (
    DEFAULT_MAX_DAILY_LOSS_PCT,
    DEFAULT_MAX_SPREAD_PIPS,
    DEFAULT_MAX_TRADES_PER_SESSION,
    DEFAULT_RISK_PCT,
    DEFAULT_RR_RATIO,
    IB_HOST,
    IB_PAPER_PORT,
    PIP_SIZES,
)


# ------------------------------------------------------------------
# Data class for IB connection settings
# ------------------------------------------------------------------
@dataclass
class IBConfig:
    """Interactive Brokers Gateway connection configuration."""

    host: str = IB_HOST
    port: int = IB_PAPER_PORT
    client_id: int = 1
    account_id: str = ""
    account_type: str = "Individual"
    is_paper: bool = True


# ------------------------------------------------------------------
# Data class for trading parameters
# ------------------------------------------------------------------
@dataclass
class TradingConfig:
    """Strategy and risk management parameters."""

    pairs: list[str] = field(default_factory=lambda: ["EURUSD", "GBPUSD", "USDJPY"])
    rr_ratio: float = DEFAULT_RR_RATIO
    risk_pct: float = DEFAULT_RISK_PCT
    max_daily_loss_pct: float = DEFAULT_MAX_DAILY_LOSS_PCT
    max_trades_per_session: int = DEFAULT_MAX_TRADES_PER_SESSION
    max_spread_pips: float = DEFAULT_MAX_SPREAD_PIPS
    spread_spike_multiplier: float = 3.0
    lot_type: str = "micro"
    session_start: str = "09:30"
    session_end: str = "10:30"
    session_end_action: str = "hold"
    london_open_enabled: bool = False
    min_body_ratio: float = 0.3
    max_wick_ratio: float = 2.0
    backtest_years: int = 3
    eur_usd_rate: float = 1.08
    starting_equity: float = 10000.0


# ------------------------------------------------------------------
# Data class for full application config
# ------------------------------------------------------------------
@dataclass
class AppConfig:
    """Complete application configuration container."""

    ib: IBConfig = field(default_factory=IBConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    log_level: str = "INFO"
    mode: str = "paper"
    news_filter_raw: dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------
# Load environment variables from .env
# ------------------------------------------------------------------
def _load_env(env_path: Path | None = None) -> None:
    """Load .env file into os.environ."""
    if env_path is None:
        env_path = Path(".env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)


# ------------------------------------------------------------------
# Load YAML config file
# ------------------------------------------------------------------
def _load_yaml(config_path: Path) -> dict[str, Any]:
    """
    Parse config.yaml and return its contents as a dict.

    Raises FileNotFoundError if the file does not exist.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh) or {}
    return data


# ------------------------------------------------------------------
# Build IBConfig from raw YAML + env data
# ------------------------------------------------------------------
def _build_ib_config(raw: dict[str, Any]) -> IBConfig:
    """Merge YAML ib section with env overrides."""
    ib_section: dict[str, Any] = raw.get("ib", {})

    # Env vars override YAML
    is_paper = os.getenv("ALPHAEDGE_PAPER", "true").lower() == "true"
    default_port = IB_PAPER_PORT if is_paper else 4001

    return IBConfig(
        host=os.getenv("ALPHAEDGE_IB_HOST", ib_section.get("host", IB_HOST)),
        port=int(os.getenv("ALPHAEDGE_IB_PORT", ib_section.get("port", default_port))),
        client_id=int(
            os.getenv("ALPHAEDGE_IB_CLIENT_ID", ib_section.get("client_id", 1))
        ),
        account_id=os.getenv("ALPHAEDGE_IB_ACCOUNT", ib_section.get("account_id", "")),
        account_type=ib_section.get("account_type", "Individual"),
        is_paper=is_paper,
    )


def _check_ib_port(port: int) -> None:
    """Warn if IB port is not one of the standard Gateway ports."""
    from alphaedge.utils.logger import get_logger

    if port not in (4001, 4002):
        get_logger().warning(
            f"ALPHAEDGE CONFIG: Non-standard IB port {port} "
            f"(expected 4001 for live or 4002 for paper)"
        )


# ------------------------------------------------------------------
# Build TradingConfig from raw YAML data
# ------------------------------------------------------------------
def _build_trading_config(raw: dict[str, Any]) -> TradingConfig:
    """Extract and validate trading parameters from the YAML section."""
    section: dict[str, Any] = raw.get("trading", {})
    eng_section: dict[str, Any] = raw.get("engulfing", {})
    cfg = TradingConfig(
        pairs=section.get("pairs", ["EURUSD", "GBPUSD", "USDJPY"]),
        rr_ratio=float(section.get("rr_ratio", DEFAULT_RR_RATIO)),
        risk_pct=float(section.get("risk_pct", DEFAULT_RISK_PCT)),
        max_daily_loss_pct=float(
            section.get("max_daily_loss_pct", DEFAULT_MAX_DAILY_LOSS_PCT)
        ),
        max_trades_per_session=int(
            section.get("max_trades_per_session", DEFAULT_MAX_TRADES_PER_SESSION)
        ),
        max_spread_pips=float(section.get("max_spread_pips", DEFAULT_MAX_SPREAD_PIPS)),
        spread_spike_multiplier=float(section.get("spread_spike_multiplier", 3.0)),
        lot_type=section.get("lot_type", "micro"),
        session_start=section.get("session_start", "09:30"),
        session_end=section.get("session_end", "10:30"),
        session_end_action=section.get("session_end_action", "hold"),
        london_open_enabled=bool(section.get("london_open_enabled", False)),
        min_body_ratio=float(eng_section.get("min_body_ratio", 0.3)),
        max_wick_ratio=float(eng_section.get("max_wick_ratio", 2.0)),
        backtest_years=int(section.get("backtest_years", 3)),
        eur_usd_rate=float(section.get("eur_usd_rate", 1.08)),
        starting_equity=float(section.get("starting_equity", 10000.0)),
    )
    _validate_trading_config(cfg)
    return cfg


def _validate_trading_config(cfg: TradingConfig) -> None:
    """Validate trading config values are within safe ranges."""
    # Pair validation: all configured pairs must be in PIP_SIZES
    for pair in cfg.pairs:
        if pair not in PIP_SIZES:
            raise ValueError(
                f"Unknown pair '{pair}'. Supported: {sorted(PIP_SIZES.keys())}"
            )
    # lot_type validation
    if cfg.lot_type not in ("standard", "mini", "micro"):
        raise ValueError(
            f"Invalid lot_type '{cfg.lot_type}'. Must be standard/mini/micro."
        )
    if not 0.0 < cfg.risk_pct <= 10.0:
        raise ValueError(f"risk_pct must be in (0, 10], got {cfg.risk_pct}")
    if cfg.rr_ratio <= 0.0:
        raise ValueError(f"rr_ratio must be > 0, got {cfg.rr_ratio}")
    if cfg.max_daily_loss_pct <= 0.0:
        raise ValueError(
            f"max_daily_loss_pct must be > 0, got {cfg.max_daily_loss_pct}"
        )
    if cfg.max_trades_per_session <= 0:
        raise ValueError(
            f"max_trades_per_session must be > 0, got {cfg.max_trades_per_session}"
        )
    if cfg.max_spread_pips <= 0.0:
        raise ValueError(f"max_spread_pips must be > 0, got {cfg.max_spread_pips}")


# ------------------------------------------------------------------
# Public: load full application config
# ------------------------------------------------------------------
def load_config(
    config_path: str | Path = "config.yaml",
    env_path: str | Path | None = None,
) -> AppConfig:
    """
    Load and merge config.yaml + .env into an AppConfig dataclass.

    Parameters
    ----------
    config_path : str | Path
        Path to the YAML configuration file.
    env_path : str | Path | None
        Path to the .env file. Defaults to '.env' in cwd.

    Returns
    -------
    AppConfig
        Fully populated application configuration.
    """
    # Load environment variables first (they can override YAML)
    _load_env(Path(env_path) if env_path else None)

    # Load YAML
    raw = _load_yaml(Path(config_path))

    # Build sub-configs
    ib_cfg = _build_ib_config(raw)
    _check_ib_port(ib_cfg.port)
    trading_cfg = _build_trading_config(raw)

    return AppConfig(
        ib=ib_cfg,
        trading=trading_cfg,
        log_level=raw.get("log_level", "INFO"),
        mode="paper" if ib_cfg.is_paper else "live",
        news_filter_raw=raw.get("news_filter", {}),
    )


if __name__ == "__main__":
    try:
        cfg = load_config()
        print(f"ALPHAEDGE config loaded: mode={cfg.mode}")
        print(f"  IB: {cfg.ib.host}:{cfg.ib.port}")
        print(f"  Pairs: {cfg.trading.pairs}")
    except FileNotFoundError as exc:
        print(f"Config error: {exc}")
