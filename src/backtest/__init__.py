# -*- coding: utf-8 -*-
"""回测引擎模块 (v2).

基于 PRD-backtest-optimization.md 设计的专业量化回测引擎。
参考 backtesting.py / mizar-alpha / QSTrader 的设计模式，独立实现。

模块结构:
- order.py: Order / Trade / Position 数据类
- strategy.py: BacktestStrategy 抽象基类
- broker.py: _Broker 模拟经纪商
- stats.py: compute_stats() 统计引擎
- engine.py: Backtest 主类
- optimizer.py: 参数优化器
- plotting.py: HTML 报告生成
- presets.py: BacktestPresets 参数预设
- exit_rules.py: ExitRule / ExitReason 平仓规则
- position_sizing.py: 仓位管理策略
- lib.py: 辅助函数
"""

from src.backtest.order import Order, Trade, Position
from src.backtest.strategy import BacktestStrategy
from src.backtest.broker import _Broker
from src.backtest.stats import compute_stats
from src.backtest.engine import (
    Backtest,
    BacktestResult,
    BacktestError,
    InsufficientDataError,
    StrategyError,
    BrokerError,
    StatsError,
)
from src.backtest.exit_rules import ExitRule, ExitReason
from src.backtest.position_sizing import PositionSizing
from src.backtest.presets import BacktestPresets, ActivityLevel, CapSize, BacktestPreset
from src.backtest.lib import (
    crossover,
    crossunder,
    SMA,
    EMA,
    RSI,
    MACD,
    ATR,
    resample_apply,
    random_ohlc_data,
)

__all__ = [
    "Backtest",
    "BacktestResult",
    "BacktestError",
    "InsufficientDataError",
    "StrategyError",
    "BrokerError",
    "StatsError",
    "BacktestStrategy",
    "Order",
    "Trade",
    "Position",
    "ExitRule",
    "ExitReason",
    "PositionSizing",
    "BacktestPresets",
    "ActivityLevel",
    "CapSize",
    "BacktestPreset",
    "compute_stats",
    "crossover",
    "crossunder",
    "SMA",
    "EMA",
    "RSI",
    "MACD",
    "ATR",
    "resample_apply",
    "random_ohlc_data",
]

__version__ = "v2"
