# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_gw_manager_health.py
# DESCRIPTION  : Gateway health checker — detect, validate, retry, auto-login
# PYTHON       : 3.11.9
# ============================================================
"""Tests for gw_manager: process detection, port probe, API, launch, login."""

from __future__ import annotations

import pathlib
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alphaedge.config.loader import IBConfig
from alphaedge.utils.gw_manager import (
    _do_login_fill,
    _escape_sendkeys,
    _fill_gateway_login_if_needed,
    _fill_gateway_login_sync,
    _find_gateway_hwnd,
    _is_api_port_open,
    _is_gateway_process_running,
    _start_gateway_process,
    _try_enable_java_access_bridge,
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


# ==================================================================
# _is_gateway_process_running
# ==================================================================
class TestIsGatewayProcessRunning:
    """Process detection via tasklist.exe."""

    @patch("alphaedge.utils.gw_manager.subprocess.run")
    def test_process_found(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="ibgateway.exe  12345 Console  1  456,789 K"
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
        mock_ib.connectAsync = AsyncMock()
        mock_ib.disconnect = MagicMock()
        mock_ib.isConnected = MagicMock(return_value=False)
        with patch("ib_insync.IB", return_value=mock_ib):
            result = await _validate_api_connection(config)
        assert result is True
        mock_ib.disconnect.assert_called()

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        config = _make_config()
        mock_ib = MagicMock()
        mock_ib.connectAsync = AsyncMock(side_effect=TimeoutError())
        mock_ib.isConnected = MagicMock(return_value=False)
        with patch("ib_insync.IB", return_value=mock_ib):
            result = await _validate_api_connection(config)
        assert result is False

    @pytest.mark.asyncio
    async def test_connection_error(self) -> None:
        config = _make_config()
        mock_ib = MagicMock()
        mock_ib.connectAsync = AsyncMock(side_effect=ConnectionError())
        mock_ib.isConnected = MagicMock(return_value=False)
        with patch("ib_insync.IB", return_value=mock_ib):
            result = await _validate_api_connection(config)
        assert result is False


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

    @patch("alphaedge.utils.gw_manager.subprocess.Popen")
    def test_launch_success(
        self, mock_popen: MagicMock, tmp_path: pathlib.Path
    ) -> None:
        """Exe exists → Popen called → True."""
        exe = tmp_path / "ibgateway.exe"
        exe.write_text("fake")
        assert _start_gateway_process(str(tmp_path)) is True
        mock_popen.assert_called_once()

    def test_exe_not_found(self, tmp_path: pathlib.Path) -> None:
        """Exe missing → False, no Popen."""
        assert _start_gateway_process(str(tmp_path)) is False

    @patch("alphaedge.utils.gw_manager.subprocess.Popen", side_effect=OSError("denied"))
    def test_oserror(self, _mock_popen: MagicMock, tmp_path: pathlib.Path) -> None:
        """Popen raises → False."""
        exe = tmp_path / "ibgateway.exe"
        exe.write_text("fake")
        assert _start_gateway_process(str(tmp_path)) is False


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
# _try_enable_java_access_bridge
# ==================================================================
class TestTryEnableJavaAccessBridge:
    """Best-effort JAB enablement."""

    def test_enables_if_jabswitch_found(self, tmp_path: pathlib.Path) -> None:
        jre_bin = tmp_path / "jre" / "bin"
        jre_bin.mkdir(parents=True)
        jabswitch = jre_bin / "jabswitch.exe"
        jabswitch.write_text("fake")
        with patch("alphaedge.utils.gw_manager.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _try_enable_java_access_bridge(tmp_path)
        mock_run.assert_called_once()
        assert "-enable" in mock_run.call_args[0][0]

    def test_no_jabswitch_does_not_raise(self, tmp_path: pathlib.Path) -> None:
        """Missing jabswitch → silently continues, no exception."""
        _try_enable_java_access_bridge(tmp_path)  # must not raise

    def test_oserror_does_not_raise(self, tmp_path: pathlib.Path) -> None:
        jabswitch = tmp_path / "jabswitch.exe"
        jabswitch.write_text("fake")
        with patch(
            "alphaedge.utils.gw_manager.subprocess.run", side_effect=OSError("denied")
        ):
            _try_enable_java_access_bridge(tmp_path)  # must not raise


# ==================================================================
# _escape_sendkeys
# ==================================================================
class TestEscapeSendkeys:
    """Verify special character escaping for pywinauto.keyboard."""

    def test_plain_text_unchanged(self) -> None:
        assert _escape_sendkeys("hello123") == "hello123"

    def test_special_chars_escaped(self) -> None:
        result = _escape_sendkeys("p@ss+w0rd!")
        assert "{+}" in result
        assert result == "p@ss{+}w0rd!"

    def test_braces_escaped(self) -> None:
        result = _escape_sendkeys("a{b}")
        assert result == "a{{}b{}}"

    def test_all_specials(self) -> None:
        for ch in "+^%~(){}":
            assert f"{{{ch}}}" in _escape_sendkeys(ch)


# ==================================================================
# _find_gateway_hwnd
# ==================================================================
class TestFindGatewayHwnd:
    """Window lookup via win32gui.EnumWindows."""

    def test_finds_window_by_title(self) -> None:
        mock_win32gui = MagicMock()

        # Simulate EnumWindows calling the callback with one visible window
        def _fake_enum(callback, _):
            callback(0x1234, None)  # visible, title matches
            return True

        mock_win32gui.EnumWindows.side_effect = _fake_enum
        mock_win32gui.IsWindowVisible.return_value = True
        mock_win32gui.GetWindowText.return_value = "Portail IBKR"
        result = _find_gateway_hwnd(mock_win32gui)
        assert result == 0x1234

    def test_returns_zero_when_not_found(self) -> None:
        mock_win32gui = MagicMock()

        def _fake_enum(callback, _):
            callback(0x1234, None)
            return True

        mock_win32gui.EnumWindows.side_effect = _fake_enum
        mock_win32gui.IsWindowVisible.return_value = True
        mock_win32gui.GetWindowText.return_value = "Notepad"
        result = _find_gateway_hwnd(mock_win32gui)
        assert result == 0

    def test_returns_zero_on_exception(self) -> None:
        mock_win32gui = MagicMock()
        mock_win32gui.EnumWindows.side_effect = OSError("access denied")
        result = _find_gateway_hwnd(mock_win32gui)
        assert result == 0


# ==================================================================
# _fill_gateway_login_sync
# ==================================================================
class TestFillGatewayLoginSync:
    """Login form automation via win32gui + pywinauto mouse/keyboard."""

    def test_pywinauto_not_installed_returns_false(self) -> None:
        """If pywinauto is not importable, returns False gracefully."""
        with patch.dict(
            "sys.modules",
            {
                "pywinauto": None,
                "pywinauto.keyboard": None,
                "pywinauto.mouse": None,
            },
        ):
            result = _fill_gateway_login_sync("user", "pass")
        assert result is False

    def test_window_not_found_returns_false(self) -> None:
        """If the login window is not visible, returns False (will retry)."""
        with patch.dict(
            "sys.modules",
            {
                "win32gui": MagicMock(),
                "pywinauto": MagicMock(),
                "pywinauto.keyboard": MagicMock(),
                "pywinauto.mouse": MagicMock(),
            },
        ):
            with patch("alphaedge.utils.gw_manager._do_login_fill", return_value=False):
                result = _fill_gateway_login_sync("user", "pass")
        assert result is False

    def test_fills_credentials_and_clicks_login(self) -> None:
        """Delegates to _do_login_fill once imports succeed."""
        with patch.dict(
            "sys.modules",
            {
                "win32gui": MagicMock(),
                "pywinauto": MagicMock(),
                "pywinauto.keyboard": MagicMock(),
                "pywinauto.mouse": MagicMock(),
            },
        ):
            with patch(
                "alphaedge.utils.gw_manager._do_login_fill",
                return_value=True,
            ) as mock_fill:
                result = _fill_gateway_login_sync("myuser", "mypass")

        assert result is True
        mock_fill.assert_called_once()
        assert mock_fill.call_args.args[0] == "myuser"
        assert mock_fill.call_args.args[1] == "mypass"


# ==================================================================
# _fill_gateway_login_if_needed
# ==================================================================
class TestFillGatewayLoginIfNeeded:
    """Async wrapper for login fill."""

    @pytest.mark.asyncio
    async def test_delegates_to_sync(self) -> None:
        """Async wrapper returns the result from _fill_gateway_login_sync."""
        with patch(
            "alphaedge.utils.gw_manager._fill_gateway_login_sync", return_value=True
        ) as mock_sync:
            result = await _fill_gateway_login_if_needed("u", "p")
        assert result is True
        mock_sync.assert_called_once_with("u", "p")


# ==================================================================
# _do_login_fill
# ==================================================================
class TestDoLoginFill:
    """GUI interaction via win32gui + pywinauto (modules passed as mocks)."""

    def _make_mocks(
        self, rect: tuple[int, int, int, int] = (100, 100, 650, 800)
    ) -> tuple[MagicMock, MagicMock, MagicMock]:
        mock_w32gui = MagicMock()
        mock_w32gui.GetWindowRect.return_value = rect
        mock_kb = MagicMock()
        mock_mouse = MagicMock()
        return mock_w32gui, mock_kb, mock_mouse

    def test_window_not_found_returns_false(self) -> None:
        mock_w32gui, mock_kb, mock_mouse = self._make_mocks()
        with patch("alphaedge.utils.gw_manager._find_gateway_hwnd", return_value=0):
            result = _do_login_fill("user", "pass", mock_w32gui, mock_kb, mock_mouse)
        assert result is False
        mock_mouse.click.assert_not_called()

    def test_fills_credentials_and_clicks_login(self) -> None:
        mock_w32gui, mock_kb, mock_mouse = self._make_mocks()
        with (
            patch("alphaedge.utils.gw_manager._find_gateway_hwnd", return_value=0x1234),
            patch("time.sleep"),  # avoid real waits (1.5s focus + 2s post-submit)
        ):
            result = _do_login_fill(
                "myuser", "mypass", mock_w32gui, mock_kb, mock_mouse
            )
        assert result is True
        # 7 clicks: triple-click username (3) + triple-click password (3) + login (1)
        assert mock_mouse.click.call_count == 7
        # 3 keyboard calls: username text + {TAB} + password text (no Ctrl+A)
        assert mock_kb.send_keys.call_count == 3

    def test_focus_error_returns_false(self) -> None:
        mock_w32gui, mock_kb, mock_mouse = self._make_mocks()
        mock_w32gui.ShowWindow.side_effect = OSError("access denied")
        with patch(
            "alphaedge.utils.gw_manager._find_gateway_hwnd", return_value=0x1234
        ):
            result = _do_login_fill("u", "p", mock_w32gui, mock_kb, mock_mouse)
        assert result is False
        mock_mouse.click.assert_not_called()


# ==================================================================
# ensure_gateway_ready — login fill integration
# ==================================================================
class TestEnsureGatewayReadyLogin:
    """Verify ensure_gateway_ready calls login fill when port is closed."""

    @pytest.mark.asyncio
    async def test_login_fill_called_when_port_closed_with_creds(self) -> None:
        """When port is closed and credentials are set, login fill is invoked."""
        config = IBConfig(
            host="127.0.0.1",
            port=4002,
            client_id=1,
            account_id="DU123456",
            is_paper=True,
            username="myuser",
            password="mypass",
        )
        fill_calls: list[tuple[str, str]] = []

        async def _mock_fill(username: str, password: str) -> bool:
            fill_calls.append((username, password))
            return True

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
                "alphaedge.utils.gw_manager._fill_gateway_login_if_needed",
                side_effect=_mock_fill,
            ),
            patch(
                "alphaedge.utils.gw_manager.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            await ensure_gateway_ready(config)

        assert len(fill_calls) > 0
        assert fill_calls[0] == ("myuser", "mypass")

    @pytest.mark.asyncio
    async def test_login_fill_not_called_without_creds(self) -> None:
        """Without credentials, login fill is never invoked."""
        config = _make_config()  # username="" password=""
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
                "alphaedge.utils.gw_manager._fill_gateway_login_if_needed",
                new_callable=AsyncMock,
            ) as mock_fill,
            patch(
                "alphaedge.utils.gw_manager.asyncio.sleep",
                new_callable=AsyncMock,
            ),
        ):
            await ensure_gateway_ready(config)

        mock_fill.assert_not_called()
