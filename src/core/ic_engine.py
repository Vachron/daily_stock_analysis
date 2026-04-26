# -*- coding: utf-8 -*-
"""
IC Calculation Engine — Rank IC, IC decay, factor orthogonality.

Core metrics:
- Rank IC: Spearman rank correlation between factor values and forward returns
- IC decay: How IC decays as forward period increases (1d, 3d, 5d, 10d, 20d)
- Orthogonality matrix: Pairwise Rank IC between factors (low = independent)

Design principles:
- All IC calculations use HFQ-adjusted data to avoid look-ahead bias
- Forward returns are computed on non-adjusted close for backtest consistency
- Minimum sample size enforced (default 30 stocks per cross-section)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

_MIN_CROSS_SECTION = 30
_FORWARD_PERIODS = [1, 3, 5, 10, 20]


@dataclass
class ICResult:
    factor_name: str
    period: int
    rank_ic: float
    rank_ic_pvalue: float
    sample_count: int
    positive_ratio: float = 0.0

    @property
    def is_significant(self) -> bool:
        return self.rank_ic_pvalue < 0.05

    @property
    def is_effective(self) -> bool:
        return abs(self.rank_ic) >= 0.03 and self.is_significant


@dataclass
class ICDaySeries:
    factor_name: str
    period: int
    ic_values: List[float] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)

    @property
    def mean_ic(self) -> float:
        if not self.ic_values:
            return 0.0
        return float(np.mean(self.ic_values))

    @property
    def std_ic(self) -> float:
        if len(self.ic_values) < 2:
            return 0.0
        return float(np.std(self.ic_values, ddof=1))

    @property
    def icir(self) -> float:
        if self.std_ic == 0:
            return 0.0
        return self.mean_ic / self.std_ic

    @property
    def positive_ratio(self) -> float:
        if not self.ic_values:
            return 0.0
        return sum(1 for v in self.ic_values if v > 0) / len(self.ic_values)

    @property
    def t_stat(self) -> float:
        n = len(self.ic_values)
        if n < 2 or self.std_ic == 0:
            return 0.0
        return self.mean_ic / (self.std_ic / np.sqrt(n))


@dataclass
class ICSummary:
    factor_name: str
    period: int
    mean_ic: float
    std_ic: float
    icir: float
    t_stat: float
    positive_ratio: float
    sample_days: int
    is_effective: bool


@dataclass
class OrthogonalityMatrix:
    factor_names: List[str]
    matrix: pd.DataFrame

    def get_redundant_pairs(self, threshold: float = 0.6) -> List[Tuple[str, str, float]]:
        pairs = []
        n = len(self.factor_names)
        for i in range(n):
            for j in range(i + 1, n):
                val = abs(self.matrix.iloc[i, j])
                if val > threshold:
                    pairs.append((self.factor_names[i], self.factor_names[j], val))
        pairs.sort(key=lambda x: x[2], reverse=True)
        return pairs


def _spearman_rank_ic(
    factor_values: np.ndarray,
    forward_returns: np.ndarray,
) -> Tuple[float, float]:
    mask = ~(np.isnan(factor_values) | np.isnan(forward_returns) | np.isinf(factor_values) | np.isinf(forward_returns))
    clean_f = factor_values[mask]
    clean_r = forward_returns[mask]
    if len(clean_f) < _MIN_CROSS_SECTION:
        return 0.0, 1.0
    corr, pval = stats.spearmanr(clean_f, clean_r)
    if np.isnan(corr):
        return 0.0, 1.0
    return float(corr), float(pval)


def compute_cross_section_ic(
    factor_values: pd.Series,
    forward_returns: pd.Series,
    factor_name: str = "",
    period: int = 1,
) -> ICResult:
    ic, pval = _spearman_rank_ic(factor_values.values, forward_returns.values)
    n = len(factor_values.dropna())
    pos_ratio = float((forward_returns > 0).sum() / len(forward_returns)) if len(forward_returns) > 0 else 0.0
    return ICResult(
        factor_name=factor_name,
        period=period,
        rank_ic=ic,
        rank_ic_pvalue=pval,
        sample_count=n,
        positive_ratio=pos_ratio,
    )


def compute_ic_decay(
    factor_df: pd.DataFrame,
    return_df: pd.DataFrame,
    factor_name: str,
    periods: Optional[List[int]] = None,
) -> List[ICResult]:
    if periods is None:
        periods = _FORWARD_PERIODS
    results = []
    for p in periods:
        if factor_name not in factor_df.columns:
            continue
        factor_vals = factor_df[factor_name]
        ret_col = f"fwd_ret_{p}d"
        if ret_col not in return_df.columns:
            continue
        ret_vals = return_df[ret_col]
        common_idx = factor_vals.dropna().index.intersection(ret_vals.dropna().index)
        if len(common_idx) < _MIN_CROSS_SECTION:
            continue
        ic_result = compute_cross_section_ic(
            factor_vals.loc[common_idx],
            ret_vals.loc[common_idx],
            factor_name=factor_name,
            period=p,
        )
        results.append(ic_result)
    return results


def compute_time_series_ic(
    factor_panel: Dict[str, pd.DataFrame],
    return_panel: Dict[str, pd.DataFrame],
    factor_name: str,
    period: int = 1,
) -> ICDaySeries:
    series = ICDaySeries(factor_name=factor_name, period=period)
    ret_col = f"fwd_ret_{period}d"

    sorted_dates = sorted(factor_panel.keys())
    for date_str in sorted_dates:
        f_df = factor_panel.get(date_str)
        r_df = return_panel.get(date_str)
        if f_df is None or r_df is None:
            continue
        if factor_name not in f_df.columns or ret_col not in r_df.columns:
            continue
        common = f_df.index.intersection(r_df.index)
        if len(common) < _MIN_CROSS_SECTION:
            continue
        ic, _ = _spearman_rank_ic(
            f_df.loc[common, factor_name].values,
            r_df.loc[common, ret_col].values,
        )
        series.ic_values.append(ic)
        series.dates.append(date_str)

    return series


def compute_ic_summary(series: ICDaySeries) -> ICSummary:
    effective = abs(series.mean_ic) >= 0.03 and series.t_stat > 2.0
    return ICSummary(
        factor_name=series.factor_name,
        period=series.period,
        mean_ic=series.mean_ic,
        std_ic=series.std_ic,
        icir=series.icir,
        t_stat=series.t_stat,
        positive_ratio=series.positive_ratio,
        sample_days=len(series.ic_values),
        is_effective=effective,
    )


def compute_orthogonality_matrix(
    factor_df: pd.DataFrame,
    factor_names: Optional[List[str]] = None,
) -> OrthogonalityMatrix:
    if factor_names is None:
        factor_names = list(factor_df.columns)
    valid = [f for f in factor_names if f in factor_df.columns]
    if not valid:
        return OrthogonalityMatrix(factor_names=[], matrix=pd.DataFrame())
    sub = factor_df[valid].dropna()
    if len(sub) < _MIN_CROSS_SECTION:
        return OrthogonalityMatrix(factor_names=valid, matrix=pd.DataFrame(index=valid, columns=valid, data=0.0))
    corr_matrix = sub.corr(method="spearman")
    return OrthogonalityMatrix(factor_names=valid, matrix=corr_matrix)


class FactorExtractor:
    """Extract factor values from OHLCV DataFrame for IC computation."""

    @staticmethod
    def extract_all(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or len(df) < 30:
            return pd.DataFrame()
        close = df["close"].values.astype(float)
        open_ = df["open"].values.astype(float)
        high = df["high"].values.astype(float)
        low = df["low"].values.astype(float)
        volume = df["volume"].values.astype(float) if "volume" in df.columns else np.ones(len(df))
        factors = {}
        factors["momentum_5d"] = FactorExtractor._momentum(close, 5)
        factors["momentum_10d"] = FactorExtractor._momentum(close, 10)
        factors["momentum_20d"] = FactorExtractor._momentum(close, 20)
        factors["volatility_10d"] = FactorExtractor._volatility(close, 10)
        factors["volatility_20d"] = FactorExtractor._volatility(close, 20)
        factors["turnover_rate_5d"] = FactorExtractor._avg_turnover(volume, close, 5)
        factors["turnover_rate_10d"] = FactorExtractor._avg_turnover(volume, close, 10)
        factors["rsi_14"] = FactorExtractor._rsi(close, 14)
        factors["bias_ma5"] = FactorExtractor._bias(close, 5)
        factors["bias_ma20"] = FactorExtractor._bias(close, 20)
        factors["volume_ratio_5d"] = FactorExtractor._volume_ratio(volume, 5)
        factors["volume_ratio_10d"] = FactorExtractor._volume_ratio(volume, 10)
        factors["amplitude_10d"] = FactorExtractor._amplitude(high, low, close, 10)
        factors["price_position_20d"] = FactorExtractor._price_position(close, high, low, 20)
        factors["body_ratio"] = FactorExtractor._body_ratio(close, open_, high, low)
        factors["upper_shadow_ratio"] = FactorExtractor._shadow_ratio(close, open_, high, low, upper=True)
        factors["lower_shadow_ratio"] = FactorExtractor._shadow_ratio(close, open_, high, low, upper=False)
        factors["alpha101_001"] = FactorExtractor._alpha101_001(close, open_, high, low)
        factors["alpha101_006"] = FactorExtractor._alpha101_006(close, open_, high, low, volume)
        factors["alpha101_012"] = FactorExtractor._alpha101_012(close, open_, high, low, volume)
        factors["alpha101_041"] = FactorExtractor._alpha101_041(close, high, low, volume)
        factors["alpha101_053"] = FactorExtractor._alpha101_053(close, low, high)
        result = pd.DataFrame(factors, index=df.index)
        return result

    @staticmethod
    def _momentum(close: np.ndarray, window: int) -> np.ndarray:
        if len(close) < window + 1:
            return np.full(len(close), np.nan)
        ret = np.full(len(close), np.nan)
        denom = close[:-window]
        ret[window:] = np.where(denom > 0, (close[window:] - denom) / denom, np.nan)
        return ret

    @staticmethod
    def _volatility(close: np.ndarray, window: int) -> np.ndarray:
        if len(close) < window + 1:
            return np.full(len(close), np.nan)
        ret = np.full(len(close), np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            log_ret = np.diff(np.log(close))
        log_ret = np.where(np.isfinite(log_ret), log_ret, 0.0)
        for i in range(window, len(close)):
            ret[i] = np.std(log_ret[i - window:i], ddof=1)
        return ret

    @staticmethod
    def _avg_turnover(volume: np.ndarray, close: np.ndarray, window: int) -> np.ndarray:
        if len(volume) < window:
            return np.full(len(volume), np.nan)
        ret = np.full(len(volume), np.nan)
        for i in range(window - 1, len(volume)):
            ret[i] = np.mean(volume[i - window + 1:i + 1])
        return ret

    @staticmethod
    def _rsi(close: np.ndarray, period: int) -> np.ndarray:
        if len(close) < period + 1:
            return np.full(len(close), np.nan)
        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avg_gain = np.mean(gain[:period])
        avg_loss = np.mean(loss[:period])
        rsi_arr = np.full(len(close), np.nan)
        if avg_loss == 0:
            rsi_arr[period] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_arr[period] = 100.0 - (100.0 / (1.0 + rs))
        alpha = 1.0 / period
        for i in range(period, len(delta)):
            avg_gain = avg_gain * (1 - alpha) + gain[i] * alpha
            avg_loss = avg_loss * (1 - alpha) + loss[i] * alpha
            if avg_loss == 0:
                rsi_arr[i + 1] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi_arr[i + 1] = 100.0 - (100.0 / (1.0 + rs))
        return rsi_arr

    @staticmethod
    def _bias(close: np.ndarray, window: int) -> np.ndarray:
        if len(close) < window:
            return np.full(len(close), np.nan)
        ma = pd.Series(close).rolling(window=window).mean().values
        return np.where(ma > 0, (close - ma) / ma, np.nan)

    @staticmethod
    def _volume_ratio(volume: np.ndarray, window: int) -> np.ndarray:
        if len(volume) < window * 2:
            return np.full(len(volume), np.nan)
        ret = np.full(len(volume), np.nan)
        for i in range(window, len(volume)):
            recent = np.mean(volume[i - window + 1:i + 1])
            prev = np.mean(volume[i - 2 * window + 1:i - window + 1])
            ret[i] = recent / prev if prev > 0 else np.nan
        return ret

    @staticmethod
    def _amplitude(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int) -> np.ndarray:
        if len(close) < window:
            return np.full(len(close), np.nan)
        ret = np.full(len(close), np.nan)
        for i in range(window - 1, len(close)):
            h = np.max(high[i - window + 1:i + 1])
            l = np.min(low[i - window + 1:i + 1])
            c_prev = close[i - window] if i >= window else close[0]
            ret[i] = (h - l) / c_prev if c_prev > 0 else np.nan
        return ret

    @staticmethod
    def _price_position(close: np.ndarray, high: np.ndarray, low: np.ndarray, window: int) -> np.ndarray:
        if len(close) < window:
            return np.full(len(close), np.nan)
        ret = np.full(len(close), np.nan)
        for i in range(window - 1, len(close)):
            h = np.max(high[i - window + 1:i + 1])
            l = np.min(low[i - window + 1:i + 1])
            ret[i] = (close[i] - l) / (h - l) if h != l else 0.5
        return ret

    @staticmethod
    def _body_ratio(close: np.ndarray, open_: np.ndarray, high: np.ndarray, low: np.ndarray) -> np.ndarray:
        body = np.abs(close - open_)
        full_range = high - low
        return np.where(full_range > 0, body / full_range, 0.5)

    @staticmethod
    def _shadow_ratio(close: np.ndarray, open_: np.ndarray, high: np.ndarray, low: np.ndarray,
                      upper: bool = True) -> np.ndarray:
        body_top = np.maximum(close, open_)
        body_bot = np.minimum(close, open_)
        full_range = high - low
        if upper:
            shadow = high - body_top
        else:
            shadow = body_bot - low
        return np.where(full_range > 0, shadow / full_range, 0.0)

    @staticmethod
    def _alpha101_001(close: np.ndarray, open_: np.ndarray, high: np.ndarray, low: np.ndarray) -> np.ndarray:
        inner = high - low
        denom = close - open_
        result = np.where(
            (inner > 0) & (denom != 0),
            inner / denom,
            0.0,
        )
        result = np.where(np.isinf(result), 0.0, result)
        if len(result) >= 6:
            ma6 = pd.Series(result).rolling(6).mean().values
            return ma6
        return result

    @staticmethod
    def _alpha101_006(close: np.ndarray, open_: np.ndarray, high: np.ndarray, low: np.ndarray,
                      volume: np.ndarray) -> np.ndarray:
        if len(close) < 6:
            return np.full(len(close), np.nan)
        co = close - open_
        sign_co = np.sign(co)
        vol_signed = volume * sign_co
        ret = np.full(len(close), np.nan)
        for i in range(5, len(close)):
            ret[i] = -np.sum(vol_signed[i - 5:i + 1])
        return ret

    @staticmethod
    def _alpha101_012(close: np.ndarray, open_: np.ndarray, high: np.ndarray, low: np.ndarray,
                      volume: np.ndarray) -> np.ndarray:
        if len(close) < 11:
            return np.full(len(close), np.nan)
        ret = np.full(len(close), np.nan)
        for i in range(10, len(close)):
            sign_delta = np.sign(close[i] - close[i - 1])
            ret[i] = -np.sum(sign_delta * volume[i - 10:i + 1])
        return ret

    @staticmethod
    def _alpha101_041(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                      volume: np.ndarray) -> np.ndarray:
        if len(close) < 10:
            return np.full(len(close), np.nan)
        ret = np.full(len(close), np.nan)
        for i in range(9, len(close)):
            v_mean = np.mean(volume[i - 9:i + 1])
            h_max = np.max(high[i - 9:i + 1])
            l_min = np.min(low[i - 9:i + 1])
            if v_mean > 0 and (h_max - l_min) > 0:
                ret[i] = -((close[i] - l_min) / (h_max - l_min)) * v_mean
        return ret

    @staticmethod
    def _alpha101_053(close: np.ndarray, low: np.ndarray, high: np.ndarray) -> np.ndarray:
        if len(close) < 13:
            return np.full(len(close), np.nan)
        ret = np.full(len(close), np.nan)
        for i in range(12, len(close)):
            x = close[i] - np.min(low[i - 12:i + 1])
            y = np.max(high[i - 12:i + 1]) - np.min(low[i - 12:i + 1])
            ret[i] = -x / y if y > 0 else 0.0
        return ret


def compute_forward_returns(
    df: pd.DataFrame,
    periods: Optional[List[int]] = None,
) -> pd.DataFrame:
    if periods is None:
        periods = _FORWARD_PERIODS
    close = df["close"].values.astype(float)
    result = {}
    for p in periods:
        fwd = np.full(len(close), np.nan)
        for i in range(len(close) - p):
            if close[i] > 0 and np.isfinite(close[i]) and np.isfinite(close[i + p]):
                fwd[i] = (close[i + p] - close[i]) / close[i]
        result[f"fwd_ret_{p}d"] = fwd
    return pd.DataFrame(result, index=df.index)


class ICEngine:
    """Full IC analysis pipeline for a basket of stocks."""

    def __init__(self, min_cross_section: int = _MIN_CROSS_SECTION):
        self.min_cross_section = min_cross_section

    def run_cross_section(
        self,
        stock_data: Dict[str, pd.DataFrame],
        date_index: int = -1,
        periods: Optional[List[int]] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if periods is None:
            periods = _FORWARD_PERIODS
        factor_rows = {}
        return_rows = {}
        for code, df in stock_data.items():
            if df is None or len(df) < 30:
                continue
            if date_index >= len(df) or abs(date_index) > len(df):
                continue
            factors = FactorExtractor.extract_all(df)
            fwd_rets = compute_forward_returns(df, periods=periods)
            idx = date_index
            if idx < 0:
                idx = len(df) + idx
            if idx < 0 or idx >= len(factors):
                continue
            factor_rows[code] = factors.iloc[idx]
            return_rows[code] = fwd_rets.iloc[idx]

        factor_df = pd.DataFrame(factor_rows).T
        return_df = pd.DataFrame(return_rows).T
        return factor_df, return_df

    def run_time_series(
        self,
        stock_data: Dict[str, pd.DataFrame],
        factor_name: str,
        period: int = 1,
        lookback: int = 60,
    ) -> ICDaySeries:
        factor_panel: Dict[str, pd.DataFrame] = {}
        return_panel: Dict[str, pd.DataFrame] = {}

        all_dates = set()
        for code, df in stock_data.items():
            if df is None or len(df) < 30:
                continue
            if "date" in df.columns:
                for d in df["date"].values[-lookback:]:
                    all_dates.add(str(d))

        for date_str in sorted(all_dates):
            f_rows = {}
            r_rows = {}
            for code, df in stock_data.items():
                if df is None or len(df) < 30:
                    continue
                if "date" not in df.columns:
                    continue
                mask = df["date"].astype(str) == date_str
                if not mask.any():
                    continue
                idx = mask.idxmax()
                factors = FactorExtractor.extract_all(df)
                fwd_rets = compute_forward_returns(df, periods=[period])
                if idx < len(factors) and idx < len(fwd_rets):
                    f_rows[code] = factors.iloc[idx]
                    r_rows[code] = fwd_rets.iloc[idx]

            if len(f_rows) >= self.min_cross_section:
                factor_panel[date_str] = pd.DataFrame(f_rows).T
                return_panel[date_str] = pd.DataFrame(r_rows).T

        return compute_time_series_ic(factor_panel, return_panel, factor_name, period)

    def run_full_analysis(
        self,
        stock_data: Dict[str, pd.DataFrame],
        factor_names: Optional[List[str]] = None,
        period: int = 5,
        lookback: int = 60,
    ) -> Dict[str, Any]:
        if factor_names is None:
            sample_df = next((df for df in stock_data.values() if df is not None and len(df) >= 30), None)
            if sample_df is not None:
                sample_factors = FactorExtractor.extract_all(sample_df)
                factor_names = list(sample_factors.columns)
            else:
                factor_names = []

        summaries = {}
        ic_decay_results = {}
        for fn in factor_names:
            series = self.run_time_series(stock_data, fn, period=period, lookback=lookback)
            if series.ic_values:
                summaries[fn] = compute_ic_summary(series)

            decay = []
            for p in _FORWARD_PERIODS:
                s = self.run_time_series(stock_data, fn, period=p, lookback=lookback)
                if s.ic_values:
                    decay.append({
                        "period": p,
                        "mean_ic": s.mean_ic,
                        "icir": s.icir,
                    })
            if decay:
                ic_decay_results[fn] = decay

        factor_df, return_df = self.run_cross_section(stock_data, date_index=-1)
        ortho = compute_orthogonality_matrix(factor_df, factor_names)

        return {
            "summaries": summaries,
            "ic_decay": ic_decay_results,
            "orthogonality": ortho,
            "effective_factors": [fn for fn, s in summaries.items() if s.is_effective],
        }
