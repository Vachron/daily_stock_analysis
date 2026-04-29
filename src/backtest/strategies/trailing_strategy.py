# -*- coding: utf-8 -*-
"""TrailingStrategy — ATR/百分比追踪止损策略 (FR-015/018)."""

from __future__ import annotations

from typing import Optional

import numpy as np

from src.backtest.strategy import BacktestStrategy
from src.backtest.lib import ATR


class TrailingStrategy(BacktestStrategy):
    """带追踪止损的策略混入基类 (FR-015).

    Usage:
        class MyStrategy(TrailingStrategy):
            def init(self):
                self.set_trailing_sl(n_atr=6)
                super().init()

            def next(self, i):
                super().next(i)
                # 交易逻辑
    """

    def __init__(self) -> None:
        super().__init__()
        self._trailing_sl_atr: Optional[float] = None
        self._trailing_sl_pct: Optional[float] = None
        self._atr_periods: int = 100
        self._atr_values: Optional[np.ndarray] = None
        self._highest_since_entry: dict[int, float] = {}
        self._lowest_since_entry: dict[int, float] = {}

    def set_atr_periods(self, periods: int = 100) -> None:
        self._atr_periods = periods

    def set_trailing_sl(self, n_atr: float = 6.0) -> None:
        self._trailing_sl_atr = n_atr
        self._trailing_sl_pct = None

    def set_trailing_pct(self, pct: float = 0.05) -> None:
        self._trailing_sl_pct = pct
        self._trailing_sl_atr = None

    def init(self) -> None:
        super().init()
        if self._trailing_sl_atr is not None and self.data is not None:
            self._atr_values = self.I(
                ATR, self.data.High, self.data.Low, self.data.Close, self._atr_periods,
                name="ATR", plot=True, overlay=False,
            )

    def next(self, i: int) -> None:
        if self._trailing_sl_atr is not None and self._atr_values is not None:
            atr_val = self._atr_values[i] if i < len(self._atr_values) else np.nan
            if not np.isnan(atr_val) and atr_val > 0:
                for trade in list(self.trades):
                    if trade._is_closed:
                        continue
                    trade_id = getattr(trade, "_id", id(trade))
                    if trade.size > 0:
                        self._highest_since_entry[trade_id] = max(
                            self._highest_since_entry.get(trade_id, trade.entry_price),
                            float(self.data.High[i]),
                        )
                        new_sl = self._highest_since_entry[trade_id] - self._trailing_sl_atr * atr_val
                        if trade.sl is None or new_sl > trade.sl:
                            trade.sl = new_sl
                    else:
                        self._lowest_since_entry[trade_id] = min(
                            self._lowest_since_entry.get(trade_id, trade.entry_price),
                            float(self.data.Low[i]),
                        )
                        new_sl = self._lowest_since_entry[trade_id] + self._trailing_sl_atr * atr_val
                        if trade.sl is None or new_sl < trade.sl:
                            trade.sl = new_sl

        elif self._trailing_sl_pct is not None:
            for trade in list(self.trades):
                if trade._is_closed:
                    continue
                trade_id = getattr(trade, "_id", id(trade))
                if trade.size > 0:
                    self._highest_since_entry[trade_id] = max(
                        self._highest_since_entry.get(trade_id, trade.entry_price),
                        float(self.data.High[i]),
                    )
                    new_sl = self._highest_since_entry[trade_id] * (1 - self._trailing_sl_pct / 100)
                    if trade.sl is None or new_sl > trade.sl:
                        trade.sl = new_sl
                else:
                    self._lowest_since_entry[trade_id] = min(
                        self._lowest_since_entry.get(trade_id, trade.entry_price),
                        float(self.data.Low[i]),
                    )
                    new_sl = self._lowest_since_entry[trade_id] * (1 + self._trailing_sl_pct / 100)
                    if trade.sl is None or new_sl < trade.sl:
                        trade.sl = new_sl
