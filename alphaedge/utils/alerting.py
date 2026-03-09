# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/utils/alerting.py
# DESCRIPTION  : External alerting via Telegram and Discord webhooks
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# ============================================================
"""ALPHAEDGE — External alerting: Telegram bot API + Discord webhooks."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from alphaedge.config.constants import PROJECT_NAME
from alphaedge.utils.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------------
# Alert types
# ------------------------------------------------------------------
class AlertLevel(Enum):
    """Severity level for alerts."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertEvent(Enum):
    """Named alert events."""

    SIGNAL_DETECTED = "signal_detected"
    TRADE_EXECUTED = "trade_executed"
    TRADE_CLOSED = "trade_closed"
    KILL_SWITCH = "kill_switch"
    IB_DISCONNECTED = "ib_disconnected"
    IB_RECONNECTED = "ib_reconnected"
    SESSION_END_OPEN = "session_end_open_position"
    SESSION_END_CLEAN = "session_end_clean"
    DAILY_SUMMARY = "daily_summary"


# ------------------------------------------------------------------
# Alert data
# ------------------------------------------------------------------
@dataclass(frozen=True)
class Alert:
    """A single alert message."""

    event: AlertEvent
    level: AlertLevel
    title: str
    message: str
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            ts = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
            object.__setattr__(self, "timestamp", ts)


# ------------------------------------------------------------------
# Alert formatting
# ------------------------------------------------------------------
_LEVEL_EMOJI: dict[AlertLevel, str] = {
    AlertLevel.INFO: "\u2139\ufe0f",
    AlertLevel.WARNING: "\u26a0\ufe0f",
    AlertLevel.CRITICAL: "\U0001f6a8",
}

_EVENT_EMOJI: dict[AlertEvent, str] = {
    AlertEvent.SIGNAL_DETECTED: "\U0001f50d",
    AlertEvent.TRADE_EXECUTED: "\u2705",
    AlertEvent.TRADE_CLOSED: "\U0001f4b0",
    AlertEvent.KILL_SWITCH: "\U0001f6d1",
    AlertEvent.IB_DISCONNECTED: "\U0001f534",
    AlertEvent.IB_RECONNECTED: "\U0001f7e2",
    AlertEvent.SESSION_END_OPEN: "\u26a0\ufe0f",
    AlertEvent.SESSION_END_CLEAN: "\u2705",
    AlertEvent.DAILY_SUMMARY: "\U0001f4ca",
}


def format_telegram(alert: Alert) -> str:
    """Format an alert for Telegram (HTML parse mode).

    Parameters
    ----------
    alert:
        The alert to format.

    Returns
    -------
    HTML-formatted string for Telegram.
    """
    emoji = _EVENT_EMOJI.get(alert.event, "")
    level_emoji = _LEVEL_EMOJI.get(alert.level, "")
    return (
        f"{emoji} <b>[{PROJECT_NAME}] {alert.title}</b>\n"
        f"{level_emoji} {alert.level.value}\n"
        f"{alert.message}\n"
        f"<i>{alert.timestamp}</i>"
    )


def format_discord(alert: Alert) -> dict[str, Any]:
    """Format an alert as a Discord webhook embed payload.

    Parameters
    ----------
    alert:
        The alert to format.

    Returns
    -------
    Dict suitable for Discord webhook JSON body.
    """
    color_map: dict[AlertLevel, int] = {
        AlertLevel.INFO: 0x3498DB,
        AlertLevel.WARNING: 0xF39C12,
        AlertLevel.CRITICAL: 0xE74C3C,
    }
    emoji = _EVENT_EMOJI.get(alert.event, "")
    return {
        "embeds": [
            {
                "title": f"{emoji} {alert.title}",
                "description": alert.message,
                "color": color_map.get(alert.level, 0x95A5A6),
                "footer": {"text": f"{PROJECT_NAME} | {alert.timestamp}"},
            }
        ]
    }


# ------------------------------------------------------------------
# Alert sender backends
# ------------------------------------------------------------------
@dataclass
class TelegramConfig:
    """Telegram Bot API configuration."""

    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = False


@dataclass
class DiscordConfig:
    """Discord webhook configuration."""

    webhook_url: str = ""
    enabled: bool = False


@dataclass
class AlertConfig:
    """Combined alerting configuration."""

    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    events: list[str] = field(default_factory=lambda: [e.value for e in AlertEvent])


def _is_event_enabled(event: AlertEvent, config: AlertConfig) -> bool:
    """Check whether a specific event type is enabled."""
    return event.value in config.events


# ------------------------------------------------------------------
# Send functions
# ------------------------------------------------------------------
def send_telegram(alert: Alert, config: TelegramConfig) -> bool:
    """Send an alert via Telegram Bot API (synchronous).

    Parameters
    ----------
    alert:
        The alert to send.
    config:
        Telegram configuration.

    Returns
    -------
    True if sent successfully, False otherwise.
    """
    if not config.enabled or not config.bot_token or not config.chat_id:
        return False

    url = f"https://api.telegram.org/bot{config.bot_token}/sendMessage"
    text = format_telegram(alert)
    payload = json.dumps(
        {"chat_id": config.chat_id, "text": text, "parse_mode": "HTML"}
    ).encode("utf-8")

    req = Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            return bool(resp.status == 200)
    except (URLError, OSError) as exc:
        logger.error(f"Telegram alert failed: {exc}")
        return False


def send_discord(alert: Alert, config: DiscordConfig) -> bool:
    """Send an alert via Discord webhook (synchronous).

    Parameters
    ----------
    alert:
        The alert to send.
    config:
        Discord configuration.

    Returns
    -------
    True if sent successfully, False otherwise.
    """
    if not config.enabled or not config.webhook_url:
        return False

    payload = json.dumps(format_discord(alert)).encode("utf-8")
    req = Request(config.webhook_url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            return resp.status in (200, 204)
    except (URLError, OSError) as exc:
        logger.error(f"Discord alert failed: {exc}")
        return False


# ------------------------------------------------------------------
# AlertManager — central dispatcher
# ------------------------------------------------------------------
class AlertManager:
    """Central alert dispatcher for all notification channels.

    Parameters
    ----------
    config:
        AlertConfig with Telegram/Discord settings and event filters.
    """

    def __init__(self, config: AlertConfig) -> None:
        self._config = config
        self._send_count: int = 0
        self._fail_count: int = 0

    @property
    def config(self) -> AlertConfig:
        """Current alert configuration."""
        return self._config

    @property
    def send_count(self) -> int:
        """Total successful sends."""
        return self._send_count

    @property
    def fail_count(self) -> int:
        """Total failed sends."""
        return self._fail_count

    def send(self, alert: Alert) -> bool:
        """Dispatch an alert to all enabled channels.

        Parameters
        ----------
        alert:
            The alert to send.

        Returns
        -------
        True if at least one channel succeeded.
        """
        if not _is_event_enabled(alert.event, self._config):
            return False

        any_success = False

        if self._config.telegram.enabled:
            ok = send_telegram(alert, self._config.telegram)
            if ok:
                self._send_count += 1
                any_success = True
            else:
                self._fail_count += 1

        if self._config.discord.enabled:
            ok = send_discord(alert, self._config.discord)
            if ok:
                self._send_count += 1
                any_success = True
            else:
                self._fail_count += 1

        if any_success:
            logger.info(f"Alert sent: {alert.event.value} — {alert.title}")
        else:
            logger.warning(f"Alert not delivered: {alert.event.value} — {alert.title}")

        return any_success

    async def send_async(self, alert: Alert) -> bool:
        """Dispatch alert in a thread pool to avoid blocking.

        Parameters
        ----------
        alert:
            The alert to send.

        Returns
        -------
        True if at least one channel succeeded.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.send, alert)


# ------------------------------------------------------------------
# Convenience alert builders
# ------------------------------------------------------------------
def alert_trade_executed(
    pair: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
) -> Alert:
    """Build an alert for a trade execution."""
    return Alert(
        event=AlertEvent.TRADE_EXECUTED,
        level=AlertLevel.INFO,
        title=f"Trade Opened: {pair} {direction}",
        message=(
            f"Entry: {entry_price:.5f}\nSL: {stop_loss:.5f}\nTP: {take_profit:.5f}"
        ),
    )


def alert_trade_closed(
    pair: str,
    direction: str,
    pnl_pips: float,
    pnl_usd: float,
    outcome: str,
) -> Alert:
    """Build an alert for a trade closure."""
    level = AlertLevel.INFO if outcome == "win" else AlertLevel.WARNING
    return Alert(
        event=AlertEvent.TRADE_CLOSED,
        level=level,
        title=f"Trade Closed: {pair} {direction} — {outcome.upper()}",
        message=f"P&L: {pnl_pips:+.1f} pips / ${pnl_usd:+.2f}",
    )


def alert_signal_detected(pair: str, direction: str) -> Alert:
    """Build an alert for a signal detection."""
    return Alert(
        event=AlertEvent.SIGNAL_DETECTED,
        level=AlertLevel.INFO,
        title=f"Signal: {pair} {direction}",
        message=f"FCR + Gap + Engulfing confirmed on {pair}.",
    )


def alert_kill_switch(reason: str, daily_pnl_pct: float) -> Alert:
    """Build an alert for kill-switch activation."""
    return Alert(
        event=AlertEvent.KILL_SWITCH,
        level=AlertLevel.CRITICAL,
        title="KILL SWITCH TRIGGERED",
        message=(
            f"Reason: {reason}\n"
            f"Daily P&L: {daily_pnl_pct:+.2f}%\n"
            f"All orders cancelled. Trading halted."
        ),
    )


def alert_ib_disconnected() -> Alert:
    """Build an alert for IB Gateway disconnection."""
    return Alert(
        event=AlertEvent.IB_DISCONNECTED,
        level=AlertLevel.CRITICAL,
        title="IB Gateway DISCONNECTED",
        message="Connection to Interactive Brokers lost. Attempting reconnection.",
    )


def alert_ib_reconnected() -> Alert:
    """Build an alert for IB Gateway reconnection."""
    return Alert(
        event=AlertEvent.IB_RECONNECTED,
        level=AlertLevel.INFO,
        title="IB Gateway Reconnected",
        message="Connection to Interactive Brokers restored.",
    )


def alert_session_end_open(pair: str, quantity: float) -> Alert:
    """Build an alert for open position at session end."""
    return Alert(
        event=AlertEvent.SESSION_END_OPEN,
        level=AlertLevel.WARNING,
        title=f"Session End: Open Position on {pair}",
        message=f"Quantity: {quantity}. Bracket SL/TP remains active on IB.",
    )


def alert_session_end_clean() -> Alert:
    """Build an alert for clean session end."""
    return Alert(
        event=AlertEvent.SESSION_END_CLEAN,
        level=AlertLevel.INFO,
        title="Session End: All Clear",
        message="No open positions. Session ended cleanly.",
    )


def alert_daily_summary(
    trades: int,
    wins: int,
    losses: int,
    pnl_usd: float,
) -> Alert:
    """Build a daily summary alert."""
    return Alert(
        event=AlertEvent.DAILY_SUMMARY,
        level=AlertLevel.INFO,
        title="Daily Summary",
        message=(f"Trades: {trades} (W: {wins} / L: {losses})\nP&L: ${pnl_usd:+.2f}"),
    )


# ------------------------------------------------------------------
# Config builder from YAML dict
# ------------------------------------------------------------------
def build_alert_config(raw: dict[str, Any]) -> AlertConfig:
    """Build AlertConfig from a raw YAML/dict section.

    Parameters
    ----------
    raw:
        Dict from config.yaml ``alerting`` section.

    Returns
    -------
    AlertConfig instance.
    """
    tg_raw = raw.get("telegram", {})
    dc_raw = raw.get("discord", {})

    telegram = TelegramConfig(
        bot_token=str(tg_raw.get("bot_token", "")),
        chat_id=str(tg_raw.get("chat_id", "")),
        enabled=bool(tg_raw.get("enabled", False)),
    )
    discord = DiscordConfig(
        webhook_url=str(dc_raw.get("webhook_url", "")),
        enabled=bool(dc_raw.get("enabled", False)),
    )
    events_raw = raw.get("events", [e.value for e in AlertEvent])
    events = [str(e) for e in events_raw]

    return AlertConfig(telegram=telegram, discord=discord, events=events)
