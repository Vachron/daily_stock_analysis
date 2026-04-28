# -*- coding: utf-8 -*-
"""Benchmark data fetcher — retrieve index daily history for alpha evaluation.

Supports: CSI 300 (000300), CSI 500 (000905), CSI 1000 (000852).
Implementation: priority tushare index_daily → akshare fallback.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

BENCHMARK_MAP = {
    "000300": {"name": "沪深300", "tushare_code": "000300.SH"},
    "000905": {"name": "中证500", "tushare_code": "000905.SH"},
    "000852": {"name": "中证1000", "tushare_code": "000852.SH"},
    "000001": {"name": "上证指数", "tushare_code": "000001.SH"},
    "399300": {"name": "沪深300(深)", "tushare_code": "399300.SZ"},
}


def get_benchmark_history(
    code: str = "000300",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> pd.DataFrame:
    if start_date is None:
        start_date = date.today() - timedelta(days=365 * 3)
    if end_date is None:
        end_date = date.today()

    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    df = _try_tushare(code, start_str, end_str)
    if df is not None and not df.empty:
        return df

    df = _try_akshare(code, start_date, end_date)
    if df is not None and not df.empty:
        return df

    logger.warning("Failed to fetch benchmark %s from all sources", code)
    return pd.DataFrame()


def _try_tushare(code: str, start: str, end: str) -> Optional[pd.DataFrame]:
    try:
        from data_provider.tushare_fetcher import TushareFetcher
        fetcher = TushareFetcher()
        if not fetcher.is_available():
            return None
        ts_code = BENCHMARK_MAP.get(code, {}).get("tushare_code")
        if not ts_code:
            return None
        df = fetcher._api.index_daily(ts_code=ts_code, start_date=start, end_date=end)
        if df is None or df.empty:
            return None
        df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
        df = df.rename(columns={
            "open": "open", "high": "high", "low": "low", "close": "close", "vol": "volume",
        })
        df = df[["date", "open", "high", "low", "close", "volume"]]
        df = df.sort_values("date")
        return df
    except Exception as e:
        logger.debug("Tushare benchmark fetch failed for %s: %s", code, e)
        return None


def _try_akshare(code: str, start: date, end: date) -> Optional[pd.DataFrame]:
    try:
        import akshare as ak
        symbol_map = {
            "000300": "sh000300",
            "000905": "sh000905",
            "000852": "sh000852",
            "000001": "sh000001",
            "399300": "sz399300",
        }
        symbol = symbol_map.get(code, "sh000300")
        df = ak.stock_zh_index_daily(symbol=symbol)
        if df is None or df.empty:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]
        df = df.rename(columns={
            "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume",
        })
        cols = ["date", "open", "high", "low", "close", "volume"]
        df = df[[c for c in cols if c in df.columns]]
        df = df.sort_values("date")
        return df
    except Exception as e:
        logger.debug("Akshare benchmark fetch failed for %s: %s", code, e)
        return None


def get_benchmark_nav_series(
    code: str = "000300",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    initial_value: float = 1.0,
) -> pd.Series:
    df = get_benchmark_history(code=code, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return pd.Series(dtype=float)

    close = df["close"].values
    nav = pd.Series(close / close[0] * initial_value, index=pd.to_datetime(df["date"]), name="benchmark_nav")
    return nav
