# -*- coding: utf-8 -*-
"""Strategy signal extractor — compute per-strategy signal scores from market data.

Each strategy yields a signal score (0-100) and a triggered flag.
Signal scores are computed from quantifiable technical indicators;
strategies requiring special conditions (e.g. sector_hot) use conditional
triggering with reduced weight when conditions are absent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class StrategySignal:
    strategy_name: str
    display_name: str
    category: str
    score: float = 0.0
    triggered: bool = False
    weight: float = 1.0
    effective_weight: float = 1.0
    details: Dict[str, Any] = field(default_factory=dict)


class StrategySignalExtractor:
    """Extract strategy signals from OHLCV data for a single stock."""

    def __init__(self, market_regime: str = "sideways"):
        self.market_regime = market_regime

    def extract_all(
        self,
        df: pd.DataFrame,
        realtime: Optional[Dict[str, Any]] = None,
    ) -> List[StrategySignal]:
        if df is None or len(df) < 20:
            return []

        signals: List[StrategySignal] = []

        signals.append(self._bull_trend(df, realtime))
        signals.append(self._ma_golden_cross(df, realtime))
        signals.append(self._multi_golden_cross(df, realtime))
        signals.append(self._macd_divergence(df, realtime))
        signals.append(self._rsi_reversal(df, realtime))
        signals.append(self._bollinger_reversion(df, realtime))
        signals.append(self._shrink_pullback(df, realtime))
        signals.append(self._volume_breakout(df, realtime))
        signals.append(self._limit_up_pullback(df, realtime))
        signals.append(self._morning_star(df, realtime))
        signals.append(self._w_bottom(df, realtime))
        signals.append(self._bottom_volume(df, realtime))
        signals.append(self._turtle_trading(df, realtime))
        signals.append(self._box_oscillation(df, realtime))
        signals.append(self._momentum_reversal(df, realtime))
        signals.append(self._dragon_head(df, realtime))
        signals.append(self._chan_theory(df, realtime))
        signals.append(self._wave_theory(df, realtime))
        signals.append(self._emotion_cycle(df, realtime))
        signals.append(self._one_yang_three_yin(df, realtime))
        signals.append(self._risk_filter(df, realtime))
        signals.append(self._volume_price_divergence(df, realtime))
        signals.append(self._volume_surge_reversal(df, realtime))
        signals.append(self._alpha101_001_signal(df, realtime))
        signals.append(self._alpha101_006_signal(df, realtime))
        signals.append(self._alpha101_053_signal(df, realtime))

        return signals

    def _safe_close(self, df: pd.DataFrame) -> np.ndarray:
        return df["close"].values if "close" in df.columns else np.array([])

    def _safe_volume(self, df: pd.DataFrame) -> np.ndarray:
        return df["volume"].values if "volume" in df.columns else np.array([])

    def _safe_high(self, df: pd.DataFrame) -> np.ndarray:
        return df["high"].values if "high" in df.columns else np.array([])

    def _safe_low(self, df: pd.DataFrame) -> np.ndarray:
        return df["low"].values if "low" in df.columns else np.array([])

    def _safe_open(self, df: pd.DataFrame) -> np.ndarray:
        return df["open"].values if "open" in df.columns else np.array([])

    def _calc_ema(self, series: np.ndarray, span: int) -> np.ndarray:
        if len(series) < span:
            return np.full_like(series, np.nan, dtype=float)
        s = pd.Series(series)
        return s.ewm(span=span, adjust=False).mean().values

    def _calc_sma(self, series: np.ndarray, window: int) -> np.ndarray:
        if len(series) < window:
            return np.full_like(series, np.nan, dtype=float)
        return pd.Series(series).rolling(window=window).mean().values

    def _calc_rsi(self, series: np.ndarray, period: int = 14) -> float:
        if len(series) < period + 1:
            return 50.0
        delta = np.diff(series)
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        if len(gain) < period:
            return 50.0
        avg_gain = float(np.mean(gain[:period]))
        avg_loss = float(np.mean(loss[:period]))
        if avg_loss == 0 and avg_gain == 0:
            return 50.0
        if avg_loss == 0:
            return 100.0
        if len(gain) > period:
            alpha = 1.0 / period
            seeded_gain = pd.Series(np.concatenate([[avg_gain], gain[period:]]))
            seeded_loss = pd.Series(np.concatenate([[avg_loss], loss[period:]]))
            avg_gain = float(seeded_gain.ewm(alpha=alpha, adjust=False).mean().iloc[-1])
            avg_loss = float(seeded_loss.ewm(alpha=alpha, adjust=False).mean().iloc[-1])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _calc_macd(self, close: np.ndarray) -> tuple:
        if len(close) < 35:
            return 0.0, 0.0, 0.0
        ema12 = self._calc_ema(close, 12)
        ema26 = self._calc_ema(close, 26)
        dif = ema12 - ema26
        dea = self._calc_ema(dif[~np.isnan(dif)], 9)
        bar = (dif[-1] - dea[-1]) * 2 if not np.isnan(dea[-1]) else 0.0
        return float(dif[-1]) if not np.isnan(dif[-1]) else 0.0, \
               float(dea[-1]) if not np.isnan(dea[-1]) else 0.0, \
               float(bar)

    def _calc_bollinger(self, close: np.ndarray, period: int = 20) -> tuple:
        if len(close) < period:
            return 0.0, 0.0, 0.0
        window = close[-period:]
        mid = float(np.mean(window))
        std = float(np.std(window))
        upper = mid + 2 * std
        lower = mid - 2 * std
        return upper, mid, lower

    def _bull_trend(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        if len(close) < 60:
            return StrategySignal("bull_trend", "多头趋势", "trend", 0, False)

        ma5 = self._calc_sma(close, 5)
        ma10 = self._calc_sma(close, 10)
        ma20 = self._calc_sma(close, 20)
        ma60 = self._calc_sma(close, 60)

        cur = close[-1]
        m5, m10, m20, m60 = ma5[-1], ma10[-1], ma20[-1], ma60[-1]

        if np.isnan(m60):
            return StrategySignal("bull_trend", "多头趋势", "trend", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        if m5 > m10 > m20:
            score += 40
            details["ma_alignment"] = "bullish_short"
            triggered = True
        if m10 > m20 > m60:
            score += 30
            details["ma_alignment"] = "bullish_full"
        if cur > m5:
            score += 15
            details["above_ma5"] = True

        if score >= 40:
            triggered = True

        return StrategySignal("bull_trend", "多头趋势", "trend", min(score, 100), triggered, details=details)

    def _ma_golden_cross(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        if len(close) < 30:
            return StrategySignal("ma_golden_cross", "均线金叉", "trend", 0, False)

        ma5 = self._calc_sma(close, 5)
        ma10 = self._calc_sma(close, 10)
        ma20 = self._calc_sma(close, 20)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        if len(ma5) >= 2 and len(ma10) >= 2:
            prev_diff = ma5[-2] - ma10[-2]
            curr_diff = ma5[-1] - ma10[-1]
            if prev_diff <= 0 and curr_diff > 0 and not np.isnan(curr_diff):
                score = 80
                triggered = True
                details["cross"] = "ma5_ma10_golden"

        if len(ma10) >= 2 and len(ma20) >= 2:
            prev_diff = ma10[-2] - ma20[-2]
            curr_diff = ma10[-1] - ma20[-1]
            if prev_diff <= 0 and curr_diff > 0 and not np.isnan(curr_diff):
                score = min(score + 50, 100)
                triggered = True
                details["cross"] = details.get("cross", "") + "+ma10_ma20_golden"

        return StrategySignal("ma_golden_cross", "均线金叉", "trend", score, triggered, details=details)

    def _multi_golden_cross(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        if len(close) < 60:
            return StrategySignal("multi_golden_cross", "多线金叉", "trend", 0, False)

        ma5 = self._calc_sma(close, 5)
        ma10 = self._calc_sma(close, 10)
        ma20 = self._calc_sma(close, 20)
        ma60 = self._calc_sma(close, 60)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        crosses = 0
        for ma_a, ma_b, label in [(ma5, ma10, "5/10"), (ma10, ma20, "10/20"), (ma20, ma60, "20/60")]:
            if len(ma_a) >= 2 and len(ma_b) >= 2:
                prev = ma_a[-2] - ma_b[-2]
                curr = ma_a[-1] - ma_b[-1]
                if prev <= 0 and curr > 0 and not np.isnan(curr):
                    crosses += 1
                    details[f"cross_{label}"] = True

        if crosses >= 3:
            score = 100
            triggered = True
        elif crosses == 2:
            score = 70
            triggered = True
        elif crosses == 1:
            score = 40
            triggered = True

        return StrategySignal("multi_golden_cross", "多线金叉", "trend", score, triggered, details=details)

    def _macd_divergence(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        if len(close) < 35:
            return StrategySignal("macd_divergence", "MACD背离", "reversal", 0, False)

        dif, dea, bar = self._calc_macd(close)
        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        if dif > dea and bar > 0:
            details["macd_status"] = "bullish"
        if dif > 0 and dea > 0:
            details["above_zero"] = True

        if len(close) >= 40:
            dif_arr = self._calc_ema(close, 12) - self._calc_ema(close, 26)
            dif_valid = dif_arr[~np.isnan(dif_arr)]
            if len(dif_valid) >= 20:
                recent_close = close[-20:]
                recent_dif = dif_valid[-20:]
                close_mins = []
                dif_mins = []
                for i in range(1, len(recent_close) - 1):
                    if recent_close[i] < recent_close[i - 1] and recent_close[i] < recent_close[i + 1]:
                        close_mins.append((i, recent_close[i], recent_dif[i] if i < len(recent_dif) else 0))
                if len(close_mins) >= 2:
                    lo1, lo2 = close_mins[-2], close_mins[-1]
                    if lo1[1] > lo2[1] and lo1[2] < lo2[2]:
                        score += 50
                        triggered = True
                        details["divergence"] = "bullish_bottom"
                    elif lo1[1] < lo2[1] and lo1[2] > lo2[2]:
                        score += 40
                        triggered = True
                        details["divergence"] = "bearish_top"

        if score >= 40:
            triggered = True

        return StrategySignal("macd_divergence", "MACD背离", "reversal", min(score, 100), triggered, details=details)

    def _rsi_reversal(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        if len(close) < 25:
            return StrategySignal("rsi_reversal", "RSI超买超卖", "reversal", 0, False)

        rsi6 = self._calc_rsi(close, 6)
        rsi12 = self._calc_rsi(close, 12)
        rsi24 = self._calc_rsi(close, 24) if len(close) >= 25 else 50.0

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {"rsi6": round(rsi6, 1), "rsi12": round(rsi12, 1), "rsi24": round(rsi24, 1)}

        if rsi12 < 30:
            score = 80
            triggered = True
            details["signal"] = "oversold"
        elif rsi12 < 40:
            score = 50
            triggered = True
            details["signal"] = "weak"
        elif rsi12 > 70:
            details["signal"] = "overbought_caution"

        if rsi6 < 30 and rsi12 < 40:
            score = min(score + 20, 100)
            triggered = True
            details["multi_oversold"] = True

        return StrategySignal("rsi_reversal", "RSI超买超卖", "reversal", score, triggered, details=details)

    def _bollinger_reversion(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        if len(close) < 20:
            return StrategySignal("bollinger_reversion", "布林回归", "reversal", 0, False)

        upper, mid, lower = self._calc_bollinger(close, 20)
        if mid == 0:
            return StrategySignal("bollinger_reversion", "布林回归", "reversal", 0, False)

        cur = close[-1]
        score = 0.0
        triggered = False
        details: Dict[str, Any] = {"upper": round(upper, 2), "mid": round(mid, 2), "lower": round(lower, 2)}

        if cur <= lower:
            score = 80
            triggered = True
            details["signal"] = "below_lower_band"
        elif cur <= lower + (mid - lower) * 0.3:
            score = 60
            triggered = True
            details["signal"] = "near_lower_band"
        elif cur >= upper:
            details["signal"] = "above_upper_band"
        elif cur >= upper - (upper - mid) * 0.3:
            details["signal"] = "near_upper_band"

        return StrategySignal("bollinger_reversion", "布林回归", "reversal", score, triggered, details=details)

    def _shrink_pullback(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        vol = self._safe_volume(df)
        if len(close) < 10 or len(vol) < 10:
            return StrategySignal("shrink_pullback", "缩量回踩", "trend", 0, False)

        ma5 = self._calc_sma(close, 5)
        ma10 = self._calc_sma(close, 10)
        ma20 = self._calc_sma(close, 20)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        cur = close[-1]
        avg_vol_5 = float(np.mean(vol[-6:-1])) if len(vol) >= 6 else 1
        today_vol = float(vol[-1])
        vol_ratio = today_vol / avg_vol_5 if avg_vol_5 > 0 else 1.0
        details["vol_ratio"] = round(vol_ratio, 2)

        if vol_ratio < 0.7:
            score += 25
            details["shrink"] = True

        if not np.isnan(ma5[-1]) and not np.isnan(ma10[-1]):
            if abs(cur - ma5[-1]) / ma5[-1] < 0.02:
                score += 30
                details["touch_ma5"] = True
            elif abs(cur - ma10[-1]) / ma10[-1] < 0.02:
                score += 25
                details["touch_ma10"] = True

        if len(ma5) >= 2 and not np.isnan(ma5[-1]) and not np.isnan(ma10[-1]):
            if ma5[-1] > ma10[-1]:
                score += 10
                details["uptrend"] = True

        if score >= 50:
            triggered = True

        return StrategySignal("shrink_pullback", "缩量回踩", "trend", min(score, 100), triggered, details=details)

    def _volume_breakout(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        vol = self._safe_volume(df)
        if len(close) < 20 or len(vol) < 20:
            return StrategySignal("volume_breakout", "放量突破", "trend", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        avg_vol_5 = float(np.mean(vol[-6:-1])) if len(vol) >= 6 else 1
        today_vol = float(vol[-1])
        vol_ratio = today_vol / avg_vol_5 if avg_vol_5 > 0 else 1.0
        details["vol_ratio"] = round(vol_ratio, 2)

        high_20 = float(np.max(close[-21:-1])) if len(close) >= 21 else 0
        cur = close[-1]
        details["high_20d"] = round(high_20, 2)

        if vol_ratio >= 1.5:
            score += 20
            details["volume_surge"] = True

        if cur > high_20 and high_20 > 0:
            score += 50
            triggered = True
            details["breakout_20d"] = True

        if vol_ratio >= 1.5 and cur > high_20 and high_20 > 0:
            score = min(score + 10, 100)
            details["volume_breakout_confirmed"] = True

        if score >= 50:
            triggered = True

        return StrategySignal("volume_breakout", "放量突破", "trend", min(score, 100), triggered, details=details)

    def _limit_up_pullback(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        if len(close) < 10:
            return StrategySignal("limit_up_pullback", "涨停回踩", "trend", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        pct_changes = np.diff(close) / close[:-1] * 100

        limit_up_found = False
        for i in range(max(0, len(pct_changes) - 5), len(pct_changes)):
            threshold = self._limit_up_threshold(close, i)
            if pct_changes[i] >= threshold:
                limit_up_found = True
                details["limit_up_day"] = i - len(pct_changes)
                details["limit_up_threshold"] = threshold
                break

        if limit_up_found:
            cur = close[-1]
            ma5 = self._calc_sma(close, 5)
            if not np.isnan(ma5[-1]):
                pullback_pct = (cur - ma5[-1]) / ma5[-1] * 100
                if -3 <= pullback_pct <= 2:
                    score = 70
                    triggered = True
                    details["pullback_to_ma5"] = True
                elif pullback_pct < -3:
                    details["deep_pullback"] = True
                else:
                    details["above_ma5"] = True

        return StrategySignal("limit_up_pullback", "涨停回踩", "trend", score, triggered, details=details)

    def _morning_star(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        open_ = self._safe_open(df)
        if len(close) < 5:
            return StrategySignal("morning_star", "早晨之星", "pattern", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        n = len(close)
        if n >= 3:
            c, o = close[-3:], open_[-3:]
            body = [abs(c[i] - o[i]) for i in range(3)]
            avg_body = float(np.mean([abs(close[i] - open_[i]) for i in range(max(0, n - 10), n)]))

            if (c[0] < o[0] and body[0] > avg_body * 1.2
                    and body[1] < avg_body * 0.4
                    and c[2] > o[2] and body[2] > avg_body * 1.2
                    and c[2] > (o[0] + c[0]) / 2):
                score = 85
                triggered = True
                details["pattern"] = "morning_star"

        return StrategySignal("morning_star", "早晨之星", "pattern", score, triggered, details=details)

    def _w_bottom(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        low = self._safe_low(df)
        if len(close) < 20:
            return StrategySignal("w_bottom", "W底形态", "reversal", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        lookback = min(20, len(low))
        recent_low = low[-lookback:]
        recent_close = close[-lookback:]
        mins = []
        for i in range(1, len(recent_low) - 1):
            if recent_low[i] < recent_low[i - 1] and recent_low[i] < recent_low[i + 1]:
                mins.append((i, recent_low[i]))

        if len(mins) >= 2:
            lo1, lo2 = mins[-2], mins[-1]
            if lo2[0] - lo1[0] >= 5:
                similarity = abs(lo1[1] - lo2[1]) / max(lo1[1], lo2[1])
                if similarity < 0.03:
                    score = 80
                    triggered = True
                    details["pattern"] = "double_bottom"
                    details["similarity"] = round(similarity * 100, 2)
                elif similarity < 0.05:
                    score = 55
                    triggered = True
                    details["pattern"] = "approx_double_bottom"

        return StrategySignal("w_bottom", "W底形态", "reversal", score, triggered, details=details)

    def _bottom_volume(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        vol = self._safe_volume(df)
        if len(close) < 20 or len(vol) < 20:
            return StrategySignal("bottom_volume", "底部放量", "reversal", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        avg_vol_20 = float(np.mean(vol[-21:-1]))
        today_vol = float(vol[-1])
        vol_ratio = today_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0
        details["vol_ratio"] = round(vol_ratio, 2)

        low_20 = float(np.min(close[-21:-1]))
        cur = close[-1]
        price_position = (cur - low_20) / (float(np.max(close[-21:-1])) - low_20) if low_20 > 0 else 0.5
        details["price_position"] = round(price_position, 2)

        if vol_ratio >= 2.0 and price_position < 0.3:
            score = 80
            triggered = True
            details["signal"] = "bottom_volume_surge"
        elif vol_ratio >= 1.5 and price_position < 0.4:
            score = 55
            triggered = True
            details["signal"] = "near_bottom_volume"

        return StrategySignal("bottom_volume", "底部放量", "reversal", score, triggered, details=details)

    def _turtle_trading(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        if len(close) < 25:
            return StrategySignal("turtle_trading", "海龟交易", "framework", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        high_20 = float(np.max(close[-21:-1]))
        low_20 = float(np.min(close[-21:-1]))
        cur = close[-1]
        atr_approx = high_20 - low_20
        details["high_20"] = round(high_20, 2)
        details["low_20"] = round(low_20, 2)

        if cur > high_20:
            score = 75
            triggered = True
            details["signal"] = "breakout_long"
        elif cur < low_20:
            details["signal"] = "breakdown_short"

        return StrategySignal("turtle_trading", "海龟交易", "framework", score, triggered, details=details)

    def _box_oscillation(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        high = self._safe_high(df)
        low = self._safe_low(df)
        if len(close) < 15:
            return StrategySignal("box_oscillation", "箱体震荡", "framework", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        recent_high = float(np.max(high[-11:]))
        recent_low = float(np.min(low[-11:]))
        box_range = (recent_high - recent_low) / recent_low * 100 if recent_low > 0 else 100
        details["box_range_pct"] = round(box_range, 2)

        if box_range < 8:
            ma5 = self._calc_sma(close, 5)
            ma20 = self._calc_sma(close, 20)
            if len(ma5) >= 2 and len(ma20) >= 2 and not np.isnan(ma5[-1]) and not np.isnan(ma20[-1]):
                ma5_slope = (ma5[-1] - ma5[-5]) / ma5[-5] * 100 if len(ma5) >= 5 and ma5[-5] != 0 else 0
                ma20_slope = (ma20[-1] - ma20[-10]) / ma20[-10] * 100 if len(ma20) >= 10 and ma20[-10] != 0 else 0
                if abs(ma5_slope) > 2 or abs(ma20_slope) > 3:
                    details["signal"] = "trending_not_box"
                    return StrategySignal("box_oscillation", "箱体震荡", "framework", 0, False)

            score = 60
            triggered = True
            details["signal"] = "in_box"
            cur = close[-1]
            position = (cur - recent_low) / (recent_high - recent_low) if recent_high != recent_low else 0.5
            if position < 0.3:
                score = 75
                details["box_position"] = "near_bottom"
            elif position > 0.7:
                score = 15
                details["box_position"] = "near_top"
            else:
                score = 40
                details["box_position"] = "mid_box"
        else:
            details["signal"] = "not_box"

        return StrategySignal("box_oscillation", "箱体震荡", "framework", score, triggered, details=details)

    def _momentum_reversal(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        vol = self._safe_volume(df)
        if len(close) < 15:
            return StrategySignal("momentum_reversal", "动量反转", "trend", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        ret_5d = (close[-1] - close[-6]) / close[-6] * 100 if len(close) >= 6 else 0
        ret_10d = (close[-1] - close[-11]) / close[-11] * 100 if len(close) >= 11 else 0
        details["return_5d"] = round(ret_5d, 2)
        details["return_10d"] = round(ret_10d, 2)

        if ret_5d < -5 and ret_10d < -8:
            score = 70
            triggered = True
            details["signal"] = "oversold_reversal"
        elif ret_5d > 5 and ret_10d > 8:
            details["signal"] = "overbought_reversal_risk"

        return StrategySignal("momentum_reversal", "动量反转", "trend", score, triggered, details=details)

    def _dragon_head(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        vol = self._safe_volume(df)
        if len(close) < 5:
            return StrategySignal("dragon_head", "龙头策略", "trend", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        if rt:
            turnover = rt.get("turnover_rate", 0)
            if turnover > 5:
                score += 30
                details["high_turnover"] = True
            pct_chg = rt.get("pct_chg", 0)
            if 0 < pct_chg < 9.5:
                score += 20
                details["active_not_limit"] = True

        if len(vol) >= 6:
            avg_vol = float(np.mean(vol[-6:-1]))
            today_vol = float(vol[-1])
            if avg_vol > 0 and today_vol / avg_vol > 1.5:
                score += 25
                details["volume_surge"] = True

        is_sector_hot = self.market_regime == "sector_hot"
        if is_sector_hot and score > 0:
            triggered = True
            score = min(score + 20, 100)
            details["sector_hot_boost"] = True

        return StrategySignal("dragon_head", "龙头策略", "trend", score, triggered, details=details)

    def _chan_theory(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        high = self._safe_high(df)
        low = self._safe_low(df)
        if len(close) < 30:
            return StrategySignal("chan_theory", "缠论", "framework", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        pivot_highs = []
        pivot_lows = []
        for i in range(2, len(close) - 2):
            if high[i] > high[i - 1] and high[i] > high[i + 1] and high[i] > high[i - 2] and high[i] > high[i + 2]:
                pivot_highs.append((i, high[i]))
            if low[i] < low[i - 1] and low[i] < low[i + 1] and low[i] < low[i - 2] and low[i] < low[i + 2]:
                pivot_lows.append((i, low[i]))

        if len(pivot_highs) >= 2 and len(pivot_lows) >= 2:
            if pivot_highs[-1][1] > pivot_highs[-2][1] and pivot_lows[-1][1] > pivot_lows[-2][1]:
                score = 65
                triggered = True
                details["signal"] = "uptrend_pivots"
            elif pivot_highs[-1][1] < pivot_highs[-2][1] and pivot_lows[-1][1] < pivot_lows[-2][1]:
                details["signal"] = "downtrend_pivots"
            else:
                details["signal"] = "consolidation_pivots"

        return StrategySignal("chan_theory", "缠论", "framework", score, triggered, details=details)

    def _wave_theory(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        high = self._safe_high(df)
        low = self._safe_low(df)
        if len(close) < 30:
            return StrategySignal("wave_theory", "波浪理论", "framework", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        ma5 = self._calc_sma(close, 5)
        ma20 = self._calc_sma(close, 20)
        if np.isnan(ma5[-1]) or np.isnan(ma20[-1]):
            return StrategySignal("wave_theory", "波浪理论", "framework", 0, False)

        cur = close[-1]
        trend_up = ma5[-1] > ma20[-1]

        if trend_up:
            recent_low = float(np.min(low[-20:]))
            recent_high = float(np.max(high[-5:]))
            if recent_low > 0:
                wave_progress = (cur - recent_low) / (recent_high - recent_low) if recent_high != recent_low else 0.5
                details["wave_progress"] = round(wave_progress, 2)
                if wave_progress < 0.38:
                    score = 70
                    triggered = True
                    details["signal"] = "wave3_early"

        return StrategySignal("wave_theory", "波浪理论", "framework", score, triggered, details=details)

    def _emotion_cycle(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        vol = self._safe_volume(df)
        if len(close) < 15:
            return StrategySignal("emotion_cycle", "情绪周期", "framework", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        ret_5d = (close[-1] - close[-6]) / close[-6] * 100 if len(close) >= 6 else 0
        rsi = self._calc_rsi(close, 14)

        if len(vol) >= 6:
            avg_vol = float(np.mean(vol[-6:-1]))
            today_vol = float(vol[-1])
            vol_ratio = today_vol / avg_vol if avg_vol > 0 else 1.0
        else:
            vol_ratio = 1.0

        details["rsi"] = round(rsi, 1)
        details["vol_ratio"] = round(vol_ratio, 2)
        details["return_5d"] = round(ret_5d, 2)

        if rsi < 35 and ret_5d < -3:
            score = 70
            triggered = True
            details["signal"] = "fear_phase"
        elif rsi > 65 and ret_5d > 5:
            details["signal"] = "greed_phase"

        return StrategySignal("emotion_cycle", "情绪周期", "framework", score, triggered, details=details)

    def _one_yang_three_yin(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        open_ = self._safe_open(df)
        if len(close) < 5:
            return StrategySignal("one_yang_three_yin", "一阳三阴", "pattern", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        n = len(close)
        if n >= 4:
            last4_c = close[-4:]
            last4_o = open_[-4:]

            bullish_first = last4_o[0] < last4_c[0]
            bearish_rest = all(last4_o[i] > last4_c[i] for i in range(1, 4))
            within_range = last4_c[3] >= last4_o[0]

            if bullish_first and bearish_rest and within_range:
                score = 65
                triggered = True
                details["pattern"] = "one_yang_three_yin_bullish"

        return StrategySignal("one_yang_three_yin", "一阳三阴", "pattern", score, triggered, details=details)

    def _risk_filter(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        if len(close) < 5:
            return StrategySignal("risk_filter", "风险过滤", "framework", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        ret_5d = (close[-1] - close[-6]) / close[-6] * 100 if len(close) >= 6 else 0
        if ret_5d > 15:
            score -= 30
            triggered = True
            details["chase_risk"] = True
        elif ret_5d > 10:
            score -= 15
            triggered = True
            details["high_momentum_risk"] = True

        rsi = self._calc_rsi(close, 14)
        if rsi > 80:
            score -= 20
            triggered = True
            details["extreme_overbought"] = True
        elif rsi > 70:
            score -= 10
            triggered = True
            details["overbought"] = True

        ma5 = self._calc_sma(close, 5)
        if not np.isnan(ma5[-1]):
            bias = (close[-1] - ma5[-1]) / ma5[-1] * 100
            if bias > 5:
                score -= 25
                triggered = True
                details["high_bias_risk"] = True
                details["bias_ma5"] = round(bias, 2)
            elif bias > 3:
                score -= 10
                triggered = True
                details["moderate_bias"] = True

        score = max(score, 0)

        if score <= 0:
            triggered = False

        return StrategySignal("risk_filter", "风险过滤", "framework", score, triggered, details=details)

    def _volume_price_divergence(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        vol = self._safe_volume(df)
        if len(close) < 20 or len(vol) < 20:
            return StrategySignal("volume_price_divergence", "量价背离", "volume_price", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        if len(close) >= 10:
            recent_close = close[-10:]
            recent_vol = vol[-10:]
            price_trend = np.polyfit(np.arange(len(recent_close)), recent_close, 1)[0]
            vol_trend = np.polyfit(np.arange(len(recent_vol)), recent_vol, 1)[0]

            price_direction = 1 if price_trend > 0 else -1
            vol_direction = 1 if vol_trend > 0 else -1

            if price_direction != vol_direction:
                if price_direction > 0 and vol_direction < 0:
                    score = 65
                    triggered = True
                    details["divergence"] = "price_up_vol_down"
                    details["signal"] = "bearish_divergence"
                elif price_direction < 0 and vol_direction > 0:
                    score = 70
                    triggered = True
                    details["divergence"] = "price_down_vol_up"
                    details["signal"] = "bullish_accumulation"

        if len(close) >= 5:
            price_chg_5d = (close[-1] - close[-5]) / close[-5] * 100 if close[-5] > 0 else 0
            vol_avg_5d = np.mean(vol[-5:])
            vol_avg_prev = np.mean(vol[-10:-5]) if len(vol) >= 10 else vol_avg_5d
            vol_chg = (vol_avg_5d - vol_avg_prev) / vol_avg_prev * 100 if vol_avg_prev > 0 else 0

            if price_chg_5d > 3 and vol_chg < -20:
                score = min(score + 15, 100)
                details["price_up_vol_shrink"] = True
            elif price_chg_5d < -3 and vol_chg > 30:
                score = min(score + 15, 100)
                details["price_down_vol_surge"] = True

        return StrategySignal("volume_price_divergence", "量价背离", "volume_price",
                              min(score, 100), triggered, details=details)

    def _volume_surge_reversal(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        vol = self._safe_volume(df)
        if len(close) < 20 or len(vol) < 20:
            return StrategySignal("volume_surge_reversal", "放量反转", "volume_price", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        avg_vol_20 = float(np.mean(vol[-21:-1])) if len(vol) >= 21 else 1.0
        today_vol = float(vol[-1])
        vol_ratio = today_vol / avg_vol_20 if avg_vol_20 > 0 else 1.0
        details["vol_ratio"] = round(vol_ratio, 2)

        open_ = self._safe_open(df)
        if len(open_) > 0 and len(close) > 0:
            body = close[-1] - open_[-1]
            body_pct = body / open_[-1] * 100 if open_[-1] > 0 else 0

            if vol_ratio >= 2.0:
                if body_pct > 2.0:
                    score = 75
                    triggered = True
                    details["signal"] = "volume_surge_bullish"
                    details["body_pct"] = round(body_pct, 2)
                elif body_pct < -2.0:
                    score = 20
                    details["signal"] = "volume_surge_bearish"
                    details["body_pct"] = round(body_pct, 2)
                else:
                    score = 40
                    triggered = True
                    details["signal"] = "volume_surge_indecision"

            if len(close) >= 5:
                ret_5d = (close[-1] - close[-5]) / close[-5] * 100 if close[-5] > 0 else 0
                if ret_5d < -8 and vol_ratio >= 2.0 and body_pct > 1.0:
                    score = min(score + 20, 100)
                    triggered = True
                    details["oversold_volume_reversal"] = True

        return StrategySignal("volume_surge_reversal", "放量反转", "volume_price",
                              min(score, 100), triggered, details=details)

    def _alpha101_001_signal(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        open_ = self._safe_open(df)
        high = self._safe_high(df)
        low = self._safe_low(df)
        if len(close) < 10:
            return StrategySignal("alpha101_001", "Alpha#1", "alpha101", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        inner = high - low
        denom = close - open_
        with np.errstate(divide='ignore', invalid='ignore'):
            raw = np.where(
                (inner > 0) & (denom != 0),
                inner / denom,
                0.0,
            )
        raw = np.where(np.isinf(raw), 0.0, raw)
        raw = np.nan_to_num(raw, nan=0.0)

        if len(raw) >= 6:
            ma6 = np.convolve(raw[-6:], np.ones(6) / 6, mode='valid')[-1]
            details["alpha001_ma6"] = round(float(ma6), 4)

            if ma6 < -1.5:
                score = 70
                triggered = True
                details["signal"] = "alpha001_bullish"
            elif ma6 > 1.5:
                score = 25
                details["signal"] = "alpha001_bearish"
            else:
                score = 40
                details["signal"] = "alpha001_neutral"

        return StrategySignal("alpha101_001", "Alpha#1", "alpha101",
                              min(score, 100), triggered, details=details)

    def _alpha101_006_signal(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        open_ = self._safe_open(df)
        vol = self._safe_volume(df)
        if len(close) < 10:
            return StrategySignal("alpha101_006", "Alpha#6", "alpha101", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        co = close - open_
        sign_co = np.sign(co)
        vol_signed = vol * sign_co

        if len(vol_signed) >= 6:
            recent_sum = -np.sum(vol_signed[-6:])
            avg_vol = np.mean(vol[-6:]) if np.mean(vol[-6:]) > 0 else 1.0
            normalized = recent_sum / avg_vol
            details["alpha006_normalized"] = round(float(normalized), 4)

            if normalized > 2.0:
                score = 65
                triggered = True
                details["signal"] = "alpha006_bullish"
            elif normalized < -2.0:
                score = 25
                details["signal"] = "alpha006_bearish"
            else:
                score = 40
                details["signal"] = "alpha006_neutral"

        return StrategySignal("alpha101_006", "Alpha#6", "alpha101",
                              min(score, 100), triggered, details=details)

    def _alpha101_053_signal(self, df: pd.DataFrame, rt: Optional[Dict]) -> StrategySignal:
        close = self._safe_close(df)
        low = self._safe_low(df)
        high = self._safe_high(df)
        if len(close) < 15:
            return StrategySignal("alpha101_053", "Alpha#53", "alpha101", 0, False)

        score = 0.0
        triggered = False
        details: Dict[str, Any] = {}

        window = min(13, len(close) - 1)
        x = close[-1] - np.min(low[-window:])
        y = np.max(high[-window:]) - np.min(low[-window:])
        alpha_val = -x / y if y > 0 else 0.0
        details["alpha053_value"] = round(float(alpha_val), 4)

        if alpha_val < -0.7:
            score = 70
            triggered = True
            details["signal"] = "alpha053_near_high"
        elif alpha_val > -0.3:
            score = 25
            details["signal"] = "alpha053_near_low"
        else:
            score = 45
            details["signal"] = "alpha053_mid"

        return StrategySignal("alpha101_053", "Alpha#53", "alpha101",
                              min(score, 100), triggered, details=details)

    @staticmethod
    def _limit_up_threshold(close: np.ndarray, bar_index: int) -> float:
        if len(close) < 3:
            return 9.5
        pct_changes = np.abs(np.diff(close) / close[:-1] * 100)
        max_observed = float(np.max(pct_changes)) if len(pct_changes) > 0 else 0
        if max_observed > 25:
            return 29.5
        if max_observed > 15:
            return 19.5
        return 9.5
