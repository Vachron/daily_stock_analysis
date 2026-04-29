# -*- coding: utf-8 -*-
"""AIPredictionStrategy — AI 预测信号驱动策略 (FR-003)."""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from src.backtest.strategy import BacktestStrategy


class AIPredictionStrategy(BacktestStrategy):
    """基于 AI 预测信号的回测策略 (FR-003).

    支持多维信号过滤:
    - 上涨概率 (threshold)
    - 置信度 (min_confidence)
    - 5日预期收益 (min_ret_5d)

    仓位管理:
    - full: 满仓
    - signal: 按信号强度 (概率 × 置信度)
    """

    def __init__(
        self,
        threshold: float = 0.55,
        min_confidence: Optional[float] = None,
        min_ret_5d: Optional[float] = None,
        position_sizing: str = "full",
        predictions: Optional[Dict[str, List[dict]]] = None,
    ) -> None:
        super().__init__()
        self._threshold = threshold
        self._min_confidence = min_confidence
        self._min_ret_5d = min_ret_5d
        self._position_sizing = position_sizing
        self._predictions = predictions or {}

    def init(self) -> None:
        pass

    def next(self, i: int) -> None:
        if self.data is None:
            return
        date_str = str(self.data.index[i])[:10] if hasattr(self.data.index[i], "strftime") else str(self.data.index[i])[:10]
        preds = self._predictions.get(date_str, [])

        if not preds:
            return

        pred = preds[0]
        up_prob = float(pred.get("up_probability", 0))
        confidence = float(pred.get("confidence", 0))
        avg_ret_5d = float(pred.get("avg_ret_5d", 0))

        if up_prob < self._threshold:
            return
        if self._min_confidence is not None and confidence < self._min_confidence:
            return
        if self._min_ret_5d is not None and avg_ret_5d < self._min_ret_5d:
            return

        has_position = any(not t._is_closed for t in self.trades)
        if has_position:
            return

        if self._position_sizing == "full":
            self.buy(tag=f"ai_signal_p={up_prob:.2f}")
        elif self._position_sizing == "signal":
            strength = up_prob * confidence
            size_pct = max(0.0, min(1.0, strength))
            if self.data.Close[i] > 0 and self.equity > 0:
                max_shares = int(self.equity * size_pct / self.data.Close[i])
                if max_shares > 0:
                    self.buy(size=max_shares, tag=f"ai_signal_s={strength:.2f}")
