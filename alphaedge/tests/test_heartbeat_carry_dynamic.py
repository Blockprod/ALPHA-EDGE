# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/tests/test_heartbeat_carry_dynamic.py
# DESCRIPTION  : P7 — BrokerConnection heartbeat + carry rate file reload
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-04-07
# ============================================================
"""ALPHAEDGE — P7 tests: heartbeat reconnect trigger + carry file reload."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.loader import (
    TradingConfig,
    load_carry_rates_from_file,
    load_config,
)


# ==============================================================================
# P7-01 — BrokerConnection heartbeat
# ==============================================================================
class TestHeartbeatLoop:
    """_heartbeat_loop triggers reconnect after max_misses consecutive misses."""

    def _make_broker(self) -> Any:
        """Build a minimal BrokerConnection with mocked IB client."""
        from alphaedge.config.loader import IBConfig
        from alphaedge.engine.broker import BrokerConnection

        cfg = IBConfig(host="127.0.0.1", port=4002, client_id=1, is_paper=True)
        with patch("alphaedge.engine.broker.IB"):
            broker = BrokerConnection(cfg)
        return broker

    @pytest.mark.asyncio
    async def test_heartbeat_no_miss_on_connected(self) -> None:
        """When connected, heartbeat must NOT increment miss counter."""
        broker = self._make_broker()
        broker._ib = MagicMock()
        broker._ib.isConnected.return_value = True
        broker._heartbeat_misses = 0

        # Run two iterations with interval=0 (instant), then cancel
        task = asyncio.ensure_future(broker._heartbeat_loop(interval=0, max_misses=2))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert broker._heartbeat_misses == 0

    @pytest.mark.asyncio
    async def test_heartbeat_increments_miss_counter(self) -> None:
        """When disconnected, each probe increments miss counter."""
        broker = self._make_broker()
        broker._ib = MagicMock()
        broker._ib.isConnected.return_value = False
        broker._heartbeat_misses = 0
        broker.reconnect = AsyncMock(return_value=True)

        task = asyncio.ensure_future(broker._heartbeat_loop(interval=0, max_misses=5))
        # Allow 1 probe cycle
        await asyncio.sleep(0.02)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert broker._heartbeat_misses >= 1

    @pytest.mark.asyncio
    async def test_heartbeat_triggers_reconnect_after_max_misses(self) -> None:
        """After max_misses misses, _heartbeat_loop calls reconnect()."""
        broker = self._make_broker()
        broker._ib = MagicMock()
        broker._ib.isConnected.return_value = False
        broker._heartbeat_misses = 0

        reconnect_called = asyncio.Event()

        async def _fake_reconnect(*_: Any, **__: Any) -> bool:
            reconnect_called.set()
            broker._ib.isConnected.return_value = True  # simulate success
            return True

        broker.reconnect = _fake_reconnect

        task = asyncio.ensure_future(broker._heartbeat_loop(interval=0, max_misses=2))
        # Wait for reconnect to be triggered (max 2s)
        await asyncio.wait_for(reconnect_called.wait(), timeout=2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert reconnect_called.is_set()

    @pytest.mark.asyncio
    async def test_heartbeat_resets_miss_counter_after_reconnect(self) -> None:
        """After reconnect, miss counter is reset to 0."""
        broker = self._make_broker()
        broker._ib = MagicMock()
        broker._ib.isConnected.return_value = False
        broker._heartbeat_misses = 0

        reconnected = asyncio.Event()

        async def _fake_reconnect(*_: Any, **__: Any) -> bool:
            broker._ib.isConnected.return_value = True
            reconnected.set()
            return True

        broker.reconnect = _fake_reconnect

        task = asyncio.ensure_future(broker._heartbeat_loop(interval=0, max_misses=2))
        await asyncio.wait_for(reconnected.wait(), timeout=2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert broker._heartbeat_misses == 0

    @pytest.mark.asyncio
    async def test_stop_heartbeat_cancels_task(self) -> None:
        """stop_heartbeat() cancels the running heartbeat task."""
        broker = self._make_broker()
        broker._ib = MagicMock()
        broker._ib.isConnected.return_value = True

        broker.start_heartbeat(interval=60, max_misses=3)
        assert broker._heartbeat_task is not None
        assert not broker._heartbeat_task.done()

        await broker.stop_heartbeat()

        assert broker._heartbeat_task is None

    def test_start_heartbeat_idempotent(self) -> None:
        """Calling start_heartbeat() twice does not create a second task."""
        broker = self._make_broker()
        broker._ib = MagicMock()
        broker._ib.isConnected.return_value = True

        loop = asyncio.new_event_loop()
        try:

            async def _run() -> None:
                broker.start_heartbeat(interval=60)
                first_task = broker._heartbeat_task
                broker.start_heartbeat(interval=60)
                assert broker._heartbeat_task is first_task, (
                    "start_heartbeat must be idempotent"
                )
                await broker.stop_heartbeat()

            loop.run_until_complete(_run())
        finally:
            loop.close()


# ==============================================================================
# P7-02 — load_carry_rates_from_file
# ==============================================================================
class TestLoadCarryRatesFromFile:
    """load_carry_rates_from_file: valid file, missing file, invalid JSON."""

    def test_valid_file_returns_rates(self, tmp_path: Path) -> None:
        """Valid JSON file with correct structure returns a dict[str, float]."""
        rates = {"EUR": 3.65, "USD": 5.25, "JPY": 0.10}
        f = tmp_path / "carry_rates.json"
        f.write_text(json.dumps(rates), encoding="utf-8")

        result = load_carry_rates_from_file(f)

        assert result == pytest.approx({"EUR": 3.65, "USD": 5.25, "JPY": 0.10})

    def test_keys_are_uppercased(self, tmp_path: Path) -> None:
        """Keys are normalised to uppercase regardless of input case."""
        rates = {"eur": 3.65, "usd": 5.25}
        f = tmp_path / "carry_rates.json"
        f.write_text(json.dumps(rates), encoding="utf-8")

        result = load_carry_rates_from_file(f)

        assert "EUR" in result
        assert "USD" in result

    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        """FileNotFoundError is raised when the file does not exist."""
        with pytest.raises(FileNotFoundError, match="carry rates file not found"):
            load_carry_rates_from_file(tmp_path / "nonexistent.json")

    def test_non_dict_json_raises_value_error(self, tmp_path: Path) -> None:
        """A JSON array (not a dict) raises ValueError."""
        f = tmp_path / "carry_rates.json"
        f.write_text("[1, 2, 3]", encoding="utf-8")

        with pytest.raises(ValueError, match="must be a JSON object"):
            load_carry_rates_from_file(f)

    def test_invalid_rate_value_raises_value_error(self, tmp_path: Path) -> None:
        """A non-numeric rate value raises ValueError."""
        f = tmp_path / "carry_rates.json"
        f.write_text(json.dumps({"EUR": "not_a_number"}), encoding="utf-8")

        with pytest.raises(ValueError, match="invalid carry rate value"):
            load_carry_rates_from_file(f)


# ==============================================================================
# P7-02 — carry_rates_source parsed by loader
# ==============================================================================
class TestCarryRatesSourceConfig:
    """carry_rates_source field is parsed correctly from YAML."""

    def test_default_is_static(self) -> None:
        """TradingConfig defaults carry_rates_source to 'static'."""
        cfg = TradingConfig()
        assert cfg.carry_rates_source == "static"

    def test_file_source_parsed_from_yaml(self, tmp_path: Path) -> None:
        """carry_rates_source: 'file' is loaded from the carry YAML section."""
        yaml_content = """\
ib:
  host: 127.0.0.1
  port: 4002
  client_id: 1
  account_id: ""
trading:
  pairs: [EURUSD]
carry:
  enabled: true
  carry_rates_source: "file"
  rates: {}
"""
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml_content, encoding="utf-8")

        config = load_config(config_path=cfg_path)
        assert config.trading.carry_rates_source == "file"

    def test_static_source_is_default_in_yaml(self, tmp_path: Path) -> None:
        """When carry_rates_source is absent from YAML, defaults to 'static'."""
        yaml_content = """\
ib:
  host: 127.0.0.1
  port: 4002
  client_id: 1
  account_id: ""
trading:
  pairs: [EURUSD]
carry:
  enabled: true
  rates: {}
"""
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(yaml_content, encoding="utf-8")

        config = load_config(config_path=cfg_path)
        assert config.trading.carry_rates_source == "static"
