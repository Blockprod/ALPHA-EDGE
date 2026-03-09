# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/tests/test_alerting.py
# DESCRIPTION  : Tests for external alerting module
# ============================================================
"""ALPHAEDGE — T4.6: Alerting module tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from alphaedge.config.constants import PROJECT_NAME
from alphaedge.utils.alerting import (
    Alert,
    AlertConfig,
    AlertEvent,
    AlertLevel,
    AlertManager,
    DiscordConfig,
    TelegramConfig,
    alert_daily_summary,
    alert_ib_disconnected,
    alert_ib_reconnected,
    alert_kill_switch,
    alert_session_end_clean,
    alert_session_end_open,
    alert_signal_detected,
    alert_trade_closed,
    alert_trade_executed,
    build_alert_config,
    format_discord,
    format_telegram,
    send_discord,
    send_telegram,
)


# ------------------------------------------------------------------
# AlertLevel enum
# ------------------------------------------------------------------
class TestAlertLevel:
    def test_values(self) -> None:
        assert AlertLevel.INFO.value == "INFO"
        assert AlertLevel.WARNING.value == "WARNING"
        assert AlertLevel.CRITICAL.value == "CRITICAL"


# ------------------------------------------------------------------
# AlertEvent enum
# ------------------------------------------------------------------
class TestAlertEvent:
    def test_all_events(self) -> None:
        assert len(AlertEvent) == 9
        assert AlertEvent.SIGNAL_DETECTED.value == "signal_detected"
        assert AlertEvent.KILL_SWITCH.value == "kill_switch"
        assert AlertEvent.IB_DISCONNECTED.value == "ib_disconnected"
        assert AlertEvent.SESSION_END_OPEN.value == "session_end_open_position"
        assert AlertEvent.DAILY_SUMMARY.value == "daily_summary"


# ------------------------------------------------------------------
# Alert dataclass
# ------------------------------------------------------------------
class TestAlert:
    def test_auto_timestamp(self) -> None:
        a = Alert(
            event=AlertEvent.KILL_SWITCH,
            level=AlertLevel.CRITICAL,
            title="Test",
            message="msg",
        )
        assert a.timestamp != ""
        assert "UTC" in a.timestamp

    def test_explicit_timestamp(self) -> None:
        a = Alert(
            event=AlertEvent.KILL_SWITCH,
            level=AlertLevel.CRITICAL,
            title="Test",
            message="msg",
            timestamp="2026-03-08 10:00:00 UTC",
        )
        assert a.timestamp == "2026-03-08 10:00:00 UTC"

    def test_frozen(self) -> None:
        a = Alert(
            event=AlertEvent.KILL_SWITCH,
            level=AlertLevel.CRITICAL,
            title="Test",
            message="msg",
        )
        with pytest.raises(AttributeError):
            setattr(a, "title", "changed")


# ------------------------------------------------------------------
# format_telegram
# ------------------------------------------------------------------
class TestFormatTelegram:
    def test_contains_html_bold(self) -> None:
        a = Alert(
            event=AlertEvent.TRADE_EXECUTED,
            level=AlertLevel.INFO,
            title="Trade Opened",
            message="EURUSD BUY",
        )
        text = format_telegram(a)
        assert "<b>" in text
        assert PROJECT_NAME in text
        assert "Trade Opened" in text
        assert "EURUSD BUY" in text

    def test_level_in_output(self) -> None:
        a = Alert(
            event=AlertEvent.KILL_SWITCH,
            level=AlertLevel.CRITICAL,
            title="Kill",
            message="test",
        )
        text = format_telegram(a)
        assert "CRITICAL" in text

    def test_timestamp_italic(self) -> None:
        a = Alert(
            event=AlertEvent.DAILY_SUMMARY,
            level=AlertLevel.INFO,
            title="Summary",
            message="...",
            timestamp="2026-03-08 10:00:00 UTC",
        )
        text = format_telegram(a)
        assert "<i>2026-03-08 10:00:00 UTC</i>" in text


# ------------------------------------------------------------------
# format_discord
# ------------------------------------------------------------------
class TestFormatDiscord:
    def test_embed_structure(self) -> None:
        a = Alert(
            event=AlertEvent.TRADE_EXECUTED,
            level=AlertLevel.INFO,
            title="Trade Opened",
            message="EURUSD BUY",
        )
        d = format_discord(a)
        assert "embeds" in d
        assert len(d["embeds"]) == 1
        embed = d["embeds"][0]
        assert "Trade Opened" in embed["title"]
        assert embed["description"] == "EURUSD BUY"
        assert isinstance(embed["color"], int)
        assert PROJECT_NAME in embed["footer"]["text"]

    def test_critical_color(self) -> None:
        a = Alert(
            event=AlertEvent.KILL_SWITCH,
            level=AlertLevel.CRITICAL,
            title="Kill",
            message="msg",
        )
        d = format_discord(a)
        assert d["embeds"][0]["color"] == 0xE74C3C

    def test_warning_color(self) -> None:
        a = Alert(
            event=AlertEvent.SESSION_END_OPEN,
            level=AlertLevel.WARNING,
            title="Open",
            message="msg",
        )
        d = format_discord(a)
        assert d["embeds"][0]["color"] == 0xF39C12


# ------------------------------------------------------------------
# Config classes
# ------------------------------------------------------------------
class TestConfigs:
    def test_telegram_config_defaults(self) -> None:
        c = TelegramConfig()
        assert c.bot_token == ""
        assert c.chat_id == ""
        assert c.enabled is False

    def test_discord_config_defaults(self) -> None:
        c = DiscordConfig()
        assert c.webhook_url == ""
        assert c.enabled is False

    def test_alert_config_defaults(self) -> None:
        c = AlertConfig()
        assert c.telegram.enabled is False
        assert c.discord.enabled is False
        assert len(c.events) == 9


# ------------------------------------------------------------------
# send_telegram
# ------------------------------------------------------------------
class TestSendTelegram:
    def test_disabled_returns_false(self) -> None:
        cfg = TelegramConfig(enabled=False)
        a = Alert(
            event=AlertEvent.KILL_SWITCH,
            level=AlertLevel.CRITICAL,
            title="t",
            message="m",
        )
        assert send_telegram(a, cfg) is False

    def test_empty_token_returns_false(self) -> None:
        cfg = TelegramConfig(enabled=True, bot_token="", chat_id="123")
        a = Alert(
            event=AlertEvent.KILL_SWITCH,
            level=AlertLevel.CRITICAL,
            title="t",
            message="m",
        )
        assert send_telegram(a, cfg) is False

    @patch("alphaedge.utils.alerting.urlopen")
    def test_success(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        cfg = TelegramConfig(enabled=True, bot_token="tok", chat_id="123")
        a = Alert(
            event=AlertEvent.TRADE_EXECUTED,
            level=AlertLevel.INFO,
            title="Trade",
            message="msg",
        )
        assert send_telegram(a, cfg) is True
        mock_urlopen.assert_called_once()

        # Verify the request
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert "api.telegram.org" in req.full_url
        assert req.method == "POST"

    @patch("alphaedge.utils.alerting.urlopen")
    def test_network_error(self, mock_urlopen: MagicMock) -> None:
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("timeout")

        cfg = TelegramConfig(enabled=True, bot_token="tok", chat_id="123")
        a = Alert(
            event=AlertEvent.KILL_SWITCH,
            level=AlertLevel.CRITICAL,
            title="t",
            message="m",
        )
        assert send_telegram(a, cfg) is False


# ------------------------------------------------------------------
# send_discord
# ------------------------------------------------------------------
class TestSendDiscord:
    def test_disabled_returns_false(self) -> None:
        cfg = DiscordConfig(enabled=False)
        a = Alert(
            event=AlertEvent.KILL_SWITCH,
            level=AlertLevel.CRITICAL,
            title="t",
            message="m",
        )
        assert send_discord(a, cfg) is False

    def test_empty_url_returns_false(self) -> None:
        cfg = DiscordConfig(enabled=True, webhook_url="")
        a = Alert(
            event=AlertEvent.KILL_SWITCH,
            level=AlertLevel.CRITICAL,
            title="t",
            message="m",
        )
        assert send_discord(a, cfg) is False

    @patch("alphaedge.utils.alerting.urlopen")
    def test_success_204(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        cfg = DiscordConfig(
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/test",
        )
        a = Alert(
            event=AlertEvent.TRADE_EXECUTED,
            level=AlertLevel.INFO,
            title="Trade",
            message="msg",
        )
        assert send_discord(a, cfg) is True

    @patch("alphaedge.utils.alerting.urlopen")
    def test_network_error(self, mock_urlopen: MagicMock) -> None:
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("connection refused")

        cfg = DiscordConfig(
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/test",
        )
        a = Alert(
            event=AlertEvent.KILL_SWITCH,
            level=AlertLevel.CRITICAL,
            title="t",
            message="m",
        )
        assert send_discord(a, cfg) is False


# ------------------------------------------------------------------
# AlertManager
# ------------------------------------------------------------------
class TestAlertManager:
    def _make_config(
        self,
        tg_enabled: bool = False,
        dc_enabled: bool = False,
    ) -> AlertConfig:
        return AlertConfig(
            telegram=TelegramConfig(enabled=tg_enabled, bot_token="tok", chat_id="123"),
            discord=DiscordConfig(
                enabled=dc_enabled,
                webhook_url="https://discord.com/api/webhooks/test",
            ),
        )

    def test_initial_counts(self) -> None:
        mgr = AlertManager(self._make_config())
        assert mgr.send_count == 0
        assert mgr.fail_count == 0

    def test_config_property(self) -> None:
        cfg = self._make_config()
        mgr = AlertManager(cfg)
        assert mgr.config is cfg

    @patch("alphaedge.utils.alerting.send_telegram", return_value=True)
    def test_send_telegram_success(self, mock_tg: MagicMock) -> None:
        mgr = AlertManager(self._make_config(tg_enabled=True))
        a = Alert(
            event=AlertEvent.TRADE_EXECUTED,
            level=AlertLevel.INFO,
            title="t",
            message="m",
        )
        assert mgr.send(a) is True
        assert mgr.send_count == 1
        assert mgr.fail_count == 0

    @patch("alphaedge.utils.alerting.send_discord", return_value=True)
    def test_send_discord_success(self, mock_dc: MagicMock) -> None:
        mgr = AlertManager(self._make_config(dc_enabled=True))
        a = Alert(
            event=AlertEvent.TRADE_EXECUTED,
            level=AlertLevel.INFO,
            title="t",
            message="m",
        )
        assert mgr.send(a) is True
        assert mgr.send_count == 1

    @patch("alphaedge.utils.alerting.send_telegram", return_value=True)
    @patch("alphaedge.utils.alerting.send_discord", return_value=True)
    def test_send_both(self, mock_dc: MagicMock, mock_tg: MagicMock) -> None:
        mgr = AlertManager(self._make_config(tg_enabled=True, dc_enabled=True))
        a = Alert(
            event=AlertEvent.TRADE_EXECUTED,
            level=AlertLevel.INFO,
            title="t",
            message="m",
        )
        assert mgr.send(a) is True
        assert mgr.send_count == 2

    @patch("alphaedge.utils.alerting.send_telegram", return_value=False)
    def test_send_failure_counted(self, mock_tg: MagicMock) -> None:
        mgr = AlertManager(self._make_config(tg_enabled=True))
        a = Alert(
            event=AlertEvent.TRADE_EXECUTED,
            level=AlertLevel.INFO,
            title="t",
            message="m",
        )
        assert mgr.send(a) is False
        assert mgr.send_count == 0
        assert mgr.fail_count == 1

    def test_event_filtering(self) -> None:
        cfg = self._make_config(tg_enabled=True)
        cfg.events = ["kill_switch"]  # only kill_switch
        mgr = AlertManager(cfg)

        a = Alert(
            event=AlertEvent.TRADE_EXECUTED,
            level=AlertLevel.INFO,
            title="t",
            message="m",
        )
        assert mgr.send(a) is False
        assert mgr.send_count == 0
        assert mgr.fail_count == 0  # Not even attempted

    @pytest.mark.asyncio
    @patch("alphaedge.utils.alerting.send_telegram", return_value=True)
    async def test_send_async(self, mock_tg: MagicMock) -> None:
        mgr = AlertManager(self._make_config(tg_enabled=True))
        a = Alert(
            event=AlertEvent.TRADE_EXECUTED,
            level=AlertLevel.INFO,
            title="t",
            message="m",
        )
        result = await mgr.send_async(a)
        assert result is True
        assert mgr.send_count == 1

    def test_no_channels_enabled(self) -> None:
        mgr = AlertManager(self._make_config())
        a = Alert(
            event=AlertEvent.TRADE_EXECUTED,
            level=AlertLevel.INFO,
            title="t",
            message="m",
        )
        assert mgr.send(a) is False


# ------------------------------------------------------------------
# Convenience alert builders
# ------------------------------------------------------------------
class TestAlertBuilders:
    def test_alert_trade_executed(self) -> None:
        a = alert_trade_executed("EURUSD", "BUY", 1.085, 1.082, 1.094)
        assert a.event == AlertEvent.TRADE_EXECUTED
        assert a.level == AlertLevel.INFO
        assert "EURUSD" in a.title
        assert "BUY" in a.title
        assert "1.08500" in a.message

    def test_alert_trade_closed_win(self) -> None:
        a = alert_trade_closed("EURUSD", "BUY", 9.0, 90.0, "win")
        assert a.event == AlertEvent.TRADE_CLOSED
        assert a.level == AlertLevel.INFO
        assert "WIN" in a.title

    def test_alert_trade_closed_loss(self) -> None:
        a = alert_trade_closed("EURUSD", "BUY", -3.0, -30.0, "loss")
        assert a.level == AlertLevel.WARNING

    def test_alert_signal_detected(self) -> None:
        a = alert_signal_detected("GBPUSD", "SELL")
        assert a.event == AlertEvent.SIGNAL_DETECTED
        assert "GBPUSD" in a.title

    def test_alert_kill_switch(self) -> None:
        a = alert_kill_switch("daily_loss_limit", -3.5)
        assert a.event == AlertEvent.KILL_SWITCH
        assert a.level == AlertLevel.CRITICAL
        assert "KILL SWITCH" in a.title
        assert "-3.50%" in a.message

    def test_alert_ib_disconnected(self) -> None:
        a = alert_ib_disconnected()
        assert a.event == AlertEvent.IB_DISCONNECTED
        assert a.level == AlertLevel.CRITICAL

    def test_alert_ib_reconnected(self) -> None:
        a = alert_ib_reconnected()
        assert a.event == AlertEvent.IB_RECONNECTED
        assert a.level == AlertLevel.INFO

    def test_alert_session_end_open(self) -> None:
        a = alert_session_end_open("EURUSD", 10000.0)
        assert a.event == AlertEvent.SESSION_END_OPEN
        assert a.level == AlertLevel.WARNING
        assert "EURUSD" in a.title

    def test_alert_session_end_clean(self) -> None:
        a = alert_session_end_clean()
        assert a.event == AlertEvent.SESSION_END_CLEAN
        assert a.level == AlertLevel.INFO

    def test_alert_daily_summary(self) -> None:
        a = alert_daily_summary(trades=5, wins=3, losses=2, pnl_usd=150.0)
        assert a.event == AlertEvent.DAILY_SUMMARY
        assert "5" in a.message
        assert "+150.00" in a.message


# ------------------------------------------------------------------
# build_alert_config
# ------------------------------------------------------------------
class TestBuildAlertConfig:
    def test_from_empty_dict(self) -> None:
        cfg = build_alert_config({})
        assert cfg.telegram.enabled is False
        assert cfg.discord.enabled is False
        assert len(cfg.events) == 9

    def test_telegram_enabled(self) -> None:
        raw: dict[str, Any] = {
            "telegram": {
                "enabled": True,
                "bot_token": "123:ABC",
                "chat_id": "-100123",
            }
        }
        cfg = build_alert_config(raw)
        assert cfg.telegram.enabled is True
        assert cfg.telegram.bot_token == "123:ABC"
        assert cfg.telegram.chat_id == "-100123"

    def test_discord_enabled(self) -> None:
        raw: dict[str, Any] = {
            "discord": {
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/test/token",
            }
        }
        cfg = build_alert_config(raw)
        assert cfg.discord.enabled is True
        assert "discord.com" in cfg.discord.webhook_url

    def test_custom_events(self) -> None:
        raw: dict[str, Any] = {
            "events": ["kill_switch", "ib_disconnected"],
        }
        cfg = build_alert_config(raw)
        assert len(cfg.events) == 2
        assert "kill_switch" in cfg.events
        assert "trade_executed" not in cfg.events

    def test_full_config(self) -> None:
        raw: dict[str, Any] = {
            "telegram": {
                "enabled": True,
                "bot_token": "tok",
                "chat_id": "123",
            },
            "discord": {
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/x/y",
            },
            "events": ["kill_switch", "trade_executed"],
        }
        cfg = build_alert_config(raw)
        assert cfg.telegram.enabled is True
        assert cfg.discord.enabled is True
        assert len(cfg.events) == 2
