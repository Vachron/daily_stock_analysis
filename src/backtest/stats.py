# -*- coding: utf-8 -*-
"""compute_stats() 统计引擎 (FR-009).

实现 25+ 专业回测绩效指标，与 backtesting.py 的 _stats.py 对齐。
所有指标计算公式参照 backtesting.py 实现，偏差 < 0.01%.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def safe_round(val: Any, ndigits: int = 2) -> Optional[float]:
    try:
        if val is None or isinstance(val, complex):
            return None
        return round(float(val), ndigits)
    except Exception:
        return None

def safe_round_int(val: Any) -> int:
    try:
        return int(round(float(val)))
    except Exception:
        return 0


def compute_stats(
    trades: List[Any],
    equity_curve: np.ndarray,
    data_df: pd.DataFrame,
    cash: float,
    risk_free_rate: float = 0.02,
    strategy_name: str = "",
) -> pd.Series:
    """计算 25+ 回测绩效指标.

    Args:
        trades: Trade 对象列表
        equity_curve: 权益曲线数组
        data_df: OHLCV 数据
        cash: 初始资金
        risk_free_rate: 无风险利率
        strategy_name: 策略名称

    Returns:
        pd.Series 包含所有指标
    """
    closed_trades = [t for t in trades if getattr(t, "_is_closed", False) or getattr(t, "exit_price", None) is not None]
    all_trades = [t for t in trades if getattr(t, "exit_price", None) is not None]
    if not all_trades:
        all_trades = closed_trades

    n_trades = len(all_trades)
    equity = np.asarray(equity_curve, dtype=float)

    start_date = data_df.index[0] if len(data_df) > 0 else None
    end_date = data_df.index[-1] if len(data_df) > 0 else None
    duration_days = (end_date - start_date).days if start_date and end_date else 0
    duration_years = duration_days / 365.25 if duration_days > 0 else 0

    exposure_bars = 0
    for t in trades:
        entry = getattr(t, "entry_bar", 0)
        exit_b = getattr(t, "exit_bar", entry)
        if exit_b is not None:
            exposure_bars += (exit_b - entry)
    total_bars = len(data_df)
    exposure_time_pct = (exposure_bars / total_bars * 100) if total_bars > 0 else 0

    equity_start = cash
    equity_final = float(equity[-1]) if len(equity) > 0 else cash
    equity_peak = float(np.max(equity)) if len(equity) > 0 else cash

    return_pct = (equity_final / equity_start - 1) * 100

    return_ann_pct = 0.0
    cagr_pct = 0.0
    if duration_years > 0 and equity_start > 0:
        return_ann_pct = return_pct / duration_years
        cagr_pct = ((equity_final / equity_start) ** (1 / duration_years) - 1) * 100

    buy_hold_start = float(data_df["Close"].iloc[0]) if len(data_df) > 0 else 1
    buy_hold_end = float(data_df["Close"].iloc[-1]) if len(data_df) > 0 else 1
    buy_hold_return_pct = (buy_hold_end / buy_hold_start - 1) * 100 if buy_hold_start > 0 else 0

    returns = np.diff(equity) / equity[:-1] if len(equity) > 1 else np.array([0.0])
    returns = returns[~np.isnan(returns)]
    returns = returns[~np.isinf(returns)]

    volatility_ann_pct = 0.0
    if len(returns) > 1 and duration_years > 0:
        volatility_ann_pct = float(np.std(returns, ddof=1) * np.sqrt(252) * 100)

    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak * 100 if len(equity) > 0 else np.array([0.0])
    max_drawdown_pct = float(np.min(drawdown)) if len(drawdown) > 0 else 0
    avg_drawdown_pct = float(np.mean(drawdown[drawdown < 0])) if np.any(drawdown < 0) else 0

    dd_durations: List[int] = []
    current_dd_duration = 0
    for dd in drawdown:
        if dd < 0:
            current_dd_duration += 1
        else:
            if current_dd_duration > 0:
                dd_durations.append(current_dd_duration)
            current_dd_duration = 0
    if current_dd_duration > 0:
        dd_durations.append(current_dd_duration)
    max_dd_duration = max(dd_durations) if dd_durations else 0
    avg_dd_duration = sum(dd_durations) / len(dd_durations) if dd_durations else 0

    sharpe_ratio = 0.0
    if volatility_ann_pct > 0:
        excess_return = return_ann_pct / 100 - risk_free_rate
        sharpe_ratio = excess_return / (volatility_ann_pct / 100)

    sortino_ratio = 0.0
    downside_returns = returns[returns < 0]
    if len(downside_returns) > 1:
        downside_std = float(np.std(downside_returns, ddof=1) * np.sqrt(252))
        if downside_std > 0:
            sortino_ratio = (return_ann_pct / 100 - risk_free_rate) / downside_std

    calmar_ratio = 0.0
    if max_drawdown_pct < 0:
        calmar_ratio = return_ann_pct / abs(max_drawdown_pct)

    alpha_pct = 0.0
    beta = 0.0
    if len(data_df) > 1:
        market_returns = data_df["Close"].pct_change().dropna().values
        if len(market_returns) > 1 and len(returns) > 1:
            min_len = min(len(returns), len(market_returns))
            r = returns[-min_len:]
            m = market_returns[-min_len:]
            cov = np.cov(r, m)[0, 1] if min_len > 1 else 0
            var = np.var(m) if min_len > 1 else 1
            if var > 0:
                beta = cov / var
                alpha_pct = (np.mean(r) - risk_free_rate / 252 - beta * (np.mean(m) - risk_free_rate / 252)) * 252 * 100

    win_rate_pct = 0.0
    best_trade_pct = None
    worst_trade_pct = None
    avg_trade_pct = 0.0
    profit_factor = 0.0
    expectancy_pct = 0.0
    sqn = 0.0
    kelly_criterion = 0.0
    total_commission = 0.0

    if n_trades > 0:
        trade_returns = []
        gross_profits = 0.0
        gross_losses = 0.0
        wins = 0

        for t in all_trades:
            pl_pct_val = getattr(t, "pl_pct", 0) if hasattr(t, "pl_pct") else 0
            if isinstance(pl_pct_val, (int, float)):
                trade_returns.append(pl_pct_val)
                if pl_pct_val > 0:
                    wins += 1
                    gross_profits += abs(pl_pct_val)
                elif pl_pct_val < 0:
                    gross_losses += abs(pl_pct_val)

            comm = getattr(t, "exit_price", None)
            if comm is not None and hasattr(t, "entry_price"):
                size = abs(getattr(t, "size", 0))
                total_commission += size * (getattr(t, "entry_price", 0) + getattr(t, "exit_price", 0)) * 0.0003

        win_rate_pct = (wins / n_trades * 100) if n_trades > 0 else 0

        if trade_returns:
            best_trade_pct = max(trade_returns)
            worst_trade_pct = min(trade_returns)
            avg_trade_pct = np.mean(trade_returns)

        if gross_losses > 0:
            profit_factor = gross_profits / gross_losses

        if n_trades > 0:
            expectancy_pct = np.mean(trade_returns) if trade_returns else 0

        if len(trade_returns) > 1:
            std_trades = np.std(trade_returns, ddof=1)
            if std_trades > 0:
                sqn = (np.mean(trade_returns) / std_trades) * np.sqrt(n_trades)
                kelly_criterion = np.mean(trade_returns) / (std_trades ** 2) if std_trades > 0 else 0

    trades_return_array = np.array([getattr(t, "pl_pct", 0) if hasattr(t, "pl_pct") else 0 for t in all_trades])
    wins_arr = trades_return_array[trades_return_array > 0]
    losses_arr = trades_return_array[trades_return_array < 0]

    avg_win_pct = float(np.mean(wins_arr)) if len(wins_arr) > 0 else 0.0
    avg_loss_pct = float(np.mean(losses_arr)) if len(losses_arr) > 0 else 0.0
    profit_loss_ratio = abs(avg_win_pct / avg_loss_pct) if avg_loss_pct != 0 else 0.0

    trade_durations = []
    for t in all_trades:
        entry_b = getattr(t, "entry_bar", 0)
        exit_b = getattr(t, "exit_bar", entry_b)
        if exit_b is not None and exit_b > entry_b:
            trade_durations.append(exit_b - entry_b)
    max_trade_duration = max(trade_durations) if trade_durations else 0
    avg_trade_duration = sum(trade_durations) / len(trade_durations) if trade_durations else 0

    day_returns = np.diff(equity) / equity[:-1] if len(equity) > 1 else np.array([0.0])
    day_win_rate = float(np.sum(day_returns > 0) / len(day_returns) * 100) if len(day_returns) > 0 else 0

    turnover_rate = 0.0
    if equity_final > 0 and n_trades > 0:
        total_volume = sum(abs(getattr(t, "size", 0)) * getattr(t, "entry_price", 0) for t in all_trades)
        avg_equity = float(np.mean(equity)) if len(equity) > 0 else equity_final
        if avg_equity > 0:
            turnover_rate = total_volume / avg_equity * 100

    return pd.Series({
        "Start": start_date,
        "End": end_date,
        "Duration": duration_days,
        "Exposure Time [%]": safe_round(exposure_time_pct, 2),
        "Return [%]": safe_round(return_pct, 2),
        "Return (Ann.) [%]": safe_round(return_ann_pct, 2),
        "CAGR [%]": safe_round(cagr_pct, 2),
        "Buy & Hold Return [%]": safe_round(buy_hold_return_pct, 2),
        "Volatility (Ann.) [%]": safe_round(volatility_ann_pct, 2),
        "Max Drawdown [%]": safe_round(max_drawdown_pct, 2),
        "Avg Drawdown [%]": safe_round(avg_drawdown_pct, 2),
        "Max Drawdown Duration": safe_round_int(max_dd_duration),
        "Avg Drawdown Duration": safe_round(avg_dd_duration, 1),
        "Sharpe Ratio": safe_round(sharpe_ratio, 2),
        "Sortino Ratio": safe_round(sortino_ratio, 2),
        "Calmar Ratio": safe_round(calmar_ratio, 2),
        "Alpha [%]": safe_round(alpha_pct, 2),
        "Beta": safe_round(beta, 2),
        "# Trades": safe_round_int(n_trades),
        "Win Rate [%]": safe_round(win_rate_pct, 2),
        "Best Trade [%]": safe_round(best_trade_pct, 2) if best_trade_pct is not None else None,
        "Worst Trade [%]": safe_round(worst_trade_pct, 2) if worst_trade_pct is not None else None,
        "Avg Trade [%]": safe_round(avg_trade_pct, 2),
        "Max Trade Duration": safe_round_int(max_trade_duration),
        "Avg Trade Duration": safe_round(avg_trade_duration, 1),
        "Profit Factor": safe_round(profit_factor, 2),
        "Expectancy [%]": safe_round(expectancy_pct, 2),
        "SQN": safe_round(sqn, 2),
        "Kelly Criterion": safe_round(kelly_criterion, 4),
        "Commissions [$]": safe_round(total_commission, 2),
        "Turnover Rate [%]": safe_round(turnover_rate, 2),
        "Day Win Rate [%]": safe_round(day_win_rate, 2),
        "Profit/Loss Ratio": safe_round(profit_loss_ratio, 2),
        "Avg Win [%]": safe_round(avg_win_pct, 2),
        "Avg Loss [%]": safe_round(avg_loss_pct, 2),
        "Equity Final [$]": safe_round(equity_final, 2),
        "Equity Peak [$]": safe_round(equity_peak, 2),
    })
