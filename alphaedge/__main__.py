# ============================================================
# PROJECT      : ALPHAEDGE
# FILE         : alphaedge/__main__.py
# DESCRIPTION  : CLI entry point — `python -m alphaedge`
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-04-06
# ============================================================
"""ALPHAEDGE — CLI entry point.

Invocation::

    python -m alphaedge [--mode paper|live] [--config path/to/config.yaml]

All orchestration logic lives in ``alphaedge.engine.strategy.SwingStrategy``.
This module is intentionally thin: it parses CLI args, starts the event loop,
and applies the Windows ProactorEventLoop monkey-patch.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import signal
import sys
from typing import Any

from alphaedge.config.constants import (
    IB_GATEWAY_WATCHDOG_INTERVAL_SECONDS,
    IB_LIVE_PORT,
    IB_PAPER_PORT,
)
from alphaedge.config.loader import AppConfig, load_config
from alphaedge.engine.strategy import SwingStrategy
from alphaedge.utils.gw_manager import check_gateway_health, ensure_gateway_ready
from alphaedge.utils.logger import get_logger, setup_logging
from alphaedge.utils.timezone import is_weekend_paris

logger = get_logger()


# ------------------------------------------------------------------
# Lightweight I/O helpers (no print)
# ------------------------------------------------------------------
def _stdout(message: str) -> None:
    """Emit user-facing CLI messages without using print()."""
    sys.stdout.write(f"{message}\n")


def _stderr(message: str) -> None:
    """Emit user-facing CLI error messages without using print()."""
    sys.stderr.write(f"{message}\n")


# ------------------------------------------------------------------
# CLI argument parsing
# ------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="ALPHAEDGE — Momentum+Carry")
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default="paper",
        help="Trading mode (default: paper)",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config.yaml",
    )
    return parser.parse_args()


# ------------------------------------------------------------------
# Config mode application
# ------------------------------------------------------------------
def _apply_cli_mode(config: AppConfig, mode: str) -> None:
    """Apply an explicit CLI trading mode to the loaded config."""
    if mode == "paper":
        config.ib.is_paper = True
        config.ib.port = IB_PAPER_PORT
        config.mode = "paper"
        return

    # Guard: ALPHAEDGE_PAPER=true ENV takes precedence over CLI --mode live.
    # This prevents switching to live mode when the ENV guard is active.
    env_paper = os.getenv("ALPHAEDGE_PAPER", "true").strip().lower()
    if env_paper == "true":
        _stderr(
            "ERROR: ALPHAEDGE_PAPER=true is set in environment. "
            "Cannot switch to live mode via --mode live. "
            "Unset ALPHAEDGE_PAPER (or set it to 'false') to enable live trading."
        )
        raise SystemExit(1)

    config.ib.is_paper = False
    config.ib.port = IB_LIVE_PORT
    config.mode = "live"


# ------------------------------------------------------------------
# Windows ProactorEventLoop pipe-write race fix
# ------------------------------------------------------------------
def _apply_proactor_monkey_patch() -> None:
    """Suppress harmless AssertionError from Windows ProactorEventLoop.

    On Windows, asyncio uses ProactorEventLoop which can trigger a harmless
    AssertionError in _loop_writing when two concurrent writes hit the same
    stderr pipe transport (e.g. loguru + uvicorn + asyncio's own error logger).
    This monkey-patch catches the assertion at the source — before asyncio
    formats a traceback and tries to write it to stderr (which would trigger
    the same race again). Affects ALL event loops in ALL threads.
    """
    import asyncio.proactor_events as _pev

    _transport_cls = getattr(_pev, "_ProactorBaseWritePipeTransport", None)
    if _transport_cls is None:
        return  # Non-Windows platform — no-op

    _original_loop_writing = getattr(_transport_cls, "_loop_writing")

    def _patched_loop_writing(
        self: object, f: object = None, data: object = None
    ) -> None:
        try:
            _original_loop_writing(self, f, data)
        except AssertionError:
            # Harmless: two futures overlapped on the same pipe transport.
            # The write still succeeds — the assertion is a stale-future check.
            pass

    setattr(_transport_cls, "_loop_writing", _patched_loop_writing)


async def _run_gateway_watchdog_tick(
    strategy: SwingStrategy,
    config: AppConfig,
) -> None:
    """Refresh gateway availability without relaunching over a live broker session."""
    broker_connected = bool(getattr(strategy._broker, "is_connected", False))
    if broker_connected:
        strategy.set_gateway_health(
            gateway_connected=True,
            gateway_status="healthy",
        )
        return

    if await check_gateway_health(config.ib):
        strategy.set_gateway_health(
            gateway_connected=True,
            gateway_status="healthy",
        )
        return

    strategy.set_gateway_health(
        gateway_connected=False,
        gateway_status="down",
    )
    logger.warning(
        "ALPHAEDGE GW: Watchdog detected unavailable gateway — reasserting availability"
    )
    if not await ensure_gateway_ready(config.ib):
        logger.error("ALPHAEDGE GW: Watchdog could not restore gateway availability")
        return

    strategy.set_gateway_health(
        gateway_connected=True,
        gateway_status="healthy",
    )


# ------------------------------------------------------------------
# Async main
# ------------------------------------------------------------------
async def _main() -> None:
    """Async main entry point."""
    args = _parse_args()

    # ⚠️ WARNING: Live trading involves real money risk
    if args.mode == "live":
        _stdout("=" * 60)
        _stdout("⚠️  WARNING: LIVE TRADING MODE")
        _stdout("⚠️  Real money is at risk. Proceed with extreme caution.")
        _stdout("=" * 60)
        try:
            confirm = input("Type 'YES' to confirm live trading: ")
        except (EOFError, KeyboardInterrupt):
            _stdout("\nALPHAEDGE: Live trading cancelled (no interactive input).")
            sys.exit(1)
        if confirm != "YES":
            _stdout("ALPHAEDGE: Live trading cancelled.")
            sys.exit(0)

    setup_logging()
    config = load_config(config_path=args.config)
    _apply_cli_mode(config, args.mode)

    if args.mode == "paper":
        _stdout("=" * 60)
        _stdout("📝  ALPHAEDGE — PAPER TRADING MODE")
        _stdout(f"📝  No real money at risk. IB Gateway port {IB_PAPER_PORT}.")
        _stdout("=" * 60)
    else:
        _stdout("=" * 60)
        _stdout("⚠️  ALPHAEDGE — LIVE TRADING MODE")
        _stdout(f"⚠️  IB Gateway live port {IB_LIVE_PORT} selected.")
        _stdout("=" * 60)

    strategy = SwingStrategy(config)
    _gateway_watchdog_task: asyncio.Task[None] | None = None

    async def _gateway_watchdog() -> None:
        while not strategy._shutdown_requested:
            await asyncio.sleep(IB_GATEWAY_WATCHDOG_INTERVAL_SECONDS)
            if strategy._shutdown_requested or is_weekend_paris():
                continue
            if getattr(strategy, "_reconnecting", False):
                continue
            try:
                await _run_gateway_watchdog_tick(strategy, config)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("ALPHAEDGE GW: Watchdog failed")

    # Install signal handlers for graceful shutdown
    # add_signal_handler is not supported on Windows — use try/except for all signals
    loop = asyncio.get_running_loop()

    # Route asyncio callback exceptions through loguru instead of raw stderr writes.
    # This prevents _ProactorBaseWritePipeTransport._loop_writing AssertionError
    # caused by asyncio writing exception tracebacks directly to sys.stderr while
    # the ProactorEventLoop pipe transport is busy with another write (Windows race).
    def _asyncio_exception_handler(
        _lp: asyncio.AbstractEventLoop, context: dict[str, Any]
    ) -> None:
        exc = context.get("exception")
        # Suppress the known Windows ProactorEventLoop pipe-write race — harmless.
        if isinstance(exc, AssertionError) and "_write_fut" in str(exc):
            return
        msg = context.get("message", "Unknown asyncio error")
        if exc is not None:
            logger.error(f"Asyncio callback exception: {msg}", exc_info=exc)
        else:
            logger.error(f"Asyncio error: {msg} | {context}")

    loop.set_exception_handler(_asyncio_exception_handler)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                sig,
                lambda: asyncio.ensure_future(strategy.graceful_shutdown()),
            )
        except NotImplementedError:
            pass  # Windows — signal handlers not supported via asyncio loop

    # Optional web dashboard (FastAPI REST + WebSocket)
    _dashboard_task: asyncio.Task[None] | None = None
    if config.dashboard_raw.get("enabled", False):
        import threading

        from alphaedge.engine.web_dashboard import (
            configure_auth,
            install_dashboard_log_sink,
            run_web_dashboard,
            start_server,
        )

        dash_host: str = str(config.dashboard_raw.get("host", "127.0.0.1"))
        dash_port: int = int(config.dashboard_raw.get("port", 8080))
        dash_token: str = str(config.dashboard_raw.get("api_token", ""))
        if dash_token:
            configure_auth(dash_token)
        install_dashboard_log_sink(level="INFO")

        threading.Thread(
            target=start_server,
            args=(dash_host, dash_port),
            daemon=True,
            name="alphaedge-web-dashboard",
        ).start()
        logger.info(f"Web dashboard: http://{dash_host}:{dash_port}/")

        async def _get_dashboard_state() -> dict[str, Any]:
            return strategy.get_live_state()

        _dashboard_task = asyncio.create_task(
            run_web_dashboard(_get_dashboard_state, refresh_rate=2.0),
            name="web-dashboard-loop",
        )

    _gateway_watchdog_task = asyncio.create_task(
        _gateway_watchdog(),
        name="gateway-watchdog",
    )

    try:
        while not strategy._shutdown_requested:
            await strategy.run_session()
            if strategy._shutdown_requested:
                break
            # Brief pause between sessions (daily loss shutdown resets next day)
            logger.info("ALPHAEDGE: Session complete — waiting for next session window")
            await asyncio.sleep(60.0)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("ALPHAEDGE: Interrupted — triggering graceful shutdown")
        await strategy.graceful_shutdown()
    finally:
        if _gateway_watchdog_task is not None:
            _gateway_watchdog_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _gateway_watchdog_task
        if _dashboard_task is not None:
            _dashboard_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _dashboard_task


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
if __name__ == "__main__":
    _apply_proactor_monkey_patch()
    asyncio.run(_main())
