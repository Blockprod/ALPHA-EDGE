# ============================================================
# PROJECT      : ALPHAEDGE — FCR Forex Trading Bot
# FILE         : alphaedge/engine/dashboard.py
# DESCRIPTION  : Rich terminal dashboard for real-time monitoring
# AUTHOR       : ALPHAEDGE Dev Team
# WORKFLOW     : VSCode + Claude + Copilot Pro + File Engineering
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-07
# ============================================================
"""ALPHAEDGE — FCR Forex Trading Bot: real-time Rich terminal dashboard."""

from __future__ import annotations

import asyncio
from typing import Any

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from alphaedge.config.constants import PROJECT_TITLE
from alphaedge.utils.logger import get_logger
from alphaedge.utils.timezone import (
    is_session_active,
    now_paris,
    now_utc,
)

logger = get_logger()

console = Console()


# ------------------------------------------------------------------
# Build the header panel
# ------------------------------------------------------------------
def _build_header(ib_connected: bool) -> Panel:
    """
    Create the dashboard header with title and connection status.

    Parameters
    ----------
    ib_connected : bool
        Whether IB Gateway is connected.

    Returns
    -------
    Panel
        Rich Panel for the header.
    """
    status_icon = "[bold green]●[/]" if ib_connected else "[bold red]●[/]"
    status_text = "CONNECTED" if ib_connected else "DISCONNECTED"
    title_text = Text(PROJECT_TITLE, style="bold cyan")

    header_content = f"{title_text}\n" f"IB Gateway: {status_icon} {status_text}"
    return Panel(header_content, style="bold white", border_style="cyan")


# ------------------------------------------------------------------
# Build the time display panel
# ------------------------------------------------------------------
def _build_time_panel() -> Panel:
    """
    Create the dual-time panel (UTC + Europe/Paris).

    Returns
    -------
    Panel
        Rich Panel with time info.
    """
    utc_now = now_utc()
    paris_now = now_paris()
    session_active = is_session_active()

    session_status = "[bold green]ACTIVE[/]" if session_active else "[dim]INACTIVE[/]"

    time_table = Table(show_header=True, header_style="bold magenta")
    time_table.add_column("Timezone", width=14)
    time_table.add_column("Time", width=22)
    time_table.add_row("UTC", utc_now.strftime("%Y-%m-%d %H:%M:%S"))
    time_table.add_row("Europe/Paris", paris_now.strftime("%Y-%m-%d %H:%M:%S %Z"))

    return Panel(
        time_table,
        title=f"Session: {session_status}",
        border_style="blue",
    )


# ------------------------------------------------------------------
# Build the signal status table
# ------------------------------------------------------------------
def _build_signal_panel(
    state: dict[str, Any],
) -> Panel:
    """
    Create the signal status panel.

    Parameters
    ----------
    state : dict
        Current strategy state data.

    Returns
    -------
    Panel
        Rich Panel with signal information.
    """
    signal_table = Table(show_header=True, header_style="bold yellow")
    signal_table.add_column("Pair", width=10)
    signal_table.add_column("FCR", width=15)
    signal_table.add_column("Gap", width=10)
    signal_table.add_column("Signal", width=12)
    signal_table.add_column("Spread", width=10)

    for pair_data in state.get("pairs", []):
        fcr_str = _format_fcr(pair_data.get("fcr"))
        gap_str = _format_gap(pair_data.get("gap"))
        signal_str = _format_signal(pair_data.get("signal"))
        spread_str = f"{pair_data.get('spread', 0.0):.1f} pips"

        signal_table.add_row(
            pair_data.get("pair", "—"),
            fcr_str,
            gap_str,
            signal_str,
            spread_str,
        )

    return Panel(signal_table, title="Signals", border_style="yellow")


# ------------------------------------------------------------------
# Format FCR detection status
# ------------------------------------------------------------------
def _format_fcr(fcr: dict[str, Any] | None) -> str:
    """Format FCR result for dashboard display."""
    if fcr is None:
        return "[dim]Scanning...[/]"
    if fcr.get("detected"):
        return f"H:{fcr['range_high']:.5f}\nL:{fcr['range_low']:.5f}"
    return "[dim]None[/]"


# ------------------------------------------------------------------
# Format gap detection status
# ------------------------------------------------------------------
def _format_gap(gap: dict[str, Any] | None) -> str:
    """Format gap result for dashboard display."""
    if gap is None:
        return "[dim]—[/]"
    if gap.get("detected"):
        return f"[green]ATR {gap['atr_ratio']:.1f}x[/]"
    return "[dim]No spike[/]"


# ------------------------------------------------------------------
# Format signal status
# ------------------------------------------------------------------
def _format_signal(signal: dict[str, Any] | None) -> str:
    """Format engulfing signal for dashboard display."""
    if signal is None:
        return "[dim]Waiting...[/]"
    if signal.get("detected"):
        direction = "SELL" if signal["signal"] == -1 else "BUY"
        color = "red" if signal["signal"] == -1 else "green"
        return f"[bold {color}]{direction}[/]"
    return "[dim]None[/]"


# ------------------------------------------------------------------
# Build the position and P&L panel
# ------------------------------------------------------------------
def _add_position_rows(
    table: Table,
    state: dict[str, Any],
) -> None:
    """Populate position table with current state data."""
    position = state.get("position", {})
    daily = state.get("daily", {})

    table.add_row("Open Position", position.get("pair", "None"))
    table.add_row("Direction", position.get("direction_str", "—"))
    table.add_row("P&L (pips)", _color_pnl(position.get("pnl_pips", 0.0)))
    table.add_row("P&L (USD)", _color_pnl(position.get("pnl_usd", 0.0)))
    table.add_row("Trades Today", str(daily.get("trades_today", 0)))
    table.add_row("Daily P&L", _color_pnl(daily.get("daily_pnl", 0.0)))
    table.add_row("Next Trade", _trade_eligibility(daily))


def _build_position_panel(
    state: dict[str, Any],
) -> Panel:
    """Create the open position and P&L panel."""
    pos_table = Table(show_header=True, header_style="bold green")
    pos_table.add_column("Field", width=18)
    pos_table.add_column("Value", width=20)

    _add_position_rows(pos_table, state)

    return Panel(pos_table, title="Position & P&L", border_style="green")


# ------------------------------------------------------------------
# Color P&L values
# ------------------------------------------------------------------
def _color_pnl(value: float) -> str:
    """Return colored P&L string based on positive/negative."""
    if value > 0:
        return f"[green]+{value:.2f}[/]"
    if value < 0:
        return f"[red]{value:.2f}[/]"
    return "[dim]0.00[/]"


# ------------------------------------------------------------------
# Trade eligibility check
# ------------------------------------------------------------------
def _trade_eligibility(daily: dict[str, Any]) -> str:
    """Determine if a new trade can be placed."""
    if daily.get("limit_breached", False):
        return "[bold red]BLOCKED — daily limit[/]"
    max_trades = daily.get("max_trades", 2)
    trades = daily.get("trades_today", 0)
    if trades >= max_trades:
        return "[yellow]Max trades reached[/]"
    return f"[green]Eligible ({max_trades - trades} left)[/]"


# ------------------------------------------------------------------
# Build the full dashboard layout
# ------------------------------------------------------------------
def build_dashboard(
    state: dict[str, Any],
    ib_connected: bool,
) -> Layout:
    """
    Assemble the complete dashboard layout.

    Parameters
    ----------
    state : dict
        Current strategy state data.
    ib_connected : bool
        IB Gateway connection status.

    Returns
    -------
    Layout
        Rich Layout for the dashboard.
    """
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )

    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )

    layout["header"].update(_build_header(ib_connected))
    layout["left"].split_column(
        Layout(_build_time_panel(), name="time", size=7),
        Layout(_build_signal_panel(state), name="signals"),
    )
    layout["right"].update(_build_position_panel(state))
    layout["footer"].update(
        Panel(
            "[dim]Press Ctrl+C to stop | ALPHAEDGE v1.0.0[/]",
            border_style="dim",
        )
    )

    return layout


# ------------------------------------------------------------------
# Dashboard runner (live-updating terminal)
# ------------------------------------------------------------------
async def run_dashboard(
    state_provider: Any,
    refresh_rate: float = 1.0,
) -> None:
    """
    Run the live-updating Rich dashboard.

    Parameters
    ----------
    state_provider : callable
        Async function returning the current strategy state dict.
    refresh_rate : float
        Dashboard refresh interval in seconds.
    """
    logger.info("ALPHAEDGE dashboard starting")

    with Live(console=console, refresh_per_second=int(1 / refresh_rate)) as live:
        try:
            while True:
                state = await state_provider()
                ib_connected = state.get("ib_connected", False)
                layout = build_dashboard(state, ib_connected)
                live.update(layout)
                await asyncio.sleep(refresh_rate)
        except KeyboardInterrupt:
            logger.info("ALPHAEDGE dashboard stopped by user")


# ------------------------------------------------------------------
# Demo state provider for standalone testing
# ------------------------------------------------------------------
async def _demo_state() -> dict[str, Any]:
    """Return a demo state dict for testing the dashboard."""
    return {
        "ib_connected": False,
        "pairs": [
            {
                "pair": "EURUSD",
                "fcr": {"detected": True, "range_high": 1.08550, "range_low": 1.08400},
                "gap": {"detected": False, "atr_ratio": 0.8},
                "signal": None,
                "spread": 0.8,
            },
            {
                "pair": "GBPUSD",
                "fcr": None,
                "gap": None,
                "signal": None,
                "spread": 1.2,
            },
        ],
        "position": {
            "pair": "None",
            "direction_str": "—",
            "pnl_pips": 0.0,
            "pnl_usd": 0.0,
        },
        "daily": {
            "trades_today": 0,
            "max_trades": 2,
            "daily_pnl": 0.0,
            "limit_breached": False,
        },
    }


if __name__ == "__main__":
    print(f"{PROJECT_TITLE} — Dashboard standalone test")
    asyncio.run(run_dashboard(_demo_state, refresh_rate=2.0))
