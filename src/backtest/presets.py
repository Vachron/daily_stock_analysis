# -*- coding: utf-8 -*-
"""BacktestPresets 参数预设系统 (FR-011)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ActivityLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class CapSize(Enum):
    LARGE = "large"
    MID = "mid"
    SMALL = "small"
    MICRO = "micro"


@dataclass
class BacktestPreset:
    name: str = ""
    display_name: str = ""
    activity_level: ActivityLevel = ActivityLevel.MEDIUM
    cap_size: CapSize = CapSize.MID
    threshold: float = 0.55
    trailing_stop_pct: Optional[float] = 0.05
    take_profit_pct: Optional[float] = 0.08
    stop_loss_pct: Optional[float] = 0.03
    max_hold_days: Optional[int] = None
    position_sizing: str = "full"
    fee_rate: float = 0.0015
    min_confidence: Optional[float] = None
    min_ret_5d: Optional[float] = None
    partial_exit_enabled: bool = False
    partial_exit_pct: float = 0.5


# 16 种预设组合 (FR-011)
_PRESETS: dict[tuple[ActivityLevel, CapSize], BacktestPreset] = {
    (ActivityLevel.LOW, CapSize.LARGE): BacktestPreset(
        name="blue_chip", display_name="蓝筹（低波动+大盘）",
        activity_level=ActivityLevel.LOW, cap_size=CapSize.LARGE,
        threshold=0.45, trailing_stop_pct=0.03, take_profit_pct=0.04,
        stop_loss_pct=0.02,
    ),
    (ActivityLevel.LOW, CapSize.MID): BacktestPreset(
        name="low_mid", display_name="低波动+中盘",
        activity_level=ActivityLevel.LOW, cap_size=CapSize.MID,
        threshold=0.48, trailing_stop_pct=0.04, take_profit_pct=0.05,
        stop_loss_pct=0.02,
    ),
    (ActivityLevel.LOW, CapSize.SMALL): BacktestPreset(
        name="low_small", display_name="低波动+小盘",
        activity_level=ActivityLevel.LOW, cap_size=CapSize.SMALL,
        threshold=0.50, trailing_stop_pct=0.04, take_profit_pct=0.05,
        stop_loss_pct=0.03, max_hold_days=3,
    ),
    (ActivityLevel.LOW, CapSize.MICRO): BacktestPreset(
        name="low_micro", display_name="低波动+微盘",
        activity_level=ActivityLevel.LOW, cap_size=CapSize.MICRO,
        threshold=0.52, trailing_stop_pct=0.05, take_profit_pct=0.06,
        stop_loss_pct=0.03,
    ),
    (ActivityLevel.MEDIUM, CapSize.LARGE): BacktestPreset(
        name="medium_large", display_name="中等波动+大盘",
        activity_level=ActivityLevel.MEDIUM, cap_size=CapSize.LARGE,
        threshold=0.50, trailing_stop_pct=0.04, take_profit_pct=0.06,
        stop_loss_pct=0.03,
    ),
    (ActivityLevel.MEDIUM, CapSize.MID): BacktestPreset(
        name="growth_mid", display_name="成长中盘（中等波动+中盘）",
        activity_level=ActivityLevel.MEDIUM, cap_size=CapSize.MID,
        threshold=0.55, trailing_stop_pct=0.05, take_profit_pct=0.08,
        stop_loss_pct=0.03, partial_exit_enabled=True, partial_exit_pct=0.5,
    ),
    (ActivityLevel.MEDIUM, CapSize.SMALL): BacktestPreset(
        name="medium_small", display_name="中等波动+小盘",
        activity_level=ActivityLevel.MEDIUM, cap_size=CapSize.SMALL,
        threshold=0.57, trailing_stop_pct=0.06, take_profit_pct=0.10,
        stop_loss_pct=0.04,
    ),
    (ActivityLevel.MEDIUM, CapSize.MICRO): BacktestPreset(
        name="medium_micro", display_name="中等波动+微盘",
        activity_level=ActivityLevel.MEDIUM, cap_size=CapSize.MICRO,
        threshold=0.58, trailing_stop_pct=0.06, take_profit_pct=0.10,
        stop_loss_pct=0.04,
    ),
    (ActivityLevel.HIGH, CapSize.LARGE): BacktestPreset(
        name="high_large", display_name="高波动+大盘",
        activity_level=ActivityLevel.HIGH, cap_size=CapSize.LARGE,
        threshold=0.55, trailing_stop_pct=0.06, take_profit_pct=0.10,
        stop_loss_pct=0.04,
    ),
    (ActivityLevel.HIGH, CapSize.MID): BacktestPreset(
        name="high_mid", display_name="高波动+中盘",
        activity_level=ActivityLevel.HIGH, cap_size=CapSize.MID,
        threshold=0.60, trailing_stop_pct=0.07, take_profit_pct=0.15,
        stop_loss_pct=0.05, min_ret_5d=0.03,
    ),
    (ActivityLevel.HIGH, CapSize.SMALL): BacktestPreset(
        name="tech_small", display_name="科技小盘（高波动+小盘）",
        activity_level=ActivityLevel.HIGH, cap_size=CapSize.SMALL,
        threshold=0.62, trailing_stop_pct=0.08, take_profit_pct=0.18,
        stop_loss_pct=0.05,
    ),
    (ActivityLevel.HIGH, CapSize.MICRO): BacktestPreset(
        name="high_micro", display_name="高波动+微盘",
        activity_level=ActivityLevel.HIGH, cap_size=CapSize.MICRO,
        threshold=0.63, trailing_stop_pct=0.08, take_profit_pct=0.18,
        stop_loss_pct=0.06, max_hold_days=12,
    ),
    (ActivityLevel.EXTREME, CapSize.LARGE): BacktestPreset(
        name="extreme_large", display_name="极端波动+大盘",
        activity_level=ActivityLevel.EXTREME, cap_size=CapSize.LARGE,
        threshold=0.58, trailing_stop_pct=0.07, take_profit_pct=0.12,
        stop_loss_pct=0.05,
    ),
    (ActivityLevel.EXTREME, CapSize.MID): BacktestPreset(
        name="extreme_mid", display_name="极端波动+中盘",
        activity_level=ActivityLevel.EXTREME, cap_size=CapSize.MID,
        threshold=0.62, trailing_stop_pct=0.08, take_profit_pct=0.16,
        stop_loss_pct=0.06,
    ),
    (ActivityLevel.EXTREME, CapSize.SMALL): BacktestPreset(
        name="quant_active", display_name="量化活跃（极端波动+小盘）",
        activity_level=ActivityLevel.EXTREME, cap_size=CapSize.SMALL,
        threshold=0.65, trailing_stop_pct=0.10, take_profit_pct=0.20,
        stop_loss_pct=0.07,
    ),
    (ActivityLevel.EXTREME, CapSize.MICRO): BacktestPreset(
        name="extreme_micro", display_name="极端波动+微盘",
        activity_level=ActivityLevel.EXTREME, cap_size=CapSize.MICRO,
        threshold=0.68, trailing_stop_pct=0.12, take_profit_pct=0.22,
        stop_loss_pct=0.08,
    ),
}


class BacktestPresets:
    """参数预设管理器 (FR-011)."""

    @staticmethod
    def all() -> list[BacktestPreset]:
        return list(_PRESETS.values())

    @staticmethod
    def get(key: tuple[ActivityLevel, CapSize]) -> Optional[BacktestPreset]:
        return _PRESETS.get(key)

    @staticmethod
    def blue_chip() -> BacktestPreset:
        return _PRESETS[(ActivityLevel.LOW, CapSize.LARGE)]

    @staticmethod
    def growth_mid() -> BacktestPreset:
        return _PRESETS[(ActivityLevel.MEDIUM, CapSize.MID)]

    @staticmethod
    def tech_small() -> BacktestPreset:
        return _PRESETS[(ActivityLevel.HIGH, CapSize.SMALL)]

    @staticmethod
    def quant_active() -> BacktestPreset:
        return _PRESETS[(ActivityLevel.EXTREME, CapSize.SMALL)]

    @staticmethod
    def from_stock(code: str, volatility: Optional[float] = None,
                   market_cap: Optional[float] = None) -> BacktestPreset:
        """根据股票属性自动匹配参数预设.

        Args:
            code: 股票代码
            volatility: 年化波动率 (可选，None 则默认 MEDIUM)
            market_cap: 市值(亿) (可选，None 则默认 MID)

        Returns:
            最匹配的 BacktestPreset
        """
        if volatility is None:
            activity = ActivityLevel.MEDIUM
        elif volatility < 0.2:
            activity = ActivityLevel.LOW
        elif volatility < 0.35:
            activity = ActivityLevel.MEDIUM
        elif volatility < 0.50:
            activity = ActivityLevel.HIGH
        else:
            activity = ActivityLevel.EXTREME

        if market_cap is None:
            cap = CapSize.MID
        elif market_cap > 500:
            cap = CapSize.LARGE
        elif market_cap > 100:
            cap = CapSize.MID
        elif market_cap > 30:
            cap = CapSize.SMALL
        else:
            cap = CapSize.MICRO

        return _PRESETS.get((activity, cap), BacktestPresets.growth_mid())

    @staticmethod
    def list_names() -> list[str]:
        return [p.name for p in _PRESETS.values()]
