# -*- coding: utf-8 -*-
"""Order / Trade / Position 数据类 (FR-004)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


@dataclass
class Order:
    """订单数据类.

    size > 0 = 多单 (long), size < 0 = 空单 (short).
    """

    size: float
    limit: Optional[float] = None
    stop: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    tag: Optional[str] = None

    _id: int = field(default=0, repr=False)
    _type: OrderType = OrderType.MARKET
    _created_bar: int = field(default=0, repr=False)
    _contingent_parent: Optional[Order] = field(default=None, repr=False)
    _cancelled: bool = field(default=False, repr=False)

    @property
    def is_long(self) -> bool:
        return self.size > 0

    @property
    def is_short(self) -> bool:
        return self.size < 0

    @property
    def is_contingent(self) -> bool:
        return self._contingent_parent is not None

    def cancel(self) -> None:
        self._cancelled = True

    def __hash__(self) -> int:
        return id(self)


@dataclass
class Trade:
    """交易记录数据类."""

    size: float
    entry_price: float
    exit_price: Optional[float] = None
    entry_bar: int = 0
    exit_bar: Optional[int] = None
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    tag: Optional[str] = None
    exit_reason: Optional[str] = None
    position_pct: float = 1.0

    _id: int = field(default=0, repr=False)
    _initial_sl: Optional[float] = field(default=None, repr=False)
    _initial_tp: Optional[float] = field(default=None, repr=False)
    _is_closed: bool = field(default=False, repr=False)
    _partial: bool = field(default=False, repr=False)

    @property
    def pl(self) -> float:
        if self.exit_price is None:
            return 0.0
        return self.size * (self.exit_price - self.entry_price)

    @property
    def pl_pct(self) -> float:
        if self.exit_price is None or self.entry_price == 0:
            return 0.0
        return (self.exit_price / self.entry_price - 1) * 100 * (1 if self.size > 0 else -1)

    @property
    def is_long(self) -> bool:
        return self.size > 0

    @property
    def is_short(self) -> bool:
        return self.size < 0

    @property
    def is_open(self) -> bool:
        return not self._is_closed

    @property
    def value(self) -> float:
        if self._is_closed:
            return 0.0
        return abs(self.size) * self.entry_price

    def close(self, portion: float = 1.0) -> None:
        portion = max(0.0, min(1.0, portion))
        if portion >= 1.0:
            self._is_closed = True
        elif portion > 0:
            self._partial = True
            self._is_closed = True


@dataclass
class Position:
    """持仓数据类."""

    size: float = 0.0
    entry_price: float = 0.0

    def pl(self, price: Optional[float] = None) -> float:
        if price is None:
            return 0.0
        return self.size * (price - self.entry_price)

    def pl_pct(self, price: Optional[float] = None) -> float:
        if price is None or self.entry_price == 0:
            return 0.0
        return (price / self.entry_price - 1) * 100 * (1 if self.size > 0 else -1)

    @property
    def is_long(self) -> bool:
        return self.size > 0

    @property
    def is_short(self) -> bool:
        return self.size < 0

    def close(self, portion: float = 1.0) -> None:
        portion = max(0.0, min(1.0, portion))
        self.size *= (1.0 - portion)
