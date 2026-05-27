# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/tests/test_data_feed_cache_json.py
# DESCRIPTION  : Tests for BarDiskCache JSON serialisation
# ============================================================
"""Tests — BarDiskCache JSON read/write (replaces legacy pickle cache)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from alphaedge.engine.data_feed import BarDiskCache


@pytest.fixture()
def tmp_cache(tmp_path: Path) -> BarDiskCache:
    return BarDiskCache(cache_dir=tmp_path)


def _make_bars(n: int = 3) -> list[dict]:
    return [
        {
            "open": 1.1000 + i * 0.001,
            "high": 1.1010 + i * 0.001,
            "low": 1.0990 + i * 0.001,
            "close": 1.1005 + i * 0.001,
            "volume": 100.0,
            "timestamp": 1700000000 + i * 86400,
            "datetime": datetime(2023, 11, 14 + i, 15, 30, 0, tzinfo=UTC),
        }
        for i in range(n)
    ]


class TestBarDiskCacheJson:
    def test_save_creates_json_file(
        self, tmp_cache: BarDiskCache, tmp_path: Path
    ) -> None:
        tmp_cache.save("EURUSD", "1 day", _make_bars())
        p = tmp_path / "EURUSD_1_day.json"
        assert p.exists()

    def test_save_produces_valid_json(
        self, tmp_cache: BarDiskCache, tmp_path: Path
    ) -> None:
        tmp_cache.save("EURUSD", "1 day", _make_bars())
        p = tmp_path / "EURUSD_1_day.json"
        raw = json.loads(p.read_text(encoding="utf-8"))
        assert isinstance(raw, list)
        assert len(raw) == 3

    def test_load_restores_bars(self, tmp_cache: BarDiskCache) -> None:
        original = _make_bars(5)
        tmp_cache.save("USDJPY", "1 day", original)
        loaded = tmp_cache.load("USDJPY", "1 day")
        assert loaded is not None
        assert len(loaded) == 5

    def test_load_restores_datetime_objects(self, tmp_cache: BarDiskCache) -> None:
        original = _make_bars(2)
        tmp_cache.save("EURUSD", "1 day", original)
        loaded = tmp_cache.load("EURUSD", "1 day")
        assert loaded is not None
        assert isinstance(loaded[0]["datetime"], datetime)

    def test_load_missing_returns_none(self, tmp_cache: BarDiskCache) -> None:
        result = tmp_cache.load("GBPUSD", "1 day")
        assert result is None

    def test_load_corrupt_file_returns_none_and_purges(
        self, tmp_cache: BarDiskCache, tmp_path: Path
    ) -> None:
        p = tmp_path / "EURUSD_1_day.json"
        p.write_text("{{not valid json}}", encoding="utf-8")
        result = tmp_cache.load("EURUSD", "1 day")
        assert result is None
        assert not p.exists()

    def test_legacy_pkl_migration(
        self, tmp_cache: BarDiskCache, tmp_path: Path
    ) -> None:
        """If a .pkl file exists but no .json, load() migrates it on first access."""
        import pickle  # noqa: PLC0415

        bars = _make_bars(4)
        pkl_path = tmp_path / "EURUSD_1_day.pkl"
        with pkl_path.open("wb") as fh:
            pickle.dump(bars, fh)

        loaded = tmp_cache.load("EURUSD", "1 day")
        assert loaded is not None
        assert len(loaded) == 4
        # .pkl should be gone; .json should exist
        assert not pkl_path.exists()
        assert (tmp_path / "EURUSD_1_day.json").exists()
