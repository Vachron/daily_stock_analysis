# -*- coding: utf-8 -*-
"""Alpha scorer — cross-section alpha prediction from parameterized strategy factors.

Uses fast scoring mode (no LLM) by translating YAML strategy conditions into
vectorized pandas operations on daily OHLCV data.

Args:
    strategies: list of StrategyTemplate with current factor values
    pool_codes: candidate stock codes to score
    date: target trading date

Returns:
    List of AlphaPrediction, each containing:
    - code, name: stock identifier
    - alpha_score: Z-score normalized alpha (mean~0, std~1)
    - factor_scores: per-strategy raw scores before normalization
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.alpha.factor_model import FactorModel, StrategyTemplate

logger = logging.getLogger(__name__)


@dataclass
class AlphaPrediction:
    code: str
    name: str = ""
    alpha_score: float = 0.0
    raw_score: float = 0.0
    factor_scores: Dict[str, float] = field(default_factory=dict)


class AlphaScorer:
    SCORE_METHODS: Dict[str, Callable] = {}

    def __init__(self, pool_codes: Optional[List[str]] = None):
        self.pool_codes = pool_codes or []

    def score_cross_section(
        self,
        target_date: date,
        strategies: List[StrategyTemplate],
        factor_values: Optional[Dict[str, Dict[str, float]]] = None,
        history_provider: Optional[Callable] = None,
        name_map: Optional[Dict[str, str]] = None,
        market_data: Optional[pd.DataFrame] = None,
    ) -> List[AlphaPrediction]:
        if history_provider is None and market_data is None:
            raise ValueError("history_provider or market_data must be provided")

        all_values = factor_values or {}
        history_cache: Dict[str, pd.DataFrame] = {}
        predictions: List[AlphaPrediction] = []

        codes = self.pool_codes
        if market_data is not None and "code" in market_data.columns:
            codes = market_data["code"].unique().tolist()

        for code in codes:
            name = (name_map or {}).get(code, "")
            hdf = None

            if history_provider is not None:
                try:
                    hdf = history_provider(code, target_date)
                except Exception:
                    pass

            if hdf is None and market_data is not None:
                mask = market_data["code"] == code
                hdf = market_data[mask].copy()

            if hdf is None or hdf.empty:
                continue

            raw_score = 0.0
            factor_scores: Dict[str, float] = {}

            for strategy in strategies:
                vals = all_values.get(strategy.name, {})
                s_score = self._score_strategy(strategy, vals, hdf, target_date)
                factor_scores[strategy.name] = s_score
                raw_score += s_score * strategy.weight

            predictions.append(AlphaPrediction(
                code=code,
                name=name,
                raw_score=raw_score,
                factor_scores=factor_scores,
            ))

        if predictions:
            raw_scores = np.array([p.raw_score for p in predictions], dtype=float)
            raw_mean = np.mean(raw_scores)
            raw_std = np.std(raw_scores) or 1.0
            for p in predictions:
                p.alpha_score = float((p.raw_score - raw_mean) / raw_std)

        predictions.sort(key=lambda x: x.alpha_score, reverse=True)
        return predictions

    def _score_strategy(
        self,
        strategy: StrategyTemplate,
        factor_values: Dict[str, float],
        df: pd.DataFrame,
        target_date: date,
    ) -> float:
        if not strategy.factors:
            return 0.0

        vals = FactorModel.clamp_values(strategy, factor_values)
        score: float = 0.0
        category = strategy.category
        name = strategy.name

        try:
            if category == "reversal" and name == "bottom_volume":
                score += self._score_bottom_volume(df, vals)
            elif category == "trend" and name == "bull_trend":
                score += self._score_bull_trend(df, vals)
            elif category == "framework" and name == "emotion_cycle":
                score += self._score_emotion_cycle(df, vals)
            elif name == "momentum_reversal":
                score += self._score_momentum_reversal(df, vals)
            elif name == "ma_golden_cross":
                score += self._score_ma_golden_cross(df, vals)
            else:
                score += self._score_generic(df, vals, strategy)
        except Exception as e:
            logger.debug("Scoring error for %s: %s", strategy.name, e)

        return score

    # --- Strategy-specific scoring functions ---

    def _score_bottom_volume(self, df: pd.DataFrame, vals: Dict[str, float]) -> float:
        days = min(30, len(df))
        if days < 10:
            return 0.0
        recent = df.tail(days).copy()
        close = recent["close"].values
        volume = recent["volume"].values
        high_20d = recent["high"].tail(20).max()
        recent_low = recent["low"].tail(20).min()
        decline_pct = (high_20d - recent_low) / high_20d if high_20d > 0 else 0
        vol_5d_avg = np.mean(volume[-6:-1]) if len(volume) >= 6 else np.mean(volume[:-1]) if len(volume) > 1 else volume[-1]
        vol_ratio = volume[-1] / vol_5d_avg if vol_5d_avg > 0 else 1.0

        threshold = vals.get("decline_threshold", 0.15)
        vol_threshold = vals.get("volume_ratio_threshold", 3.0)
        score_base = vals.get("score_base", 8.0)
        score_bonus = vals.get("score_catalyst_bonus", 5.0)

        sc = 0.0
        if decline_pct >= threshold:
            sc += score_base * 0.5
        if vol_ratio >= vol_threshold:
            sc += score_base * 0.5
        if len(close) >= 2 and close[-1] > close[-2]:
            sc += score_bonus * 0.3

        return sc

    def _score_bull_trend(self, df: pd.DataFrame, vals: Dict[str, float]) -> float:
        days = min(60, len(df))
        if days < 20:
            return 0.0
        recent = df.tail(days).copy()
        close = recent["close"].values
        ma5 = np.mean(close[-5:])
        ma10 = np.mean(close[-10:])
        ma20 = np.mean(close[-20:])
        ma20_prev = np.mean(close[-21:-1]) if len(close) >= 21 else ma20

        trend_score = vals.get("trend_score", 12.0)
        pullback_score = vals.get("pullback_score", 8.0)
        breakout_score = vals.get("breakout_score", 10.0)
        breakdown_penalty = vals.get("breakdown_penalty", 12.0)

        sc = 0.0
        is_bull = ma5 >= ma10 >= ma20
        ma20_rising = ma20 > ma20_prev

        if is_bull and ma20_rising:
            sc += trend_score
        elif is_bull:
            sc += trend_score * 0.5

        if close[-1] >= ma20 * 0.98 and close[-1] <= ma5 * 1.02:
            sc += pullback_score * 0.5

        if close[-1] < ma20:
            sc -= breakdown_penalty * 0.5

        if days >= 20:
            vol_recent = recent["volume"].tail(5).mean()
            vol_prev = recent["volume"].iloc[-10:-5].mean() if len(recent) >= 10 else vol_recent
            if vol_recent > vol_prev * 1.2 and close[-1] > close[-2]:
                sc += breakout_score * 0.3

        return sc

    def _score_emotion_cycle(self, df: pd.DataFrame, vals: Dict[str, float]) -> float:
        days = min(60, len(df))
        if days < 10:
            return 0.0
        recent = df.tail(days).copy()
        close = recent["close"].values
        volume = recent["volume"].values
        turnover = recent.get("turnover", recent.get("turnover_rate"))
        if turnover is None:
            turnover_cols = ["turnover", "turnover_rate", "turn"]
            for col in turnover_cols:
                if col in recent.columns:
                    turnover = recent[col].values
                    break
        if turnover is None:
            turnover = np.full_like(volume, np.nan)

        cold_score = vals.get("cold_score", 10.0)
        hot_warn = vals.get("hot_warn_score", -8.0)
        mean_rev_score = vals.get("mean_reversion_score", 7.0)
        vol_dry_score = vals.get("volume_dry_score", 5.0)
        sentiment_extreme = vals.get("sentiment_extreme_score", 6.0)

        sc = 0.0
        vol_60d_avg = np.mean(volume) if len(volume) > 0 else volume[-1]
        vol_ratio = volume[-1] / vol_60d_avg if vol_60d_avg > 0 else 1.0

        if len(turnover) > 0 and not np.isnan(turnover[-1]):
            t_curr = float(turnover[-1])
            if t_curr < 0.5:
                sc += cold_score * 0.5
            elif t_curr > 5.0:
                sc += hot_warn * 0.5

        if vol_ratio < 0.5:
            sc += vol_dry_score * 0.5

        if days >= 20:
            ma20_val = np.mean(close[-20:])
            dev_pct = (close[-1] - ma20_val) / ma20_val if ma20_val > 0 else 0
            if abs(dev_pct) < 0.05:
                sc += mean_rev_score * 0.3
            if abs(dev_pct) > 0.08:
                sc += sentiment_extreme * (0.5 if dev_pct > 0 else 0.3)

        return sc

    def _score_momentum_reversal(self, df: pd.DataFrame, vals: Dict[str, float]) -> float:
        days = min(60, len(df))
        if days < 20:
            return 0.0
        recent = df.tail(days).copy()
        close = recent["close"].values

        momentum_window = int(vals.get("momentum_window", 20))
        reversal_window = int(vals.get("reversal_window", 60))
        momentum_score = vals.get("momentum_score", 10.0)
        reversal_score = vals.get("reversal_score", 8.0)

        sc = 0.0
        if len(close) >= momentum_window:
            mom_ret = (close[-1] - close[-momentum_window]) / close[-momentum_window] if close[-momentum_window] > 0 else 0
            if mom_ret > 0.05:
                sc += momentum_score * min(mom_ret / 0.1, 1.0)

        if len(close) >= reversal_window:
            rev_ret = (close[-1] - close[-reversal_window]) / close[-reversal_window] if close[-reversal_window] > 0 else 0
            if rev_ret < -0.2:
                vol_recent = recent["volume"].tail(5).mean()
                vol_all = recent["volume"].mean()
                if vol_recent > vol_all * 1.3:
                    sc += reversal_score * 0.5

        return sc

    def _score_ma_golden_cross(self, df: pd.DataFrame, vals: Dict[str, float]) -> float:
        days = min(120, len(df))
        if days < 60:
            return 0.0
        recent = df.tail(days).copy()
        close = recent["close"].values

        short_win = int(vals.get("short_window", 5))
        mid_win = int(vals.get("mid_window", 20))
        long_win = int(vals.get("long_window", 60))
        golden_cross_score = vals.get("golden_cross_score", 12.0)
        death_cross_penalty = vals.get("death_cross_penalty", -10.0)
        vol_confirm_score = vals.get("vol_confirm_score", 5.0)

        sc = 0.0
        if len(close) >= long_win + 1:
            ma_short_curr = np.mean(close[-short_win:])
            ma_short_prev = np.mean(close[-short_win-1:-1])
            ma_mid_curr = np.mean(close[-mid_win:])
            ma_mid_prev = np.mean(close[-mid_win-1:-1])
            ma_long = np.mean(close[-long_win:])

            golden = ma_short_prev <= ma_mid_prev and ma_short_curr > ma_mid_curr
            death = ma_short_prev >= ma_mid_prev and ma_short_curr < ma_mid_curr

            if golden:
                sc += golden_cross_score
                if ma_mid_curr > ma_long:
                    sc += vol_confirm_score * 0.5
            elif death:
                sc += death_cross_penalty * 0.5

        return sc

    def _score_generic(self, df: pd.DataFrame, vals: Dict[str, float], _strategy: StrategyTemplate) -> float:
        sc = 0.0
        for fid, fval in vals.items():
            sc += fval * 0.1
        return sc


def make_default_history_provider():
    from data_provider.base import get_provider

    provider = get_provider()

    def _fetch(code: str, target_date: date) -> Optional[pd.DataFrame]:
        try:
            start = target_date - timedelta(days=180)
            df = provider.get_daily_history(
                code=code,
                start_date=start.strftime("%Y-%m-%d"),
                end_date=target_date.strftime("%Y-%m-%d"),
            )
            return df
        except Exception:
            return None

    return _fetch
