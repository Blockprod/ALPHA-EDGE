# ============================================================
# PROJECT      : ALPHAEDGE — Momentum+Carry Forex Trading Bot
# FILE         : alphaedge/engine/regime_filter.py
# DESCRIPTION  : Daily market regime classifier (K-Means, observation mode)
# PYTHON       : 3.11.9
# LAST UPDATED : 2026-03-22
# ============================================================
"""Daily market regime detection via K-Means clustering.

This module classifies each trading day as high_vol or low_vol
based on pre-session M5 bar features. It operates in **observation
mode only**: the regime label is logged but never blocks a trade.

Integration point: strategy.py → _detect_momentum() → log regime only.
Activation guard (blocking trades) requires 30 NYSE sessions of
observation + explicit confirmation before enabling.
"""

from __future__ import annotations

import pathlib
from datetime import date
from typing import Any

import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from alphaedge.utils.logger import get_logger

logger = get_logger()

_CACHE_DIR = pathlib.Path(__file__).parent.parent / "cache"
_RECALIBRATION_DAYS = 30


def _cache_path(pair: str) -> pathlib.Path:
    return _CACHE_DIR / f"regime_model_{pair}.pkl"


def _extract_daily_features(daily_bars: list[dict[str, Any]]) -> list[float] | None:
    """Extract [atr_daily, intraday_range, momentum] from a list of Daily bars.

    Accepts either a window of Daily bars (one bar per calendar day) or a
    list of intra-day bars for a single session.  Requires at least one bar.

    Parameters
    ----------
    daily_bars : list[dict]
        Bars for the period to analyse.  Each bar must have keys:
        ``open``, ``high``, ``low``, ``close``.  For Daily bars, one
        element represents one full trading day.

    Returns
    -------
    list[float] | None
        ``[atr_daily, intraday_range, momentum]`` or ``None`` if the list
        is empty.
    """
    if len(daily_bars) < 1:
        return None

    highs = [b["high"] for b in daily_bars]
    lows = [b["low"] for b in daily_bars]
    closes = [b["close"] for b in daily_bars]
    opens = [b["open"] for b in daily_bars]

    # ATR daily = std of per-bar ranges; for a single bar use the bar range.
    ranges = [h - lo for h, lo in zip(highs, lows)]
    atr_daily = float(np.std(ranges)) if len(ranges) > 1 else ranges[0]

    # Intraday range = max(highs) - min(lows) over the window.
    intraday_range = max(highs) - min(lows)

    # Momentum = last close - first open (works for both single and multi-bar).
    momentum = closes[-1] - opens[0]

    return [atr_daily, intraday_range, momentum]


class DailyRegimeFilter:
    """K-Means daily regime classifier (observation mode).

    Usage
    -----
    ::

        flt = DailyRegimeFilter()
        flt.fit(daily_bars_history)         # train on ≥30 days of Daily bars
        regime = flt.predict(today, pre_session_m5)
        # returns: "high_vol" | "low_vol" | "unknown"

    """

    def __init__(self) -> None:
        self._kmeans: KMeans | None = None
        self._scaler: StandardScaler | None = None
        self._high_vol_cluster: int = 0
        self._last_fit_date: date | None = None

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------
    def fit(
        self,
        daily_bars_history: list[dict[str, Any]],
        pair: str = "",
    ) -> None:
        """Train the K-Means classifier on historical Daily bars.

        Bars are grouped into daily buckets by the ``datetime`` key.
        Requires at least 10 days with valid features to fit.

        Parameters
        ----------
        daily_bars_history : list[dict]
            Full history of bars (each bar must have a ``datetime`` key).
            Accepts both Daily bars (one bar per day) and intra-day bars
            (e.g. M5 — grouped by calendar date internally).
        pair : str
            Currency pair — used for cache file naming only.
        """
        # Group bars by calendar date
        _daily_buckets: dict[date, list[dict[str, Any]]] = {}
        for bar in daily_bars_history:
            dt = bar.get("datetime")
            if dt is None:
                continue
            d = dt.date() if hasattr(dt, "date") else dt
            _daily_buckets.setdefault(d, []).append(bar)

        # Extract features per day
        feature_rows: list[list[float]] = []
        for bars in _daily_buckets.values():
            feats = _extract_daily_features(bars)
            if feats is not None:
                feature_rows.append(feats)

        if len(feature_rows) < 10:
            logger.warning(
                "DailyRegimeFilter.fit: insufficient data (%d days < 10) — "
                "regime detection disabled",
                len(feature_rows),
            )
            return

        x_arr = np.array(feature_rows, dtype=np.float64)
        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(x_arr)

        kmeans = KMeans(n_clusters=2, random_state=42, n_init="auto")
        kmeans.fit(x_scaled)

        # Identify which cluster is "high_vol" (cluster with highest avg ATR)
        labels = [int(label) for label in kmeans.predict(x_scaled)]
        cluster_atr: dict[int, float] = {}
        for i, label in enumerate(labels):
            cluster_atr.setdefault(label, 0.0)
            cluster_atr[label] += feature_rows[i][0]  # atr_daily index
        counts: dict[int, int] = {}
        for label in labels:
            counts[label] = counts.get(label, 0) + 1
        avg_atr = {k: cluster_atr[k] / counts[k] for k in cluster_atr}
        high_vol_cluster = max(avg_atr, key=lambda k: avg_atr[k])

        self._kmeans = kmeans
        self._scaler = scaler
        self._high_vol_cluster = high_vol_cluster
        self._last_fit_date = date.today()

        logger.info(
            "DailyRegimeFilter.fit: trained on %d days — high_vol cluster=%d",
            len(feature_rows),
            high_vol_cluster,
        )

        if pair:
            self._save(pair)

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------
    def predict(
        self,
        session_date: date,  # noqa: ARG002 — reserved for future per-date logging
        pre_session_m5: list[dict[str, Any]],
    ) -> str:
        """Predict the market regime for a given session.

        Parameters
        ----------
        session_date : date
            The date of the upcoming session (used for logging).
        pre_session_m5 : list[dict]
            Pre-session M5 bars (typically last 30 minutes before session open).

        Returns
        -------
        str
            ``"high_vol"``, ``"low_vol"``, or ``"unknown"`` if classifier
            is not trained or features cannot be extracted.
        """
        if self._kmeans is None or self._scaler is None:
            return "unknown"

        feats = _extract_daily_features(pre_session_m5)
        if feats is None:
            return "unknown"

        x_arr = np.array([feats], dtype=np.float64)
        x_scaled = self._scaler.transform(x_arr)
        cluster = int(self._kmeans.predict(x_scaled)[0])

        regime = "high_vol" if cluster == self._high_vol_cluster else "low_vol"
        logger.info(
            "DailyRegimeFilter.predict: %s → regime=%s (cluster=%d) [OBSERVATION ONLY]",
            session_date,
            regime,
            cluster,
        )
        return regime

    # ------------------------------------------------------------------
    # Recalibration guard
    # ------------------------------------------------------------------
    def needs_recalibration(self, reference_date: date | None = None) -> bool:
        """Return True if the model is older than _RECALIBRATION_DAYS days.

        Parameters
        ----------
        reference_date : date | None
            Date to compare against. Defaults to today.
        """
        if self._last_fit_date is None:
            return True
        ref = reference_date or date.today()
        return (ref - self._last_fit_date).days > _RECALIBRATION_DAYS

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _save(self, pair: str) -> None:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path(pair)
        payload = {
            "kmeans": self._kmeans,
            "scaler": self._scaler,
            "high_vol_cluster": self._high_vol_cluster,
            "last_fit_date": self._last_fit_date,
        }
        joblib.dump(payload, path)
        logger.debug("DailyRegimeFilter: model saved to %s", path)

    def load(self, pair: str) -> bool:
        """Load a previously serialised model. Returns True on success."""
        path = _cache_path(pair)
        if not path.exists():
            return False
        payload: dict[str, Any] = joblib.load(path)
        self._kmeans = payload["kmeans"]
        self._scaler = payload["scaler"]
        self._high_vol_cluster = payload["high_vol_cluster"]
        self._last_fit_date = payload["last_fit_date"]
        logger.info("DailyRegimeFilter: model loaded from %s", path)
        return True
