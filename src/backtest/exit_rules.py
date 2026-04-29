# -*- coding: utf-8 -*-
"""平仓规则引擎 (FR-007)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ExitReason(Enum):
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    TAKE_PROFIT = "take_profit"
    PARTIAL_TAKE_PROFIT = "partial_take_profit"
    SIGNAL_LOST = "signal_lost"
    FIXED_DAYS = "fixed_days"
    MAX_HOLD_DAYS = "max_hold_days"
    FORCE_CLOSE = "force_close"
    SIGNAL_EXIT = "signal_exit"
    STOP_ORDER = "stop_order"


EXIT_PRIORITY = {
    ExitReason.STOP_LOSS: 0,
    ExitReason.STOP_ORDER: 1,
    ExitReason.TRAILING_STOP: 2,
    ExitReason.TAKE_PROFIT: 3,
    ExitReason.PARTIAL_TAKE_PROFIT: 4,
    ExitReason.SIGNAL_LOST: 5,
    ExitReason.FIXED_DAYS: 6,
    ExitReason.SIGNAL_EXIT: 7,
    ExitReason.MAX_HOLD_DAYS: 8,
    ExitReason.FORCE_CLOSE: 9,
}


@dataclass
class ExitRule:
    """平仓规则配置.

    优先级顺序 (从高到低):
    1. 固定止损 (stop_loss_pct)
    2. 移动止损 (trailing_stop_pct / trailing_stop_atr)
    3. 目标止盈 (take_profit_pct)
    4. 信号消失 (signal_threshold)
    5. 固定天数 (fixed_days)
    6. 最大持仓天数 (max_hold_days)
    """

    signal_threshold: Optional[float] = None
    fixed_days: Optional[int] = None
    trailing_stop_pct: Optional[float] = None
    trailing_stop_atr: Optional[float] = None
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    max_hold_days: Optional[int] = None
    partial_exit_pct: float = 1.0

    _highest_since_entry: float = field(default=0.0, repr=False)
    _lowest_since_entry: float = field(default=float("inf"), repr=False)
    _entry_bar: int = field(default=0, repr=False)
    _current_bar: int = field(default=0, repr=False)

    def update(self, high: float, low: float, current_bar: int) -> None:
        self._highest_since_entry = max(self._highest_since_entry, high)
        self._lowest_since_entry = min(self._lowest_since_entry, low)
        self._current_bar = current_bar

    def get_entry_bar(self) -> int:
        return self._entry_bar

    def set_entry_bar(self, bar: int) -> None:
        self._entry_bar = bar

    def check(self, entry_price: float, position_size: float,
              signal_strength: Optional[float] = None) -> list[tuple[ExitReason, float, str]]:
        """检查所有平仓规则，返回触发的原因列表.

        Returns:
            [(reason, exit_fraction, description), ...]
            按优先级排序，用 fraction=1.0 表示完全平仓
        """
        triggers: list[tuple[int, ExitReason, float, str]] = []

        if self.stop_loss_pct is not None and self.stop_loss_pct > 0:
            if position_size > 0:
                stop_price = entry_price * (1 - self.stop_loss_pct / 100)
                if self._lowest_since_entry <= stop_price:
                    triggers.append((
                        EXIT_PRIORITY[ExitReason.STOP_LOSS],
                        ExitReason.STOP_LOSS,
                        1.0,
                        f"固定止损触发: 最低价 {self._lowest_since_entry:.2f} <= 止损价 {stop_price:.2f}",
                    ))
            elif position_size < 0:
                stop_price = entry_price * (1 + self.stop_loss_pct / 100)
                if self._highest_since_entry >= stop_price:
                    triggers.append((
                        EXIT_PRIORITY[ExitReason.STOP_LOSS],
                        ExitReason.STOP_LOSS,
                        1.0,
                        f"固定止损触发: 最高价 {self._highest_since_entry:.2f} >= 止损价 {stop_price:.2f}",
                    ))

        if self.trailing_stop_pct is not None and self.trailing_stop_pct > 0:
            if position_size > 0:
                trailing_price = self._highest_since_entry * (1 - self.trailing_stop_pct / 100)
                if self._lowest_since_entry <= trailing_price:
                    triggers.append((
                        EXIT_PRIORITY[ExitReason.TRAILING_STOP],
                        ExitReason.TRAILING_STOP,
                        1.0,
                        f"移动止损触发: 从最高点 {self._highest_since_entry:.2f} 回撤 {self.trailing_stop_pct}%",
                    ))
            elif position_size < 0:
                trailing_price = self._lowest_since_entry * (1 + self.trailing_stop_pct / 100)
                if self._highest_since_entry >= trailing_price:
                    triggers.append((
                        EXIT_PRIORITY[ExitReason.TRAILING_STOP],
                        ExitReason.TRAILING_STOP,
                        1.0,
                        f"移动止损触发: 从最低点 {self._lowest_since_entry:.2f} 反弹 {self.trailing_stop_pct}%",
                    ))

        if self.take_profit_pct is not None and self.take_profit_pct > 0:
            if position_size > 0:
                tp_price = entry_price * (1 + self.take_profit_pct / 100)
                if self._highest_since_entry >= tp_price:
                    reason = ExitReason.TAKE_PROFIT
                    fraction = 1.0
                    desc = f"目标止盈触发: 最高价 {self._highest_since_entry:.2f} >= 止盈价 {tp_price:.2f}"
                    if self.partial_exit_pct < 1.0:
                        reason = ExitReason.PARTIAL_TAKE_PROFIT
                        fraction = self.partial_exit_pct
                        desc = f"部分止盈触发 ({self.partial_exit_pct*100:.0f}%): 最高价 {self._highest_since_entry:.2f} >= 止盈价 {tp_price:.2f}"
                    triggers.append((
                        EXIT_PRIORITY[ExitReason.TAKE_PROFIT],
                        reason,
                        fraction,
                        desc,
                    ))
            elif position_size < 0:
                tp_price = entry_price * (1 - self.take_profit_pct / 100)
                if self._lowest_since_entry <= tp_price:
                    triggers.append((
                        EXIT_PRIORITY[ExitReason.TAKE_PROFIT],
                        ExitReason.TAKE_PROFIT,
                        1.0,
                        f"目标止盈触发: 最低价 {self._lowest_since_entry:.2f} <= 止盈价 {tp_price:.2f}",
                    ))

        if self.signal_threshold is not None and signal_strength is not None:
            if signal_strength < self.signal_threshold:
                triggers.append((
                    EXIT_PRIORITY[ExitReason.SIGNAL_LOST],
                    ExitReason.SIGNAL_LOST,
                    1.0,
                    f"信号消失: 信号强度 {signal_strength:.4f} < 阈值 {self.signal_threshold}",
                ))

        if self.fixed_days is not None and self.fixed_days > 0:
            bars_held = self._current_bar - self._entry_bar
            if bars_held >= self.fixed_days:
                triggers.append((
                    EXIT_PRIORITY[ExitReason.FIXED_DAYS],
                    ExitReason.FIXED_DAYS,
                    1.0,
                    f"固定天数平仓: 持仓 {bars_held} 天 >= {self.fixed_days} 天",
                ))

        if self.max_hold_days is not None and self.max_hold_days > 0:
            bars_held = self._current_bar - self._entry_bar
            if bars_held >= self.max_hold_days:
                triggers.append((
                    EXIT_PRIORITY[ExitReason.MAX_HOLD_DAYS],
                    ExitReason.MAX_HOLD_DAYS,
                    1.0,
                    f"最大持仓天数强制平仓: 持仓 {bars_held} 天 >= {self.max_hold_days} 天",
                ))

        triggers.sort(key=lambda x: x[0])
        return [(reason, fraction, desc) for _, reason, fraction, desc in triggers]
