# -*- coding: utf-8 -*-
"""辅助函数库 (FR-015/016/020)."""

from __future__ import annotations

from typing import Any, Callable, Generator, Optional

import numpy as np
import pandas as pd


def crossover(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """检测 a 上穿 b.

    Returns:
        bool 数组，True 表示当日上穿
    """
    a, b = np.asarray(a), np.asarray(b)
    result = np.zeros(len(a), dtype=bool)
    if len(a) < 2:
        return result
    result[1:] = (a[1:] > b[1:]) & (a[:-1] <= b[:-1])
    return result


def crossunder(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """检测 a 下穿 b."""
    a, b = np.asarray(a), np.asarray(b)
    result = np.zeros(len(a), dtype=bool)
    if len(a) < 2:
        return result
    result[1:] = (a[1:] < b[1:]) & (a[:-1] >= b[:-1])
    return result


def SMA(arr: np.ndarray, n: int) -> np.ndarray:
    """简单移动平均线."""
    arr = np.asarray(arr, dtype=float)
    result = np.full(len(arr), np.nan)
    if n <= 0 or n > len(arr):
        return result
    cumsum = np.cumsum(np.insert(arr, 0, 0))
    result[n - 1:] = (cumsum[n:] - cumsum[:-n]) / n
    return result


def EMA(arr: np.ndarray, n: int, alpha: Optional[float] = None) -> np.ndarray:
    """指数移动平均线."""
    arr = np.asarray(arr, dtype=float)
    result = np.full(len(arr), np.nan)
    if n <= 0 or n > len(arr):
        return result
    a = alpha if alpha is not None else 2.0 / (n + 1)
    result[0] = arr[0]
    for i in range(1, len(arr)):
        result[i] = a * arr[i] + (1 - a) * result[i - 1]
    return result


def RSI(arr: np.ndarray, n: int = 14) -> np.ndarray:
    """相对强弱指标."""
    arr = np.asarray(arr, dtype=float)
    result = np.full(len(arr), np.nan)
    if n <= 0 or len(arr) < n + 1:
        return result
    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[:n])
    avg_loss = np.mean(losses[:n])
    if avg_loss == 0:
        result[n] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[n] = 100.0 - (100.0 / (1.0 + rs))
    for i in range(n + 1, len(arr)):
        avg_gain = (avg_gain * (n - 1) + gains[i - 1]) / n
        avg_loss = (avg_loss * (n - 1) + losses[i - 1]) / n
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))
    return result


def MACD(arr: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MACD 指标.

    Returns:
        (MACD线, 信号线, 柱状图)
    """
    arr = np.asarray(arr, dtype=float)
    ema_fast = EMA(arr, fast)
    ema_slow = EMA(arr, slow)
    macd_line = ema_fast - ema_slow
    signal_line = EMA(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def ATR(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> np.ndarray:
    """平均真实波幅."""
    high, low, close = np.asarray(high, dtype=float), np.asarray(low, dtype=float), np.asarray(close, dtype=float)
    result = np.full(len(high), np.nan)
    if n <= 0 or len(high) < 2:
        return result
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1]),
        ),
    )
    result[n] = np.mean(tr[:n])
    for i in range(n + 1, len(high)):
        result[i] = (result[i - 1] * (n - 1) + tr[i - 1]) / n
    return result


def resample_apply(
    rule: str,
    func: Callable,
    series: pd.Series,
    *args: Any,
    agg: Optional[Callable] = None,
    **kwargs: Any,
) -> np.ndarray:
    """将指标函数应用到重采样后的时间框架 (FR-020).

    Args:
        rule: Pandas 频率字符串 ('D', 'W', 'ME' 等)
        func: 指标函数
        series: 价格序列 (带 DatetimeIndex)
        agg: 聚合函数 (默认取 Close)
    """
    series = series.copy() if hasattr(series, "copy") else pd.Series(series)
    if not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError("series must have DatetimeIndex")
    if agg is None:
        def _agg(x):
            return x.iloc[-1] if len(x) > 0 else np.nan
        agg = _agg
    resampled = series.resample(rule).apply(agg)
    indicator = func(resampled.values, *args, **kwargs)
    indicator_series = pd.Series(indicator, index=resampled.index)
    result = indicator_series.reindex(series.index, method="ffill")
    return result.values


def random_ohlc_data(
    example_data: pd.DataFrame,
    frac: float = 1.0,
    random_state: Optional[int] = None,
) -> Generator[pd.DataFrame, None, None]:
    """生成具有相似统计特征的随机 OHLC 数据 (FR-016).

    蒙特卡洛模拟的随机数据生成器.
    """
    rng = np.random.RandomState(random_state)
    n = int(len(example_data) * frac)
    returns = example_data["Close"].pct_change().dropna()
    mu = returns.mean()
    sigma = returns.std()

    base_price = example_data["Close"].iloc[0]
    for _ in range(1):
        random_returns = rng.normal(mu, sigma, n)
        random_prices = base_price * np.exp(np.cumsum(random_returns))

        df = pd.DataFrame(index=pd.RangeIndex(n))
        df["Close"] = random_prices
        df["Open"] = df["Close"] * (1 + rng.normal(0, sigma * 0.5, n))
        high_low_spread = np.abs(rng.normal(sigma, sigma * 0.3, n))
        df["High"] = np.maximum(df["Open"], df["Close"]) + high_low_spread * df["Close"]
        df["Low"] = np.minimum(df["Open"], df["Close"]) - high_low_spread * df["Close"]
        df["Volume"] = example_data["Volume"].sample(n=n, replace=True, random_state=rng.randint(0, 2**31)).values

        yield df
