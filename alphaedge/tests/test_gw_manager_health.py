# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_gw_manager_health.py
# DESCRIPTION  : Gateway health checker — detect, validate, retry, auto-login
# PYTHON       : 3.11.9
# ============================================================
"""Tests for gw_manager: process detection, port probe, API, launch, modes."""

from __future__ import annotations

import pathlib
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.loader import IBConfig
from alphaedge.utils.gw_manager import (
    _is_api_port_open,
    _is_gateway_process_running,
    _normalize_login_mode,
    _resolve_gateway_executable,
    _start_gateway_process,
    _validate_api_connection,
    ensure_gateway_ready,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _force_weekday(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests always run as if it were a weekday."""
    monkeypatch.setattr("alphaedge.utils.gw_manager._is_weekend", lambda: False)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make_config() -> IBConfig:
    """Build an IBConfig for testing."""
    return IBConfig(
        host="127.0.0.1",
        port=4002,
        client_id=1,
        account_id="DU123456",
        is_paper=True,
    )


def test_normalize_login_mode_defaults_invalid_value() -> None:
    assert _normalize_login_mode("bogus") == "manual"


def test_normalize_login_mode_accepts_ibc() -> None:
    assert _normalize_login_mode("IBC") == "ibc"


def test_normalize_login_mode_rejects_legacy_pywinauto() -> None:
    assert _normalize_login_mode("pywinauto") == "manual"


# ==================================================================
# _is_gateway_process_running
# ==================================================================
class TestIsGatewayProcessRunning:
    """Process detection via tasklist.exe."""

    @patch("alphaedge.utils.gw_manager.subprocess.run")
    def test_process_found(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout='"ibgateway.exe","12345","Console","1","456,789 K"'
        )
        assert _is_gateway_process_running() is True

    @patch("alphaedge.utils.gw_manager.subprocess.run")
    def test_renamed_process_found(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout='"ibgateway1.exe","12345","Console","1","456,789 K"'
        )
        assert _is_gateway_process_running() is True

    @patch("alphaedge.utils.gw_manager.subprocess.run")
    def test_process_not_found(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="INFO: No tasks are running which match."
        )
        assert _is_gateway_process_running() is False

    @patch("alphaedge.utils.gw_manager.subprocess.run")
    def test_timeout_returns_false(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tasklist", timeout=10)
        assert _is_gateway_process_running() is False

    @patch("alphaedge.utils.gw_manager.subprocess.run")
    def test_oserror_returns_false(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = OSError("tasklist not found")
        assert _is_gateway_process_running() is False


# ==================================================================
# _is_api_port_open
# ==================================================================
class TestIsApiPortOpen:
    """TCP port probe."""

    @patch("alphaedge.utils.gw_manager.socket.create_connection")
    def test_port_open(self, mock_conn: MagicMock) -> None:
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        assert _is_api_port_open("127.0.0.1", 4002) is True

    @patch("alphaedge.utils.gw_manager.socket.create_connection")
    def test_port_refused(self, mock_conn: MagicMock) -> None:
        mock_conn.side_effect = ConnectionRefusedError()
        assert _is_api_port_open("127.0.0.1", 4002) is False

    @patch("alphaedge.utils.gw_manager.socket.create_connection")
    def test_port_timeout(self, mock_conn: MagicMock) -> None:
        mock_conn.side_effect = TimeoutError()
        assert _is_api_port_open("127.0.0.1", 4002) is False

    @patch("alphaedge.utils.gw_manager.socket.create_connection")
    def test_port_oserror(self, mock_conn: MagicMock) -> None:
        mock_conn.side_effect = OSError("network unreachable")
        assert _is_api_port_open("127.0.0.1", 4002) is False


# ==================================================================
# _validate_api_connection
# ==================================================================
class TestValidateApiConnection:
    """Lightweight ib_insync connection probe."""

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        config = _make_config()
        mock_ib = MagicMock()
        mock_ib.client.connectAsync = AsyncMock()
        mock_ib.client.isReady = MagicMock(return_value=True)
        mock_ib.disconnect = MagicMock()
        with patch("ib_insync.IB", return_value=mock_ib):
            result = await _validate_api_connection(config)
        assert result is True
        mock_ib.disconnect.assert_called()

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        config = _make_config()
        mock_ib = MagicMock()
        mock_ib.client.connectAsync = AsyncMock(side_effect=TimeoutError())
        mock_ib.client.isReady = MagicMock(return_value=False)
        with patch("ib_insync.IB", return_value=mock_ib):
            result = await _validate_api_connection(config)
        assert result is False

    @pytest.mark.asyncio
    async def test_connection_error(self) -> None:
        config = _make_config()
        mock_ib = MagicMock()
        mock_ib.client.connectAsync = AsyncMock(side_effect=ConnectionError())
        mock_ib.client.isReady = MagicMock(return_value=False)
        with patch("ib_insync.IB", return_value=mock_ib):
            result = await _validate_api_connection(config)
        assert result is False

    @pytest.mark.asyncio
    async def test_not_ready_returns_false(self) -> None:
        config = _make_config()
        mock_ib = MagicMock()
        mock_ib.client.connectAsync = AsyncMock()
        mock_ib.client.isReady = MagicMock(return_value=False)
        mock_ib.disconnect = MagicMock()
        with patch("ib_insync.IB", return_value=mock_ib):
            result = await _validate_api_connection(config)
        assert result is False
        mock_ib.disconnect.assert_not_called()


# ==================================================================
# _is_weekend guard
# ==================================================================
class TestWeekendGuard:
    """ensure_gateway_ready returns False immediately on weekends."""

    @pytest.mark.asyncio
    async def test_weekend_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("alphaedge.utils.gw_manager._is_weekend", lambda: True)
        config = _make_config()
        result = await ensure_gateway_ready(config)
        assert result is False


# ==================================================================
# ensure_gateway_ready (integration flow)
# ==================================================================
class TestEnsureGatewayReady:
    """Full orchestration — mocked subprocess and network."""

    @pytest.mark.asyncio
    async def test_already_healthy(self) -> None:
        """Port open + API responds → immediate True."""
        config = _make_config()
        with (
            patch(
                "alphaedge.utils.gw_manager._is_api_port_open",
                return_value=True,
            ),
            patch(
                "alphaedge.utils.gw_manager._validate_api_connection",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            result = await ensure_gateway_ready(config)
        assert result is True

    @pytest.mark.asyncio
    async def test_port_closed_then_becomes_ready(self) -> None:
        """Process not running → polls → port opens after 2 polls."""
        config = _make_config()

        port_calls: list[bool] = [False, False, True]
        port_idx = {"i": 0}

        def _port_side_effect(_host: str, _port: int) -> bool:
            idx = port_idx["i"]
            port_idx["i"] += 1
            if idx < len(port_calls):
                return port_calls[idx]
            return True

        with (
            patch(
                "alphaedge.utils.gw_manager._is_api_port_open",
                side_effect=_port_side_effect,
            ),
            patch(
                "alphaedge.utils.gw_manager._validate_api_connection",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "alphaedge.utils.gw_manager._is_gateway_process_running",
                return_value=False,
            ),
            patch(
                "alphaedge.utils.gw_manager.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            result = await ensure_gateway_ready(config)
        assert result is True

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self) -> None:
        """Port never opens → False after max retries."""
        config = _make_config()
        with (
            patch(
                "alphaedge.utils.gw_manager._is_api_port_open",
                return_value=False,
            ),
            patch(
                "alphaedge.utils.gw_manager._is_gateway_process_running",
                return_value=False,
            ),
            patch(
                "alphaedge.utils.gw_manager.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            result = await ensure_gateway_ready(config)
        assert result is False

    @pytest.mark.asyncio
    async def test_port_open_api_fails_then_recovers(self) -> None:
        """Port open but API fails, then succeeds on retry."""
        config = _make_config()

        validate_calls = [False, False, True]
        validate_idx = {"i": 0}

        async def _validate_effect(_cfg: IBConfig) -> bool:
            idx = validate_idx["i"]
            validate_idx["i"] += 1
            if idx < len(validate_calls):
                return validate_calls[idx]
            return True

        with (
            patch(
                "alphaedge.utils.gw_manager._is_api_port_open",
                return_value=True,
            ),
            patch(
                "alphaedge.utils.gw_manager._validate_api_connection",
                side_effect=_validate_effect,
            ),
            patch(
                "alphaedge.utils.gw_manager._is_gateway_process_running",
                return_value=True,
            ),
            patch(
                "alphaedge.utils.gw_manager.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            result = await ensure_gateway_ready(config)
        assert result is True

    @pytest.mark.asyncio
    async def test_process_running_no_port_then_recovers(self) -> None:
        """Process alive, port closed, then opens on 3rd poll."""
        config = _make_config()

        port_calls = [False, False, False, True]
        port_idx = {"i": 0}

        def _port_effect(_host: str, _port: int) -> bool:
            idx = port_idx["i"]
            port_idx["i"] += 1
            if idx < len(port_calls):
                return port_calls[idx]
            return True

        with (
            patch(
                "alphaedge.utils.gw_manager._is_api_port_open",
                side_effect=_port_effect,
            ),
            patch(
                "alphaedge.utils.gw_manager._validate_api_connection",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "alphaedge.utils.gw_manager._is_gateway_process_running",
                return_value=True,
            ),
            patch(
                "alphaedge.utils.gw_manager.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            result = await ensure_gateway_ready(config)
        assert result is True


# ==================================================================
# _start_gateway_process
# ==================================================================
class TestStartGatewayProcess:
    """Auto-launch of ibgateway.exe."""

    @patch("alphaedge.utils.gw_manager._is_gateway_process_running", return_value=False)
    @patch("alphaedge.utils.gw_manager.subprocess.Popen")
    def test_launch_success(
        self, mock_popen: MagicMock, _mock_running: MagicMock, tmp_path: pathlib.Path
    ) -> None:
        """Exe exists → Popen called → True."""
        exe = tmp_path / "ibgateway.exe"
        exe.write_text("fake")
        with patch(
            "alphaedge.utils.gw_manager._GW_LAUNCH_MUTEX_PATH",
            tmp_path / ".launch.lock",
        ):
            assert _start_gateway_process(str(tmp_path)) is True
        mock_popen.assert_called_once()

    @patch("alphaedge.utils.gw_manager._is_gateway_process_running", return_value=False)
    def test_exe_not_found(
        self, _mock_running: MagicMock, tmp_path: pathlib.Path
    ) -> None:
        """Exe missing → False, no Popen."""
        assert _start_gateway_process(str(tmp_path)) is False

    def test_resolve_gateway_executable_prefers_ibgateway(
        self, tmp_path: pathlib.Path
    ) -> None:
        exe = tmp_path / "ibgateway.exe"
        exe.write_text("fake")
        renamed = tmp_path / "ibgateway1.exe"
        renamed.write_text("fake")

        result = _resolve_gateway_executable(tmp_path)

        assert result == exe

    def test_resolve_gateway_executable_uses_renamed_copy(
        self, tmp_path: pathlib.Path
    ) -> None:
        renamed = tmp_path / "ibgateway1.exe"
        renamed.write_text("fake")

        result = _resolve_gateway_executable(tmp_path)

        assert result == renamed

    @patch("alphaedge.utils.gw_manager._is_gateway_process_running", return_value=False)
    @patch("alphaedge.utils.gw_manager.subprocess.Popen", side_effect=OSError("denied"))
    def test_oserror(
        self, _mock_popen: MagicMock, _mock_running: MagicMock, tmp_path: pathlib.Path
    ) -> None:
        """Popen raises → False."""
        exe = tmp_path / "ibgateway.exe"
        exe.write_text("fake")
        with patch(
            "alphaedge.utils.gw_manager._GW_LAUNCH_MUTEX_PATH",
            tmp_path / ".launch.lock",
        ):
            assert _start_gateway_process(str(tmp_path)) is False

    @patch("alphaedge.utils.gw_manager._is_gateway_process_running", return_value=True)
    def test_already_running_skips_launch(
        self, _mock_running: MagicMock, tmp_path: pathlib.Path
    ) -> None:
        """Process already running → True without Popen."""
        exe = tmp_path / "ibgateway.exe"
        exe.write_text("fake")
        with patch("alphaedge.utils.gw_manager.subprocess.Popen") as mock_popen:
            assert _start_gateway_process(str(tmp_path)) is True
        mock_popen.assert_not_called()

    @patch("alphaedge.utils.gw_manager._is_gateway_process_running", return_value=False)
    @patch("alphaedge.utils.gw_manager.subprocess.Popen")
    def test_launcher_script_uses_cmd_shell(
        self, mock_popen: MagicMock, _mock_running: MagicMock, tmp_path: pathlib.Path
    ) -> None:
        launcher = tmp_path / "StartIBC.bat"
        launcher.write_text("@echo off")
        with patch(
            "alphaedge.utils.gw_manager._GW_LAUNCH_MUTEX_PATH",
            tmp_path / ".launch.lock",
        ):
            assert _start_gateway_process(str(launcher)) is True
        assert mock_popen.call_args.args[0] == ["cmd", "/c", str(launcher)]


# ==================================================================
# ensure_gateway_ready — auto-launch path
# ==================================================================
class TestEnsureGatewayReadyAutoLaunch:
    """Auto-launch when gateway_path is set and process not running."""

    @pytest.mark.asyncio
    async def test_launches_and_becomes_ready(self, tmp_path: pathlib.Path) -> None:
        """No process → launch → poll → API ready → True."""
        exe = tmp_path / "ibgateway.exe"
        exe.write_text("fake")
        config = IBConfig(
            host="127.0.0.1",
            port=4002,
            client_id=1,
            account_id="DU123456",
            is_paper=True,
            gateway_path=str(tmp_path),
        )

        port_calls = [False, False, True]
        port_idx = {"i": 0}

        def _port_effect(_host: str, _port: int) -> bool:
            idx = port_idx["i"]
            port_idx["i"] += 1
            if idx < len(port_calls):
                return port_calls[idx]
            return True

        with (
            patch(
                "alphaedge.utils.gw_manager._is_api_port_open",
                side_effect=_port_effect,
            ),
            patch(
                "alphaedge.utils.gw_manager._validate_api_connection",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "alphaedge.utils.gw_manager._is_gateway_process_running",
                return_value=False,
            ),
            patch("alphaedge.utils.gw_manager.subprocess.Popen"),
            patch(
                "alphaedge.utils.gw_manager.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "alphaedge.utils.gw_manager._GW_LAUNCH_MUTEX_PATH",
                tmp_path / ".launch.lock",
            ),
        ):
            result = await ensure_gateway_ready(config)
        assert result is True

    @pytest.mark.asyncio
    async def test_launch_fails_returns_false(self) -> None:
        """No process, exe missing → launch fails → False immediately."""
        config = IBConfig(
            host="127.0.0.1",
            port=4002,
            client_id=1,
            account_id="DU123456",
            is_paper=True,
            gateway_path="/nonexistent/path",
        )

        with (
            patch(
                "alphaedge.utils.gw_manager._is_api_port_open",
                return_value=False,
            ),
            patch(
                "alphaedge.utils.gw_manager._is_gateway_process_running",
                return_value=False,
            ),
        ):
            result = await ensure_gateway_ready(config)
        assert result is False

    @pytest.mark.asyncio
    async def test_no_gateway_path_falls_through_to_poll(self) -> None:
        """No process, no gateway_path → poll (no launch) → exhausted → False."""
        config = _make_config()

        with (
            patch(
                "alphaedge.utils.gw_manager._is_api_port_open",
                return_value=False,
            ),
            patch(
                "alphaedge.utils.gw_manager._is_gateway_process_running",
                return_value=False,
            ),
            patch(
                "alphaedge.utils.gw_manager.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            result = await ensure_gateway_ready(config)
        assert result is False


# ==================================================================
# ensure_gateway_ready — mode handling
# ==================================================================
class TestEnsureGatewayReadyModes:
    """Verify ensure_gateway_ready behavior for supported auth modes."""

    @pytest.mark.asyncio
    async def test_stored_mode_never_calls_login_fill(self) -> None:
        config = IBConfig(
            host="127.0.0.1",
            port=4002,
            client_id=1,
            account_id="DU123456",
            is_paper=True,
            login_mode="stored",
            username="myuser",
            password="mypass",
        )

        with (
            patch(
                "alphaedge.utils.gw_manager._is_api_port_open",
                return_value=False,
            ),
            patch(
                "alphaedge.utils.gw_manager._is_gateway_process_running",
                return_value=True,
            ),
            patch(
                "alphaedge.utils.gw_manager.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            result = await ensure_gateway_ready(config)

        assert result is False

    @pytest.mark.asyncio
    async def test_ibc_mode_launches_external_launcher(
        self, tmp_path: pathlib.Path
    ) -> None:
        launcher = tmp_path / "StartIBC.bat"
        launcher.write_text("@echo off")
        config = IBConfig(
            host="127.0.0.1",
            port=4002,
            client_id=1,
            account_id="DU123456",
            is_paper=True,
            login_mode="ibc",
            launcher_path=str(launcher),
        )

        port_calls = [False, False, True]
        port_idx = {"i": 0}

        def _port_effect(_host: str, _port: int) -> bool:
            idx = port_idx["i"]
            port_idx["i"] += 1
            if idx < len(port_calls):
                return port_calls[idx]
            return True

        with (
            patch(
                "alphaedge.utils.gw_manager._is_api_port_open",
                side_effect=_port_effect,
            ),
            patch(
                "alphaedge.utils.gw_manager._validate_api_connection",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "alphaedge.utils.gw_manager._is_gateway_process_running",
                return_value=False,
            ),
            patch("alphaedge.utils.gw_manager.subprocess.Popen") as mock_popen,
            patch(
                "alphaedge.utils.gw_manager.asyncio.sleep",
                new_callable=AsyncMock,
            ),
            patch(
                "alphaedge.utils.gw_manager._GW_LAUNCH_MUTEX_PATH",
                tmp_path / ".launch.lock",
            ),
        ):
            result = await ensure_gateway_ready(config)

        assert result is True
        assert mock_popen.call_args.args[0] == ["cmd", "/c", str(launcher)]
