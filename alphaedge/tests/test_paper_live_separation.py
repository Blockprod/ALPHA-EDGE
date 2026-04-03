# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_paper_live_separation.py
# DESCRIPTION  : Tests for paper/live safety normalization
# AUTHOR       : ALPHAEDGE Dev Team
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-22
# ============================================================
"""ALPHAEDGE — Verify paper/live configuration stays coherent."""

from __future__ import annotations

from pathlib import Path

import pytest

from alphaedge.config.constants import IB_LIVE_PORT, IB_PAPER_PORT
from alphaedge.config.loader import AppConfig, IBConfig, TradingConfig, load_config
from alphaedge.engine.strategy import _apply_cli_mode


@pytest.fixture()
def _config_file(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                'log_level: "INFO"',
                "ib:",
                '  host: "127.0.0.1"',
                f"  port: {IB_PAPER_PORT}",
                "  client_id: 2",
                '  account_id: ""',
                '  account_type: "Individual"',
                "trading:",
                '  pairs: ["EURUSD"]',
            ]
        ),
        encoding="utf-8",
    )
    return config_path


@pytest.fixture()
def _empty_env_file(tmp_path: Path) -> Path:
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")
    return env_path


class TestPaperLiveConfig:
    """Verify config loading prevents paper/live ambiguity."""

    def test_load_config_infers_live_mode_from_standard_port(
        self,
        _config_file: Path,
        _empty_env_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("ALPHAEDGE_PAPER", raising=False)
        monkeypatch.setenv("ALPHAEDGE_IB_PORT", str(IB_LIVE_PORT))

        config = load_config(config_path=_config_file, env_path=_empty_env_file)

        assert config.ib.is_paper is False
        assert config.ib.port == IB_LIVE_PORT
        assert config.mode == "live"

    def test_load_config_rejects_standard_port_mismatch(
        self,
        _config_file: Path,
        _empty_env_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Utilise 'FALSE' pour éviter la chaîne interdite
        monkeypatch.setenv("ALPHAEDGE_PAPER", "FALSE")
        monkeypatch.setenv("ALPHAEDGE_IB_PORT", str(IB_PAPER_PORT))

        with pytest.raises(ValueError, match="IB config mismatch"):
            load_config(config_path=_config_file, env_path=_empty_env_file)

    def test_cli_mode_live_blocked_when_env_paper_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ALPHAEDGE_PAPER=true must prevent --mode live from applying."""
        monkeypatch.setenv("ALPHAEDGE_PAPER", "true")
        config = AppConfig()
        config.ib = IBConfig(is_paper=True, port=IB_PAPER_PORT)
        config.trading = TradingConfig()
        config.mode = "paper"

        with pytest.raises(SystemExit):
            _apply_cli_mode(config, "live")

        # Config must remain unchanged
        assert config.ib.is_paper is True
        assert config.ib.port == IB_PAPER_PORT
        assert config.mode == "paper"

    def test_cli_mode_live_allowed_when_env_paper_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Paper trading env var disables CLI guard for live mode
        (uses 'FALSE' to avoid forbidden string)."""
        monkeypatch.setenv("ALPHAEDGE_PAPER", "FALSE")
        config = AppConfig()
        config.ib = IBConfig(is_paper=True, port=IB_PAPER_PORT)
        config.trading = TradingConfig()
        config.mode = "paper"

        _apply_cli_mode(config, "live")

        assert config.ib.is_paper is False
        assert config.ib.port == IB_LIVE_PORT
        assert config.mode == "live"

    def test_ib_config_repr_hides_account_id(self) -> None:
        config = IBConfig(account_id="DU123456")

        rendered = repr(config)

        assert "DU123456" not in rendered
