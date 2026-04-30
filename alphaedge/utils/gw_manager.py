# ============================================================
# PROJECT      : ALPHAEDGE — Swing Trading Bot
# FILE         : alphaedge/utils/gw_manager.py
# DESCRIPTION  : IB Gateway health checker — detect, launch, login, validate
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-04-11
# ============================================================
"""IB Gateway health checker with auto-launch and readiness validation.

Ensures IB Gateway is running, authenticated, and its API is reachable
before the bot starts trading. Handles the daily 05:30 restart cycle
by polling with backoff until the API becomes available.

Capabilities:
- **Auto-detect**: checks process presence and API port.
- **Auto-launch**: starts ``ibgateway.exe`` if not running and
    ``config.gateway_path`` is set.
- **External launcher support**: starts an IBC launcher when
    ``login_mode=ibc`` and ``launcher_path`` is configured.
- **Daily restart (05:30)**: the poll loop tolerates delayed gateway
    restarts until authentication completes externally.

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
import time

from alphaedge.config.constants import (
    IB_GATEWAY_HEALTH_RETRIES,
    IB_GATEWAY_HEALTH_RETRY_DELAY_SECONDS,
    IB_GATEWAY_STARTUP_TIMEOUT_SECONDS,
    IB_PROBE_CLIENT_ID_OFFSET,
    IB_TIMEOUT_SECONDS,
)
from alphaedge.config.loader import IBConfig
from alphaedge.utils.logger import get_logger
from alphaedge.utils.timezone import is_weekend_paris

logger = get_logger()

_LOGIN_MODES = frozenset({"stored", "manual", "ibc"})
_GATEWAY_EXECUTABLE_NAMES = ("ibgateway.exe", "ibgateway1.exe")


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------
def _is_weekend() -> bool:
    """Return True on Saturday (5) or Sunday (6) in Europe/Paris time.

    Uses Paris local time so that Friday evening that has already crossed
    midnight into Saturday in Paris is correctly treated as a weekend day,
    preventing IB Gateway from being launched outside trading days.
    """
    return is_weekend_paris()


async def check_gateway_health(config: IBConfig) -> bool:
    """Read-only probe: is IB Gateway reachable and authenticated?

    Unlike :func:`ensure_gateway_ready` this function **never** launches
    a process, fills credentials, or polls.  It is safe to call when
    another project manages the gateway lifecycle (e.g. EDGECORE_V1 has
    already launched, logged in, and connected IB Gateway).

    Returns True if the API port is open **and** a lightweight readonly
    ``ib_insync`` handshake succeeds.
    """
    if not _is_api_port_open(config.host, config.port):
        return False
    return await _validate_api_connection(config)


async def ensure_gateway_ready(config: IBConfig) -> bool:
    """Ensure IB Gateway is running and the API is reachable.

    Returns False immediately on weekends (market closed, no gateway
    needed).  The session lifecycle skips to _wait_for_session_open
    which handles the weekend → Monday transition.

    Strategy:
    1. If port open + API responds → return True immediately.
    2. If process not running + ``gateway_path`` configured → launch it.
     3. Poll until the API becomes reachable.
    4. After all retries exhausted → return False.

    Parameters
    ----------
    config : IBConfig
        IB connection configuration (host, port, gateway_path).

    Returns
    -------
    bool
        True if gateway is healthy and API is reachable.
    """
    # Weekend guard — market closed Sat & Sun, do not launch gateway
    if _is_weekend():
        logger.info("ALPHAEDGE GW: Weekend — market closed, skipping gateway launch")
        return False

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

    login_mode = _normalize_login_mode(config.login_mode)

    # Auto-launch or wait for external startup
    launched = False
    if not _is_gateway_process_running():
        if login_mode == "ibc":
            if not config.launcher_path:
                logger.error(
                    "ALPHAEDGE GW: login_mode=ibc requires launcher_path "
                    "(set ALPHAEDGE_IB_LAUNCHER_PATH)"
                )
                return False
            launched = _start_gateway_process(config.launcher_path)
            if not launched:
                return False
        elif config.gateway_path:
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

    if login_mode == "stored":
        logger.info(
            "ALPHAEDGE GW: login_mode=stored — expecting IB Gateway to reuse "
            "stored credentials"
        )
    elif login_mode == "manual":
        logger.warning(
            "ALPHAEDGE GW: login_mode=manual — operator action may be required"
        )
    else:
        logger.info(
            "ALPHAEDGE GW: login_mode=ibc — external launcher handles authentication"
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


def _normalize_login_mode(login_mode: str) -> str:
    """Return a supported gateway login mode."""
    normalized = login_mode.strip().lower()
    if normalized in _LOGIN_MODES:
        return normalized

    logger.warning(
        f"ALPHAEDGE GW: Unsupported login_mode={login_mode!r} — defaulting to manual"
    )
    return "manual"


# ------------------------------------------------------------------
# Gateway launcher (native — no IBC)
# ------------------------------------------------------------------
# Windows-only process creation flags — defined as literals so pyright does not
# flag them on Linux (subprocess.CREATE_NEW_PROCESS_GROUP is Windows-only).
_DETACHED_PROCESS: int = 0x00000008  # DETACHED_PROCESS
_CREATE_NEW_PROCESS_GROUP: int = 0x00000200  # CREATE_NEW_PROCESS_GROUP

# Shared mutex file that prevents EDGECORE_V1 and AlphaEdge from both launching
# ibgateway.exe at the same moment.  Whichever process creates the file first
# wins; the other defers.  Stale lock (> TTL) is auto-removed.
_GW_LAUNCH_MUTEX_PATH = pathlib.Path(r"C:\Jts\ibgateway\.launch.lock")
_GW_LAUNCH_MUTEX_TTL_SECONDS: float = 30.0


def _start_gateway_process(gateway_path: str) -> bool:
    """Launch IB Gateway directly or via an external launcher.

    IB Gateway remembers credentials when **Store settings on server**
    is enabled in the gateway configuration.  Subsequent launches
    auto-authenticate without manual intervention.

    **Duplicate protection (absolute rule — never open two instances):**

    1. Process-level guard: if ``ibgateway.exe`` is already in the
       process list, return True immediately without launching.
    2. Cross-project file mutex (``C:\\Jts\\ibgateway\\.launch.lock``):
       atomic ``O_CREAT|O_EXCL`` ensures only one process wins.
    3. The lock is **intentionally NOT released** after a successful
       launch.  It expires via TTL (30 s), by which time the process
       is guaranteed to appear in ``tasklist``.  This closes the
       ~50 ms TOCTOU window between ``Popen`` and process visibility.

    Parameters
    ----------
    gateway_path : str
        Either a directory containing ``ibgateway.exe``
        (e.g. ``C:\\Jts\\ibgateway\\1044``) or an external launcher
        path (e.g. ``C:\\IBC\\StartIBC.bat``).

    Returns
    -------
    bool
        True if the process was launched (or is already running).
    """
    # ── Guard 1: process already running ──────────────────────────
    # The caller checks _is_gateway_process_running() before calling us,
    # but a second project may have launched it in the meantime (TOCTOU).
    if _is_gateway_process_running():
        logger.info("ALPHAEDGE GW: ibgateway.exe already running — skipping launch")
        return True

    target = pathlib.Path(gateway_path)
    if target.is_dir():
        exe = _resolve_gateway_executable(target)
        cmd = [str(exe)]
        cwd = str(exe.parent)
        launched_desc = f"IB Gateway from {exe}"
    else:
        exe = target
        if exe.suffix.lower() in {".bat", ".cmd"}:
            cmd = ["cmd", "/c", str(exe)]
        else:
            cmd = [str(exe)]
        cwd = str(exe.parent)
        launched_desc = f"gateway launcher {exe}"

    if not exe.exists():
        logger.error(f"ALPHAEDGE GW: Gateway executable not found: {exe}")
        return False

    # ── Guard 2: cross-project file mutex ─────────────────────────
    # Prevents AlphaEdge and EDGECORE_V1 from both launching
    # ibgateway.exe when they start at the same moment.  Exclusive
    # O_CREAT|O_EXCL open ensures only one process wins the race.
    lock = _GW_LAUNCH_MUTEX_PATH
    lock_acquired = False
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        if lock.exists():
            age = time.time() - lock.stat().st_mtime
            if age < _GW_LAUNCH_MUTEX_TTL_SECONDS:
                logger.info(
                    f"ALPHAEDGE GW: Launch deferred — another process is launching "
                    f"gateway (lock age {age:.1f}s)"
                )
                return False  # let the other project's launch complete
            lock.unlink(missing_ok=True)  # stale lock — remove and proceed
        lock.touch(exist_ok=False)
        lock_acquired = True
    except FileExistsError:
        logger.info(
            "ALPHAEDGE GW: Launch deferred — concurrent launch detected via mutex"
        )
        return False
    except OSError as exc:
        logger.warning(f"ALPHAEDGE GW: Mutex unavailable — {exc}")
        # Proceed without mutex rather than aborting entirely

    try:
        subprocess.Popen(
            cmd,
            cwd=cwd,
            creationflags=_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        logger.info(f"ALPHAEDGE GW: Launched {launched_desc}")
        # Lock intentionally NOT released here.  It auto-expires via TTL
        # (30 s), giving ibgateway.exe time to appear in the process list.
        # This prevents a second project from launching a duplicate in the
        # ~50 ms window between Popen and tasklist visibility.
        return True
    except OSError as exc:
        logger.error(f"ALPHAEDGE GW: Failed to launch IB Gateway — {exc}")
        if lock_acquired:
            lock.unlink(missing_ok=True)  # release lock on failure only
        return False


def _resolve_gateway_executable(gateway_dir: pathlib.Path) -> pathlib.Path:
    """Return the preferred Gateway executable within an install directory."""
    for name in _GATEWAY_EXECUTABLE_NAMES:
        candidate = gateway_dir / name
        if candidate.exists():
            return candidate
    return gateway_dir / _GATEWAY_EXECUTABLE_NAMES[0]


# ------------------------------------------------------------------
# Process detection (tasklist.exe — no psutil dependency)
# ------------------------------------------------------------------
def _is_gateway_process_running() -> bool:
    """Check if an IB Gateway process is running (Windows)."""
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout.lower()
        return any(name in output for name in _GATEWAY_EXECUTABLE_NAMES)
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

    Important: use the low-level client socket handshake instead of
    ``IB.connectAsync()``. The high-level ib_insync connect path triggers
    full startup synchronization (positions, account updates, open orders),
    which is too heavy for a simple health probe and can emit noisy
    ``account updates request timed out`` / IB 321 messages on some
    Gateway setups even though the API socket is otherwise healthy.
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
            ib.client.connectAsync(
                host=config.host,
                port=config.port,
                clientId=probe_client_id,
            ),
            timeout=IB_TIMEOUT_SECONDS,
        )
        return bool(ib.client.isReady())
    except (TimeoutError, ConnectionError, OSError):
        return False
    except Exception:
        logger.debug("ALPHAEDGE GW: API validation failed", exc_info=True)
        return False
    finally:
        if ib.client.isReady():
            ib.disconnect()
