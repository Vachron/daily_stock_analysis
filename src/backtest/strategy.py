# -*- coding: utf-8 -*-
"""BacktestStrategy 抽象基类 (FR-001)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING
import warnings

import numpy as np

from src.backtest.order import Order, Trade, Position

if TYPE_CHECKING:
    from src.backtest.broker import _Broker


class _Indicator:
    """内部指标包装器，与 backtesting.py 的 self.I() 行为一致."""

    def __init__(
        self,
        func: Callable,
        *args: Any,
        name: str = None,
        plot: bool = True,
        overlay: bool = True,
        color: str = None,
        **kwargs: Any,
    ) -> None:
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.name = name or func.__name__
        self.plot = plot
        self.overlay = overlay
        self.color = color
        self._cache: Optional[np.ndarray] = None

    def compute(self, data: np.ndarray) -> np.ndarray:
        if self._cache is not None:
            return self._cache
        result = self.func(data, *self.args, **self.kwargs)
        self._cache = np.asarray(result, dtype=float)
        return self._cache

    def clear_cache(self) -> None:
        self._cache = None


class _OHLCVData:
    """OHLCV 数据访问器."""

    def __init__(self, df) -> None:
        self._df = df
        self.Open = df["Open"].values
        self.High = df["High"].values
        self.Low = df["Low"].values
        self.Close = df["Close"].values
        self.Volume = df["Volume"].values if "Volume" in df.columns else np.zeros(len(df))
        self.index = df.index
        self.df = df

    def __len__(self) -> int:
        return len(self._df)


class BacktestStrategy(ABC):
    """回测策略抽象基类 (FR-001).

    用户通过继承此类实现自定义策略:
    - init(): 注册指标 (self.I)
    - next(): 逐根K线执行交易逻辑
    """

    def __init__(self) -> None:
        self._broker: Optional["_Broker"] = None
        self._data: Optional[_OHLCVData] = None
        self._indicators: List[_Indicator] = []
        self._indicator_values: Dict[str, np.ndarray] = {}
        self._equity: float = 0.0

    @abstractmethod
    def init(self) -> None:
        """初始化策略，声明指标和参数."""
        pass

    @abstractmethod
    def next(self, i: int) -> None:
        """每根 K 线调用一次，实现交易逻辑.

        Args:
            i: 当前 K 线索引
        """
        pass

    @property
    def data(self) -> Optional[_OHLCVData]:
        """当前回测数据的访问接口."""
        return self._data

    def I(
        self,
        func: Callable,
        *args: Any,
        name: str = None,
        plot: bool = True,
        overlay: bool = True,
        color: str = None,
        **kwargs: Any,
    ) -> np.ndarray:
        """注册指标函数，框架自动管理计算和绘图 (FR-001).

        返回一个 numpy 数组，可用 [i] 方式访问每根 K 线的值.
        """
        ind = _Indicator(func, *args, name=name, plot=plot, overlay=overlay, color=color, **kwargs)
        self._indicators.append(ind)
        return np.zeros(0)

    def _compute_indicators(self, data: _OHLCVData) -> None:
        """内部: 计算所有已注册指标."""
        self._indicator_values.clear()
        close = data.Close
        for ind in self._indicators:
            try:
                result = ind.compute(close)
                self._indicator_values[ind.name] = result
                setattr(self, ind.name, result)
            except Exception:
                self._indicator_values[ind.name] = np.full(len(close), np.nan)
                setattr(self, ind.name, self._indicator_values[ind.name])

    def _get_indicator(self, name: str, i: int) -> float:
        """获取指标在指定索引处的值."""
        arr = self._indicator_values.get(name)
        if arr is None:
            arr = getattr(self, name, None)
        if arr is not None and 0 <= i < len(arr):
            val = arr[i]
            return float(val) if not np.isnan(val) else np.nan
        return np.nan

    def buy(
        self,
        size: Optional[float] = None,
        limit: Optional[float] = None,
        stop: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        tag: Optional[str] = None,
    ) -> Optional[Order]:
        """下多单 (FR-001)."""
        if self._broker is None:
            return None
        order = Order(
            size=abs(size) if size else float("inf"),
            limit=limit,
            stop=stop,
            sl=sl,
            tp=tp,
            tag=tag,
        )
        self._broker._submit_order(order)
        return order

    def sell(
        self,
        size: Optional[float] = None,
        limit: Optional[float] = None,
        stop: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        tag: Optional[str] = None,
    ) -> Optional[Order]:
        """下空单 (FR-001)."""
        if self._broker is None:
            return None
        order = Order(
            size=-abs(size) if size else float("-inf"),
            limit=limit,
            stop=stop,
            sl=sl,
            tp=tp,
            tag=tag,
        )
        self._broker._submit_order(order)
        return order

    @property
    def position(self) -> Position:
        """当前持仓."""
        if self._broker is None:
            return Position()
        return self._broker.position

    @property
    def equity(self) -> float:
        """当前权益（现金+持仓市值）."""
        if self._broker is None:
            return self._equity
        return self._broker._equity

    @property
    def trades(self) -> Tuple[Trade, ...]:
        """活跃交易."""
        if self._broker is None:
            return ()
        return tuple(self._broker._trades)

    @property
    def closed_trades(self) -> Tuple[Trade, ...]:
        """已结算交易."""
        if self._broker is None:
            return ()
        return tuple(self._broker._closed_trades)

    @property
    def orders(self) -> Tuple[Order, ...]:
        """等待执行的订单."""
        if self._broker is None:
            return ()
        return tuple(self._broker._orders)

    def close_position(self, portion: float = 1.0) -> None:
        """关闭当前持仓 (通过 Broker).

        Args:
            portion: 平仓比例 (0~1)
        """
        if self._broker is None:
            return
        self._broker._close_position(portion)
