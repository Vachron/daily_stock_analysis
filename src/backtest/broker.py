# -*- coding: utf-8 -*-
"""_Broker 模拟经纪商 (FR-005/006)."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np

from src.backtest.order import Order, Trade, Position, OrderType

if TYPE_CHECKING:
    from src.backtest.strategy import _OHLCVData


class _Broker:
    """模拟经纪商 — 订单管理、撮合、手续费、T+1 规则."""

    def __init__(
        self,
        cash: float,
        data: "_OHLCVData",
        commission: float = 0.0003,
        slippage: float = 0.001,
        stamp_duty: float = 0.001,
        min_commission: float = 5.0,
        margin: float = 1.0,
        trade_on_close: bool = False,
        hedging: bool = False,
        exclusive_orders: bool = False,
        t_plus_one: bool = True,
        exit_rule: Any = None,
    ) -> None:
        self._cash: float = float(cash)
        self._initial_cash: float = float(cash)
        self._data = data
        self._commission: float = commission
        self._slippage: float = slippage
        self._stamp_duty: float = stamp_duty
        self._min_commission: float = min_commission
        self._margin: float = margin
        self._trade_on_close: bool = trade_on_close
        self._hedging: bool = hedging
        self._exclusive_orders: bool = exclusive_orders
        self._t_plus_one: bool = t_plus_one
        self._exit_rule = exit_rule

        self._orders: List[Order] = []
        self._trades: List[Trade] = []
        self._closed_trades: List[Trade] = []
        self._equity_history: List[float] = []
        self._position: Position = Position()
        self._order_id_counter: int = 0
        self._trade_id_counter: int = 0
        self._last_trade_bar: int = -1
        self._current_bar: int = 0

    @property
    def position(self) -> Position:
        return self._position

    @property
    def _equity(self) -> float:
        idx = max(0, self._current_bar)
        high = self._data.High[idx] if idx < len(self._data.High) else self._data.High[-1]
        close = self._data.Close[idx] if idx < len(self._data.Close) else self._data.Close[-1]
        price = high if not self._trade_on_close else close
        return self._cash + self._position.pl(price)

    def _submit_order(self, order: Order) -> None:
        """提交订单到订单簿."""
        if order._cancelled:
            return
        if order.limit is not None:
            order._type = OrderType.LIMIT
        elif order.stop is not None:
            order._type = OrderType.STOP
        self._order_id_counter += 1
        order._id = self._order_id_counter
        self._orders.append(order)

        if order.sl is not None or order.tp is not None:
            contingent = Order(
                size=-order.size,
                sl=None,
                tp=None,
                tag=f"{order.tag or ''}_contingent",
            )
            contingent._contingent_parent = order
            contingent._id = self._order_id_counter
            self._orders.append(contingent)

    def _process_orders(self, i: int) -> None:
        """逐K线处理挂单 (FR-006)."""
        open_p = float(self._data.Open[i])
        high_p = float(self._data.High[i])
        low_p = float(self._data.Low[i])
        close_p = float(self._data.Close[i])

        remaining: List[Order] = []

        for order in self._orders:
            if order._cancelled:
                continue

            if order._contingent_parent is not None:
                parent_filled = not any(
                    o._id == order._contingent_parent._id for o in self._orders
                ) and order._contingent_parent._id not in {t._id for t in self._trades}
                if not parent_filled:
                    remaining.append(order)
                    continue

            fill_price = self._match_order(order, open_p, high_p, low_p, close_p)

            if fill_price is not None:
                self._execute_order(order, fill_price, i)
            else:
                remaining.append(order)

        self._orders = remaining

    def _match_order(
        self,
        order: Order,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
    ) -> Optional[float]:
        """订单撮合逻辑."""
        if order._type == OrderType.MARKET:
            if self._trade_on_close:
                return close_p
            return open_p

        elif order._type == OrderType.LIMIT:
            if order.limit is None:
                return open_p
            if order.size > 0 and low_p <= order.limit:
                return order.limit
            if order.size < 0 and high_p >= order.limit:
                return order.limit
            return None

        elif order._type == OrderType.STOP:
            if order.stop is None:
                return open_p
            if order.size > 0 and high_p >= order.stop:
                if order.is_contingent:
                    return max(order.stop, open_p)
                return order.stop
            if order.size < 0 and low_p <= order.stop:
                if order.is_contingent:
                    return min(order.stop, open_p)
                return order.stop
            return None

        return None

    def _execute_order(self, order: Order, fill_price: float, bar: int) -> None:
        """执行订单，创建交易."""
        from src.backtest.exit_rules import ExitReason

        if order.is_contingent:
            if order._contingent_parent is None:
                return
            parent_size = order._contingent_parent.size
            exit_trade = self._find_matching_trade(parent_size)
            if exit_trade is not None:
                exit_trade.sl = order.sl
                exit_trade.tp = order.tp
            return

        slippage_adj = self._slippage
        if order.size > 0:
            effective_price = fill_price * (1 + slippage_adj)
        else:
            effective_price = fill_price * (1 - slippage_adj)

        if self._exclusive_orders and len(self._trades) > 0:
            self._close_all_trades(effective_price, bar, exit_reason=ExitReason.FORCE_CLOSE)

        actual_size = order.size
        if order.size == float("inf"):
            actual_size = math.floor(self._cash / effective_price)
        elif order.size == float("-inf"):
            actual_size = -math.floor(self._cash / effective_price)
        elif isinstance(order.size, float) and 0 < order.size < 1:
            actual_size = math.floor(self._cash / effective_price * order.size)

        if actual_size == 0:
            return

        if self._t_plus_one and bar == self._last_trade_bar:
            return

        trade = Trade(
            size=actual_size,
            entry_price=effective_price,
            entry_bar=bar,
            entry_time=self._data.index[bar] if hasattr(self._data.index[bar], "to_pydatetime") else self._data.index[bar],
            sl=order.sl,
            tp=order.tp,
            tag=order.tag,
            position_pct=1.0,
        )
        self._trade_id_counter += 1
        trade._id = self._trade_id_counter
        trade._initial_sl = order.sl
        trade._initial_tp = order.tp

        if self._exit_rule is not None:
            sl_pct = getattr(self._exit_rule, 'stop_loss_pct', None)
            if trade.sl is None and sl_pct is not None and sl_pct > 0:
                trade.sl = effective_price * (1 - sl_pct / 100)
            tp_pct = getattr(self._exit_rule, 'take_profit_pct', None)
            if trade.tp is None and tp_pct is not None and tp_pct > 0:
                trade.tp = effective_price * (1 + tp_pct / 100)

        cost = abs(actual_size) * effective_price
        commission = max(self._min_commission, cost * self._commission)
        trade_cost = cost + commission
        if trade_cost > self._cash:
            actual_size = math.floor(self._cash / (effective_price + commission / max(abs(actual_size), 1)))
            if actual_size == 0:
                return
            trade.size = actual_size
            cost = abs(actual_size) * effective_price
            commission = max(self._min_commission, cost * self._commission)

        self._cash -= (cost + commission)
        self._position.size += actual_size
        self._position.entry_price = effective_price
        self._trades.append(trade)
        self._last_trade_bar = bar

    def _close_trade(
        self,
        trade: Trade,
        price: float,
        bar: int,
        exit_reason: Any = None,
        portion: float = 1.0,
    ) -> None:
        """平仓一笔交易."""
        if trade._is_closed:
            return

        portion = max(0.0, min(1.0, portion))
        closed_size = trade.size * portion

        slippage_adj = self._slippage
        if closed_size > 0:
            effective_price = price * (1 - slippage_adj)
        else:
            effective_price = price * (1 + slippage_adj)

        trade.exit_price = effective_price
        trade.exit_bar = bar
        trade.exit_time = self._data.index[bar] if hasattr(self._data.index[bar], "to_pydatetime") else self._data.index[bar]

        from src.backtest.exit_rules import ExitReason
        if isinstance(exit_reason, ExitReason):
            trade.exit_reason = exit_reason.value
        elif isinstance(exit_reason, str):
            trade.exit_reason = exit_reason
        else:
            trade.exit_reason = ExitReason.FORCE_CLOSE.value

        revenue = abs(closed_size) * effective_price
        commission = max(self._min_commission, revenue * self._commission)
        stamp = revenue * self._stamp_duty if closed_size > 0 else 0

        trade._is_closed = True
        if portion < 1.0:
            trade._partial = True

        self._cash += revenue - commission - stamp
        self._position.size -= closed_size

        if trade in self._trades:
            self._trades.remove(trade)
        self._closed_trades.append(trade)
        
        if portion < 1.0 and not trade._partial:
            trade.size -= closed_size

    def _close_all_trades(self, price: float, bar: int, exit_reason: Any = None) -> None:
        """平掉所有持仓."""
        for trade in list(self._trades):
            if not trade._is_closed:
                self._close_trade(trade, price, bar, exit_reason)

    def _find_matching_trade(self, size: float) -> Optional[Trade]:
        """查找方向匹配的持仓."""
        for trade in self._trades:
            if not trade._is_closed and (size > 0) == (trade.size > 0):
                return trade
        return None

    def _check_sl_tp(self, i: int) -> None:
        """检查止损止盈条件 (FR-007)."""
        high_p = float(self._data.High[i])
        low_p = float(self._data.Low[i])
        close_p = float(self._data.Close[i])
        open_p = float(self._data.Open[i])

        from src.backtest.exit_rules import ExitReason

        for trade in list(self._trades):
            if trade._is_closed:
                continue

            exit_triggered = False
            exit_price = close_p
            exit_reason = None
            exit_portion = 1.0

            if trade.size > 0:
                if trade.sl is not None and low_p <= trade.sl:
                    exit_price = max(trade.sl, open_p)
                    exit_triggered = True
                    exit_reason = ExitReason.STOP_LOSS
                elif trade.tp is not None and high_p >= trade.tp:
                    exit_price = trade.tp
                    exit_triggered = True
                    exit_reason = ExitReason.TAKE_PROFIT
            else:
                if trade.sl is not None and high_p >= trade.sl:
                    exit_price = min(trade.sl, open_p)
                    exit_triggered = True
                    exit_reason = ExitReason.STOP_LOSS
                elif trade.tp is not None and low_p <= trade.tp:
                    exit_price = trade.tp
                    exit_triggered = True
                    exit_reason = ExitReason.TAKE_PROFIT

            if exit_triggered:
                self._close_trade(trade, exit_price, i, exit_reason, exit_portion)

    def _check_ruin(self) -> bool:
        """破产检测."""
        return self._equity <= 0

    def _finalize(self, bar: int) -> None:
        """收尾: 强制平仓."""
        from src.backtest.exit_rules import ExitReason
        close_p = float(self._data.Close[-1])
        self._close_all_trades(close_p, bar, exit_reason=ExitReason.FORCE_CLOSE)

    def _close_position(self, portion: float = 1.0, price: Optional[float] = None, bar: Optional[int] = None) -> None:
        if price is None:
            idx = bar if bar is not None else max(0, self._current_bar)
            price = float(self._data.Close[idx])
        idx = bar if bar is not None else max(0, self._current_bar)
        for trade in list(self._trades):
            if not trade._is_closed:
                self._close_trade(trade, price, idx, exit_reason="manual")
