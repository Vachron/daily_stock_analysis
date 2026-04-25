# -*- coding: utf-8 -*-
"""Market regime detector and dynamic strategy weight adjuster.

Detects the current market regime from index-level data and adjusts
strategy weights accordingly. Strategies whose market_regimes match
the detected regime receive a boost; mismatched strategies are dampened.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

REGIME_TRENDING_UP = "trending_up"
REGIME_TRENDING_DOWN = "trending_down"
REGIME_SIDEWAYS = "sideways"
REGIME_VOLATILE = "volatile"
REGIME_SECTOR_HOT = "sector_hot"

ALL_REGIMES = [REGIME_TRENDING_UP, REGIME_TRENDING_DOWN, REGIME_SIDEWAYS, REGIME_VOLATILE, REGIME_SECTOR_HOT]

REGIME_LABELS = {
    REGIME_TRENDING_UP: "上升趋势",
    REGIME_TRENDING_DOWN: "下降趋势",
    REGIME_SIDEWAYS: "横盘震荡",
    REGIME_VOLATILE: "高波动",
    REGIME_SECTOR_HOT: "板块轮动",
}

STRATEGY_BASE_WEIGHTS: Dict[str, float] = {
    "bull_trend": 1.0,
    "ma_golden_cross": 0.8,
    "multi_golden_cross": 0.9,
    "macd_divergence": 0.85,
    "rsi_reversal": 0.75,
    "bollinger_reversion": 0.7,
    "shrink_pullback": 0.8,
    "volume_breakout": 0.85,
    "limit_up_pullback": 0.6,
    "morning_star": 0.65,
    "w_bottom": 0.7,
    "bottom_volume": 0.75,
    "turtle_trading": 0.6,
    "box_oscillation": 0.55,
    "momentum_reversal": 0.65,
    "dragon_head": 0.7,
    "chan_theory": 0.5,
    "wave_theory": 0.5,
    "emotion_cycle": 0.55,
    "one_yang_three_yin": 0.45,
    "risk_filter": 1.0,
}

STRATEGY_REGIME_MAP: Dict[str, List[str]] = {
    "bull_trend": [REGIME_TRENDING_UP],
    "ma_golden_cross": [REGIME_TRENDING_UP],
    "multi_golden_cross": [REGIME_TRENDING_UP, REGIME_SECTOR_HOT],
    "macd_divergence": [REGIME_TRENDING_UP, REGIME_TRENDING_DOWN],
    "rsi_reversal": [REGIME_SIDEWAYS, REGIME_TRENDING_DOWN],
    "bollinger_reversion": [REGIME_SIDEWAYS],
    "shrink_pullback": [REGIME_TRENDING_DOWN, REGIME_SIDEWAYS],
    "volume_breakout": [REGIME_TRENDING_UP],
    "limit_up_pullback": [REGIME_SECTOR_HOT, REGIME_TRENDING_UP],
    "morning_star": [REGIME_TRENDING_DOWN, REGIME_SIDEWAYS],
    "w_bottom": [REGIME_TRENDING_DOWN, REGIME_SIDEWAYS],
    "bottom_volume": [REGIME_TRENDING_DOWN],
    "turtle_trading": [REGIME_TRENDING_UP, REGIME_VOLATILE],
    "box_oscillation": [REGIME_SIDEWAYS],
    "momentum_reversal": [REGIME_TRENDING_UP, REGIME_SECTOR_HOT],
    "dragon_head": [REGIME_SECTOR_HOT],
    "chan_theory": [REGIME_VOLATILE],
    "wave_theory": [REGIME_VOLATILE],
    "emotion_cycle": [REGIME_SECTOR_HOT],
    "one_yang_three_yin": [],
    "risk_filter": ALL_REGIMES,
}

REGIME_BOOST = 1.5
REGIME_DAMPEN = 0.5
REGIME_NEUTRAL = 1.0

CATEGORY_WEIGHTS: Dict[str, float] = {
    "trend": 0.35,
    "reversal": 0.25,
    "pattern": 0.15,
    "framework": 0.15,
    "screener": 0.0,
}


@dataclass
class RegimeResult:
    regime: str = REGIME_SIDEWAYS
    confidence: float = 0.5
    indicators: Dict[str, Any] = field(default_factory=dict)
    label: str = ""


class MarketRegimeDetector:
    """Detect current market regime from index data."""

    def detect(self, index_df: Optional[pd.DataFrame] = None) -> RegimeResult:
        if index_df is not None and len(index_df) >= 20:
            return self._detect_from_data(index_df)

        return self._detect_from_approximation()

    def _detect_from_data(self, df: pd.DataFrame) -> RegimeResult:
        close = df["close"].values if "close" in df.columns else np.array([])
        if len(close) < 20:
            return RegimeResult(label=REGIME_LABELS.get(REGIME_SIDEWAYS, ""))

        ma5 = self._sma(close, 5)
        ma20 = self._sma(close, 20)

        ret_5d = (close[-1] - close[-6]) / close[-6] * 100 if len(close) >= 6 else 0
        ret_20d = (close[-1] - close[-21]) / close[-21] * 100 if len(close) >= 21 else 0

        volatility = 0.0
        if len(close) >= 10:
            daily_returns = np.diff(close[-11:]) / close[-11:-1] * 100
            volatility = float(np.std(daily_returns))

        indicators: Dict[str, Any] = {
            "return_5d": round(ret_5d, 2),
            "return_20d": round(ret_20d, 2),
            "volatility": round(volatility, 2),
        }

        if not np.isnan(ma5[-1]) and not np.isnan(ma20[-1]):
            ma_alignment = "bullish" if ma5[-1] > ma20[-1] else "bearish"
            indicators["ma_alignment"] = ma_alignment
        else:
            ma_alignment = "neutral"

        if volatility > 2.0:
            regime = REGIME_VOLATILE
            confidence = min(volatility / 3.0, 0.9)
        elif ma_alignment == "bullish" and ret_20d > 5:
            regime = REGIME_TRENDING_UP
            confidence = min(abs(ret_20d) / 10.0, 0.9)
        elif ma_alignment == "bearish" and ret_20d < -5:
            regime = REGIME_TRENDING_DOWN
            confidence = min(abs(ret_20d) / 10.0, 0.9)
        elif abs(ret_20d) < 5:
            regime = REGIME_SIDEWAYS
            confidence = 0.6
        else:
            regime = REGIME_SIDEWAYS
            confidence = 0.4

        return RegimeResult(
            regime=regime,
            confidence=round(confidence, 2),
            indicators=indicators,
            label=REGIME_LABELS.get(regime, ""),
        )

    def _detect_from_approximation(self) -> RegimeResult:
        try:
            import akshare as ak
            df = ak.stock_zh_index_daily(symbol="sh000300")
            if df is not None and len(df) >= 30:
                df = df.tail(30).copy()
                if "close" not in df.columns and "收盘" in df.columns:
                    df = df.rename(columns={"收盘": "close"})
                return self._detect_from_data(df)
        except Exception as e:
            logger.debug("[RegimeDetector] akshare index fetch failed: %s", e)

        try:
            from datetime import date, timedelta
            end = date.today()
            start = end - timedelta(days=60)
            from data_provider.factory import DataProviderFactory
            factory = DataProviderFactory()
            hist = factory.get_daily_history("000300", start_date=start, end_date=end)
            if hist is not None and len(hist) >= 20:
                return self._detect_from_data(hist.tail(30))
        except Exception as e:
            logger.debug("[RegimeDetector] data_provider index fetch failed: %s", e)

        logger.info("[RegimeDetector] 无法获取指数数据，默认横盘震荡")
        return RegimeResult(
            regime=REGIME_SIDEWAYS,
            confidence=0.3,
            label=REGIME_LABELS.get(REGIME_SIDEWAYS, ""),
        )

    @staticmethod
    def _sma(arr: np.ndarray, window: int) -> np.ndarray:
        if len(arr) < window:
            return np.full_like(arr, np.nan, dtype=float)
        return pd.Series(arr).rolling(window=window).mean().values


class DynamicWeightAdjuster:
    """Adjust strategy weights based on detected market regime."""

    def __init__(
        self,
        base_weights: Optional[Dict[str, float]] = None,
        strategy_regime_map: Optional[Dict[str, List[str]]] = None,
    ):
        self.base_weights = base_weights or STRATEGY_BASE_WEIGHTS
        self.strategy_regime_map = strategy_regime_map or STRATEGY_REGIME_MAP

    def adjust(
        self,
        regime: str,
        strategy_signals: List[Any],
    ) -> Dict[str, float]:
        effective: Dict[str, float] = {}

        for sig in strategy_signals:
            name = sig.strategy_name
            base = self.base_weights.get(name, 0.5)
            applicable_regimes = self.strategy_regime_map.get(name, [])

            if not applicable_regimes or regime in applicable_regimes:
                multiplier = REGIME_BOOST
            else:
                multiplier = REGIME_DAMPEN

            if not sig.triggered:
                multiplier *= 0.3

            effective[name] = round(base * multiplier, 3)

        return effective

    def compute_fusion_score(
        self,
        strategy_signals: List[Any],
        effective_weights: Dict[str, float],
        base_factor_score: float = 0.0,
        base_factor_weight: float = 0.4,
    ) -> tuple:
        strategy_weight_total = 0.0
        weighted_score = 0.0
        category_scores: Dict[str, List[tuple]] = {}

        for sig in strategy_signals:
            w = effective_weights.get(sig.strategy_name, 0.0)
            if w <= 0:
                continue

            weighted_score += sig.score * w
            strategy_weight_total += w

            cat = sig.category
            if cat not in category_scores:
                category_scores[cat] = []
            category_scores[cat].append((sig.score, w, sig.strategy_name))

        strategy_fusion = 0.0
        if strategy_weight_total > 0:
            strategy_fusion = weighted_score / strategy_weight_total

        final_score = base_factor_score * base_factor_weight + strategy_fusion * (1 - base_factor_weight)
        final_score = max(0.0, min(100.0, final_score))

        category_breakdown: Dict[str, Any] = {}
        for cat, items in category_scores.items():
            total_w = sum(w for _, w, _ in items)
            avg = sum(s * w for s, w, _ in items) / total_w if total_w > 0 else 0
            cat_weight = CATEGORY_WEIGHTS.get(cat, 0.1)
            top = sorted(items, key=lambda x: x[0], reverse=True)[:3]
            category_breakdown[cat] = {
                "avg_score": round(avg, 1),
                "weight": cat_weight,
                "top_strategies": [
                    {"name": n, "score": round(s, 1), "weight": round(w, 3)}
                    for s, w, n in top
                ],
            }

        return final_score, strategy_fusion, category_breakdown
