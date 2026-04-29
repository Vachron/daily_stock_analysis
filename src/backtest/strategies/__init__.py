# -*- coding: utf-8 -*-
"""内置可组合策略."""

from src.backtest.strategies.signal_strategy import SignalStrategy
from src.backtest.strategies.trailing_strategy import TrailingStrategy
from src.backtest.strategies.ai_prediction_strategy import AIPredictionStrategy

__all__ = [
    "SignalStrategy",
    "TrailingStrategy",
    "AIPredictionStrategy",
]
