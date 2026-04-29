# -*- coding: utf-8 -*-
"""仓位管理策略 (FR-008)."""

from __future__ import annotations

import math
from enum import Enum
from typing import Optional


class PositionSizing(Enum):
    FULL = "full"
    SIGNAL = "signal"
    KELLY = "kelly"
    FIXED = "fixed"
    EQUAL_RISK = "equal"


def calculate_position_size(
    method: PositionSizing,
    cash: float,
    price: float,
    signal_strength: Optional[float] = None,
    win_rate: Optional[float] = None,
    avg_win_pct: Optional[float] = None,
    avg_loss_pct: Optional[float] = None,
    atr: Optional[float] = None,
    risk_per_trade_pct: float = 0.02,
    fixed_pct: float = 1.0,
) -> float:
    """计算仓位大小.

    Args:
        method: 仓位管理模式
        cash: 可用资金
        price: 当前价格
        signal_strength: 信号强度 (0-1), 用于 signal 模式
        win_rate: 胜率, 用于 kelly 模式
        avg_win_pct: 平均盈利百分比, 用于 kelly 模式
        avg_loss_pct: 平均亏损百分比, 用于 kelly 模式
        atr: ATR 值, 用于 equal_risk 模式
        risk_per_trade_pct: 每笔交易风险比例
        fixed_pct: 固定仓位比例

    Returns:
        建议仓位大小 (股票数量)
    """
    if price <= 0:
        return 0.0

    if method == PositionSizing.FULL:
        return math.floor(cash / price)

    elif method == PositionSizing.SIGNAL:
        if signal_strength is None:
            signal_strength = 0.5
        signal_strength = max(0.0, min(1.0, signal_strength))
        target_cash = cash * signal_strength
        return math.floor(target_cash / price)

    elif method == PositionSizing.KELLY:
        if win_rate is None or avg_win_pct is None or avg_loss_pct is None:
            return math.floor(cash / price)
        if avg_loss_pct == 0:
            return math.floor(cash / price)
        b = avg_win_pct / abs(avg_loss_pct)
        p = win_rate
        q = 1 - p
        kelly_fraction = (p * b - q) / b if b > 0 else 0
        kelly_fraction = max(0.0, min(1.0, kelly_fraction))
        kelly_fraction *= 0.5
        target_cash = cash * kelly_fraction
        return math.floor(target_cash / price)

    elif method == PositionSizing.FIXED:
        fixed_pct = max(0.0, min(1.0, fixed_pct))
        target_cash = cash * fixed_pct
        return math.floor(target_cash / price)

    elif method == PositionSizing.EQUAL_RISK:
        if atr is None or atr <= 0:
            return math.floor(cash / price)
        risk_amount = cash * risk_per_trade_pct
        shares = math.floor(risk_amount / atr)
        max_shares = math.floor(cash / price)
        return min(shares, max_shares)

    return 0.0
