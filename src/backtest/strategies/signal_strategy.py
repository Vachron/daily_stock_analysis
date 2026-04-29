# -*- coding: utf-8 -*-
"""SignalStrategy — 向量化信号策略 (FR-017)."""

from __future__ import annotations

from typing import Optional

import numpy as np

from src.backtest.strategy import BacktestStrategy


class SignalStrategy(BacktestStrategy):
    """基于预定义信号的向量化回测策略.

    Usage:
        strategy = SignalStrategy()
        strategy.set_signal(entry_signal, exit_signal)
    """

    def __init__(self) -> None:
        super().__init__()
        self._entry_signal: Optional[np.ndarray] = None
        self._exit_signal: Optional[np.ndarray] = None
        self._exit_portion: float = 1.0
        self._plot_signal: bool = True

    def init(self) -> None:
        pass

    def next(self, i: int) -> None:
        if self._entry_signal is None:
            return

        if i < len(self._entry_signal) and self._entry_signal[i]:
            for trade in list(self.trades):
                if not trade._is_closed and trade.size > 0:
                    return
            self.buy(tag="signal_entry")

        if self._exit_signal is not None and i < len(self._exit_signal) and self._exit_signal[i]:
            for trade in list(self.trades):
                if not trade._is_closed:
                    trade.close(portion=self._exit_portion)

    def set_signal(
        self,
        entry_size: np.ndarray,
        exit_portion: Optional[np.ndarray] = None,
        plot: bool = True,
    ) -> None:
        """设置入场/出场信号向量.

        Args:
            entry_size: 入场信号向量，>0 表示买入，<=0 表示不操作
            exit_portion: 出场信号向量，>0 表示平仓比例
            plot: 是否绘图
        """
        self._entry_signal = np.asarray(entry_size)
        self._exit_signal = np.asarray(exit_portion) if exit_portion is not None else None
        self._plot_signal = plot

    def set_exit_portion(self, portion: float = 1.0) -> None:
        self._exit_portion = max(0.0, min(1.0, portion))
