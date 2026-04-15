# ============================================================
# PROJECT      : ALPHAEDGE — Swing Trading Bot
# FILE         : alphaedge/utils/gw_manager.py
# DESCRIPTION  : IB Gateway health checker — detect, launch, login, validate
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-04-11
# ============================================================
"""IB Gateway health checker with auto-launch and auto-login.

Ensures IB Gateway is running, authenticated, and its API is reachable
before the bot starts trading.  Handles the daily 05:30 restart cycle
by polling with backoff, filling the login form when credentials are
configured.

Capabilities:
- **Auto-detect**: checks process presence and API port.
- **Auto-launch**: starts ``ibgateway.exe`` if not running and
  ``config.gateway_path`` is set.
- **Auto-login**: fills the IB Gateway login form (username + password)
  and clicks "Connexion" by simulating physical mouse clicks and
  keystrokes via ``pywinauto.mouse`` / ``pywinauto.keyboard``.
  Works with Java Swing without requiring the Java Access Bridge.
- **Daily restart (05:30)**: the poll loop retries the login fill
  whenever the port is closed and credentials are configured.

Usage::

    from alphaedge.utils.gw_manager import ensure_gateway_ready

    if not await ensure_gateway_ready(config.ib):
        logger.critical("Gateway unavailable — aborting session")
        return
"""

from __future__ import annotations

import asyncio
import pathlib
import socket
import subprocess
from collections.abc import Callable
from typing import Protocol, cast

from alphaedge.config.constants import (
    IB_GATEWAY_HEALTH_RETRIES,
    IB_GATEWAY_HEALTH_RETRY_DELAY_SECONDS,
    IB_GATEWAY_STARTUP_TIMEOUT_SECONDS,
    IB_PROBE_CLIENT_ID_OFFSET,
    IB_TIMEOUT_SECONDS,
)
from alphaedge.config.loader import IBConfig
from alphaedge.utils.logger import get_logger

logger = get_logger()

# Regex patterns for locating the IB Gateway login window.
# IB Gateway shows "Portail IBKR" (FR), "IBKR Portal" (EN), or "IB Gateway".
_GW_WINDOW_TITLE_RE = r"Portail IBKR|IBKR Portal|IB Gateway"
# Login button label varies by language.
_GW_LOGIN_BTN_RE = r"Connexion|Login|Log In|Se connecter"

# Win32 constant: SW_RESTORE = 9 (show and restore window)
# This value has been stable in the Windows API since Windows 3.1.
_SW_RESTORE: int = 9

# Guard against re-submitting the login form while IB Gateway is processing
# authentication.  Auth takes 30–60 s; the poll loop runs every 10 s.
# Without this guard the form would be refilled on each cycle, confusing
# the authentication server and causing systematic login failures.
_last_login_submitted_at: float = 0.0
_LOGIN_SUBMIT_COOLDOWN_SECONDS: float = 90.0


# ------------------------------------------------------------------
# Win32 / pywinauto Protocol shims (for type checking without stubs)
# ------------------------------------------------------------------
class _Win32Gui(Protocol):
    """Subset of win32gui used by gateway detection and login fill."""

    def EnumWindows(  # noqa: N802
        self,
        func: Callable[..., object],
        extra: object,
        /,
    ) -> None: ...

    def IsWindowVisible(self, hwnd: int, /) -> int: ...  # noqa: N802

    def GetWindowText(self, hwnd: int, /) -> str: ...  # noqa: N802

    def ShowWindow(self, hwnd: int, ncmd: int, /) -> int: ...  # noqa: N802

    def SetForegroundWindow(self, hwnd: int, /) -> None: ...  # noqa: N802

    def GetWindowRect(self, hwnd: int, /) -> tuple[int, int, int, int]: ...  # noqa: N802


class _PwKeyboard(Protocol):
    """Subset of pywinauto.keyboard used for key injection."""

    def send_keys(
        self,
        keys: str,
        pause: float = ...,
        with_spaces: bool = ...,
    ) -> None: ...


class _PwMouse(Protocol):
    """Subset of pywinauto.mouse used for click injection."""

    def click(
        self,
        button: str = ...,
        coords: tuple[int, int] = ...,
    ) -> None: ...


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------
async def ensure_gateway_ready(config: IBConfig) -> bool:
    """Ensure IB Gateway is running and the API is reachable.

    Strategy:
    1. If port open + API responds → return True immediately.
    2. If process not running + ``gateway_path`` configured → launch it.
    3. Poll until the API becomes reachable.  On each cycle where the port
       is still closed and ``username``/``password`` are configured, try to
       fill the login form (handles fresh launch + daily 05:30 restart).
    4. After all retries exhausted → return False.

    Parameters
    ----------
    config : IBConfig
        IB connection configuration (host, port, gateway_path,
        username, password).

    Returns
    -------
    bool
        True if gateway is healthy and API is reachable.
    """
    # Fast path: already healthy
    if _is_api_port_open(config.host, config.port):
        if await _validate_api_connection(config):
            logger.info(
                f"ALPHAEDGE GW: IB Gateway healthy ({config.host}:{config.port})"
            )
            return True
        logger.warning(
            "ALPHAEDGE GW: Port open but API validation failed "
            "— gateway may be restarting"
        )

    has_credentials = bool(config.username and config.password)

    # Auto-launch or wait for external startup
    launched = False
    if not _is_gateway_process_running():
        if config.gateway_path:
            launched = _start_gateway_process(config.gateway_path)
            if not launched:
                return False
        else:
            logger.warning(
                "ALPHAEDGE GW: Gateway process NOT detected "
                "— waiting for external startup "
                "(Task Scheduler / manual)"
            )
    else:
        logger.info(
            "ALPHAEDGE GW: Gateway process detected "
            "— waiting for API to become available"
        )

    if has_credentials:
        logger.info("ALPHAEDGE GW: Credentials configured — will auto-fill login form")
    else:
        logger.info(
            "ALPHAEDGE GW: No credentials configured "
            "(set ALPHAEDGE_IB_USERNAME / ALPHAEDGE_IB_PASSWORD for auto-login)"
        )

    # More retries after a fresh launch (gateway needs time to start Java + auth)
    max_retries = (
        IB_GATEWAY_STARTUP_TIMEOUT_SECONDS // IB_GATEWAY_HEALTH_RETRY_DELAY_SECONDS
        if launched
        else IB_GATEWAY_HEALTH_RETRIES
    )

    # Poll until API becomes reachable
    for attempt in range(1, max_retries + 1):
        logger.info(f"ALPHAEDGE GW: Waiting for API (attempt {attempt}/{max_retries})")
        await asyncio.sleep(IB_GATEWAY_HEALTH_RETRY_DELAY_SECONDS)

        if not _is_api_port_open(config.host, config.port):
            # Login form may be visible — try to fill it
            if has_credentials:
                await _fill_gateway_login_if_needed(config.username, config.password)
            continue

        if await _validate_api_connection(config):
            logger.info(
                f"ALPHAEDGE GW: IB Gateway ready after {attempt} "
                f"poll{'s' if attempt > 1 else ''}"
            )
            return True

    logger.critical(
        f"ALPHAEDGE GW: IB Gateway NOT reachable after "
        f"{max_retries} retries "
        f"— manual intervention required"
    )
    return False


# ------------------------------------------------------------------
# Gateway launcher (native — no IBC)
# ------------------------------------------------------------------
# Windows-only process creation flags — defined as literals so pyright does not
# flag them on Linux (subprocess.CREATE_NEW_PROCESS_GROUP is Windows-only).
_DETACHED_PROCESS: int = 0x00000008  # DETACHED_PROCESS
_CREATE_NEW_PROCESS_GROUP: int = 0x00000200  # CREATE_NEW_PROCESS_GROUP


def _start_gateway_process(gateway_path: str) -> bool:
    """Launch ``ibgateway.exe`` from *gateway_path*.

    IB Gateway remembers credentials when **Store settings on server**
    is enabled in the gateway configuration.  Subsequent launches
    auto-authenticate without manual intervention.

    Parameters
    ----------
    gateway_path : str
        Directory containing ``ibgateway.exe``
        (e.g. ``C:\\Jts\\ibgateway\\1044``).

    Returns
    -------
    bool
        True if the process was launched successfully.
    """
    exe = pathlib.Path(gateway_path) / "ibgateway.exe"
    if not exe.exists():
        logger.error(f"ALPHAEDGE GW: Gateway executable not found: {exe}")
        return False

    try:
        subprocess.Popen(
            [str(exe)],
            cwd=str(exe.parent),
            creationflags=_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        logger.info(f"ALPHAEDGE GW: Launched IB Gateway from {exe}")
        return True
    except OSError as exc:
        logger.error(f"ALPHAEDGE GW: Failed to launch IB Gateway — {exc}")
        return False


def _try_enable_java_access_bridge(gateway_dir: pathlib.Path) -> None:
    """Enable the Java Accessibility Bridge once (best-effort).

    ``jabswitch -enable`` makes Java Swing controls visible to Windows
    UIA, which is required for ``pywinauto`` to interact with the
    IB Gateway login form.

    IB Gateway bundles its own JRE.  ``jabswitch.exe`` is typically found
    in ``<gateway_dir>/jre/bin/`` or directly in ``<gateway_dir>``.
    """
    candidates = [
        gateway_dir / "jre" / "bin" / "jabswitch.exe",
        gateway_dir / "bin" / "jabswitch.exe",
        gateway_dir / "jabswitch.exe",
    ]
    for jabswitch in candidates:
        if jabswitch.exists():
            try:
                subprocess.run(
                    [str(jabswitch), "-enable"],
                    timeout=10,
                    check=False,
                    capture_output=True,
                )
                logger.info(f"ALPHAEDGE GW: Java Access Bridge enabled via {jabswitch}")
                return
            except OSError:
                pass
    logger.debug(
        "ALPHAEDGE GW: jabswitch.exe not found — "
        "run 'jabswitch -enable' manually if auto-login fails"
    )


# ------------------------------------------------------------------
# Login form automation (win32gui + SendInput — no JAB, no UIA)
# ------------------------------------------------------------------
async def _fill_gateway_login_if_needed(username: str, password: str) -> bool:
    """Async wrapper — fills the IB Gateway login form if the window is visible.

    Runs the blocking call in a thread pool so it does not block the
    event loop.
    """
    return await asyncio.to_thread(_fill_gateway_login_sync, username, password)


def _fill_gateway_login_sync(username: str, password: str) -> bool:
    """Fill the IB Gateway login window (blocking).

    Finds the window by title via ``win32gui``, brings it to the
    foreground, then simulates physical mouse clicks on the username and
    password fields (located by their proportional position inside the
    window) and types the credentials using ``pywinauto.keyboard``
    SendInput.  Clicks the login button to submit.

    This approach does **not** require the Java Access Bridge or UIA —
    it works at the Win32 ``SendInput`` level and is compatible with
    Java Swing, Electron, and any other GUI framework.

    Returns
    -------
    bool
        True if credentials were submitted.  False if the window was not
        visible yet — will be retried on the next poll cycle.
    """
    import time

    global _last_login_submitted_at
    elapsed = time.monotonic() - _last_login_submitted_at
    if elapsed < _LOGIN_SUBMIT_COOLDOWN_SECONDS:
        logger.debug(
            f"ALPHAEDGE GW: Login cooldown active — submitted {elapsed:.0f}s ago "
            f"(retry after {_LOGIN_SUBMIT_COOLDOWN_SECONDS:.0f}s cooldown)"
        )
        return False

    try:
        import pywinauto.keyboard as pw_keyboard
        import pywinauto.mouse as pw_mouse
        import win32gui
    except ImportError:
        logger.warning(
            "ALPHAEDGE GW: pywinauto/pywin32 not installed — cannot auto-fill login. "
            "Install with: pip install pywinauto"
        )
        return False

    submitted = _do_login_fill(
        username,
        password,
        cast(_Win32Gui, win32gui),
        cast(_PwKeyboard, pw_keyboard),
        cast(_PwMouse, pw_mouse),
    )
    if submitted:
        _last_login_submitted_at = time.monotonic()
    return submitted


def _do_login_fill(
    username: str,
    password: str,
    win32gui: _Win32Gui,
    pw_keyboard: _PwKeyboard,
    pw_mouse: _PwMouse,
) -> bool:
    """Execute the actual GUI fill once all modules are available.

    Separated from :func:`_fill_gateway_login_sync` so that unit tests
    can pass mock modules directly without fighting Python's import
    machinery.
    """
    import time

    hwnd = _find_gateway_hwnd(cast(_Win32Gui, win32gui))
    if not hwnd:
        return False

    # Bring window to foreground
    try:
        win32gui.ShowWindow(hwnd, _SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception as exc:
        logger.debug(f"ALPHAEDGE GW: Could not focus window — {exc}")
        return False

    time.sleep(1.5)  # wait for Java Swing to finish rendering all controls

    # Re-check: if the window closed while waiting, auth already completed.
    if not win32gui.IsWindowVisible(hwnd):
        logger.info(
            "ALPHAEDGE GW: Login window closed while focusing — already authenticated"
        )
        return True

    rect = win32gui.GetWindowRect(hwnd)
    cx = (rect[0] + rect[2]) // 2
    win_top = rect[1]
    win_h = rect[3] - rect[1]

    # Field positions — relative to window height (IB Gateway fixed layout).
    # Calibrated from the IB Gateway 10.44 login window:
    #   username field ~43%, password field ~53%, connexion button ~67%.
    user_y = win_top + int(win_h * 0.43)
    pass_y = win_top + int(win_h * 0.53)
    btn_y = win_top + int(win_h * 0.67)

    try:
        # Username field — rapid triple-click selects all existing text in the
        # JTextField without relying on Ctrl+A (which fails when Java Swing focus
        # is not fully established after SetForegroundWindow).
        pw_mouse.click(coords=(cx, user_y))
        time.sleep(0.05)
        pw_mouse.click(coords=(cx, user_y))
        time.sleep(0.05)
        pw_mouse.click(coords=(cx, user_y))
        time.sleep(0.4)
        pw_keyboard.send_keys(_escape_sendkeys(username), with_spaces=True, pause=0.05)

        # Password field — Tab out of username then triple-click for selection.
        pw_keyboard.send_keys("{TAB}", pause=0.1)
        time.sleep(0.3)
        pw_mouse.click(coords=(cx, pass_y))
        time.sleep(0.05)
        pw_mouse.click(coords=(cx, pass_y))
        time.sleep(0.05)
        pw_mouse.click(coords=(cx, pass_y))
        time.sleep(0.4)
        pw_keyboard.send_keys(_escape_sendkeys(password), with_spaces=True, pause=0.05)

        time.sleep(0.3)

        # Connexion button
        pw_mouse.click(coords=(cx, btn_y))

        logger.info(
            "ALPHAEDGE GW: Login credentials submitted — awaiting authentication"
        )
        # Post-submit check: if the login window is still visible after 2 s the
        # button click may have missed.  The cooldown guard prevents re-submit for
        # 90 s — the next cycle will retry once the cooldown expires.
        time.sleep(2.0)
        if _find_gateway_hwnd(cast(_Win32Gui, win32gui)):
            logger.warning(
                "ALPHAEDGE GW: Login window still visible 2 s after submit — "
                "button click may have missed; retrying after cooldown"
            )
        else:
            logger.info(
                "ALPHAEDGE GW: Login window dismissed — authentication accepted"
            )
        return True

    except Exception as exc:
        logger.debug(f"ALPHAEDGE GW: Login fill attempt failed — {exc}")
        return False


def _find_gateway_hwnd(win32gui: _Win32Gui) -> int:
    """Return the HWND of the IB Gateway login window, or 0 if not found."""
    import re

    pattern = re.compile(_GW_WINDOW_TITLE_RE, re.IGNORECASE)
    found = [0]

    def _cb(hwnd: int, _: object) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            title: str = win32gui.GetWindowText(hwnd)
            if pattern.search(title):
                found[0] = hwnd
                return False  # stop enumeration
        return True

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        pass

    return found[0]


def _escape_sendkeys(text: str) -> str:
    """Escape pywinauto send_keys special characters.

    Characters ``+``, ``^``, ``%``, ``~``, ``(``, ``)``, ``{``, ``}``
    have special meaning in ``pywinauto.keyboard.send_keys`` — wrap each
    in braces to send them literally.
    """
    _special = frozenset("+^%~(){}")
    return "".join(f"{{{c}}}" if c in _special else c for c in text)


# ------------------------------------------------------------------
# Process detection (tasklist.exe — no psutil dependency)
# ------------------------------------------------------------------
def _is_gateway_process_running() -> bool:
    """Check if an IB Gateway process is running (Windows)."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq ibgateway.exe", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # tasklist returns "INFO: No tasks are running..." when not found
        return "ibgateway.exe" in result.stdout.lower()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        logger.warning("ALPHAEDGE GW: Unable to query process list")
        return False


# ------------------------------------------------------------------
# TCP port probe
# ------------------------------------------------------------------
def _is_api_port_open(host: str, port: int) -> bool:
    """Test whether the IB Gateway API port accepts TCP connections."""
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


# ------------------------------------------------------------------
# API validation (lightweight ib_insync connect + disconnect)
# ------------------------------------------------------------------
async def _validate_api_connection(config: IBConfig) -> bool:
    """Perform a lightweight IB API handshake to confirm authentication.

    Connects with a dedicated client ID (client_id + 99) to avoid
    colliding with the main trading connection, then disconnects
    immediately.
    """
    try:
        from ib_insync import IB
    except ImportError:
        logger.error("ALPHAEDGE GW: ib_insync not installed — cannot validate API")
        return False

    ib = IB()
    probe_client_id = config.client_id + IB_PROBE_CLIENT_ID_OFFSET
    try:
        await asyncio.wait_for(
            ib.connectAsync(
                host=config.host,
                port=config.port,
                clientId=probe_client_id,
                readonly=True,
            ),
            timeout=IB_TIMEOUT_SECONDS,
        )
        ib.disconnect()
        return True
    except (TimeoutError, ConnectionError, OSError):
        return False
    except Exception:
        logger.debug("ALPHAEDGE GW: API validation failed", exc_info=True)
        return False
    finally:
        if ib.isConnected():
            ib.disconnect()
