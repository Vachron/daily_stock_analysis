# -*- coding: utf-8 -*-
"""Factor monitor — track IC history, detect aging, suggest factor rotation.

Core mechanism:
1. For each factor (per strategy), compute Rank IC against forward excess returns
2. Track IC history in a rolling window
3. When IC consecutively falls below threshold for N periods → mark as "aged"
4. Suggest replacement factors from the factor library
5. Persist IC history to JSON for cross-session tracking
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.alpha.alpha_evaluator import FactorICReport
from src.alpha.factor_model import FactorDefinition, StrategyTemplate

logger = logging.getLogger(__name__)

DEFAULT_IC_THRESHOLD = 0.02
DEFAULT_AGED_WINDOW = 12
DEFAULT_IC_HISTORY_PATH = "data/factor_ic_history.json"


@dataclass
class FactorHealth:
    factor_id: str
    strategy_name: str
    recent_ic: float = 0.0
    ic_ir: float = 0.0
    ic_trend: float = 0.0
    is_aged: bool = False
    aged_periods: int = 0
    status: str = "healthy"
    suggestion: str = ""


@dataclass
class MonitorReport:
    total_factors: int = 0
    healthy_count: int = 0
    aged_count: int = 0
    factors: List[FactorHealth] = field(default_factory=list)
    rotation_suggestions: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""


class FactorMonitor:
    def __init__(
        self,
        ic_threshold: float = DEFAULT_IC_THRESHOLD,
        aged_window: int = DEFAULT_AGED_WINDOW,
        history_path: str = DEFAULT_IC_HISTORY_PATH,
    ):
        self.ic_threshold = ic_threshold
        self.aged_window = aged_window
        self.history_path = Path(history_path)
        self.ic_history: Dict[str, Dict[str, List[float]]] = {}

    def load_history(self) -> Dict[str, Dict[str, List[float]]]:
        if self.history_path.exists():
            try:
                self.ic_history = json.loads(self.history_path.read_text(encoding="utf-8"))
                logger.info("Loaded IC history: %d strategies", len(self.ic_history))
            except Exception:
                self.ic_history = {}
        return self.ic_history

    def save_history(self) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text(json.dumps(self.ic_history, ensure_ascii=False, indent=2), encoding="utf-8")

    def update_ic(
        self,
        strategy_name: str,
        factor_id: str,
        factor_values: np.ndarray,
        forward_returns: np.ndarray,
    ) -> FactorICReport:
        from scipy.stats import spearmanr

        key = "%s:%s" % (strategy_name, factor_id)
        if strategy_name not in self.ic_history:
            self.ic_history[strategy_name] = {}
        if factor_id not in self.ic_history[strategy_name]:
            self.ic_history[strategy_name][factor_id] = []

        if len(factor_values) < 30 or len(forward_returns) < 30:
            return FactorICReport(factor_id=factor_id, aged_reason="样本不足（<30）")

        ic_val, _ = spearmanr(factor_values, forward_returns)
        ic_val = float(ic_val) if not np.isnan(ic_val) else 0.0

        self.ic_history[strategy_name][factor_id].append(round(ic_val, 6))
        if len(self.ic_history[strategy_name][factor_id]) > 100:
            self.ic_history[strategy_name][factor_id] = self.ic_history[strategy_name][factor_id][-100:]

        ic_series = self.ic_history[strategy_name][factor_id]
        ic_mean = np.mean(ic_series[-self.aged_window:]) if len(ic_series) >= self.aged_window else np.mean(ic_series)
        ic_std = np.std(ic_series[-self.aged_window:]) if len(ic_series) >= 2 else 0.01
        ic_ir = ic_mean / ic_std if ic_std > 0 else 0.0

        is_aged = False
        aged_reason = ""
        if len(ic_series) >= self.aged_window:
            recent = ic_series[-self.aged_window:]
            below = sum(1 for v in recent if abs(v) < self.ic_threshold)
            if below >= self.aged_window * 0.75:
                is_aged = True
                aged_reason = "IC 连续 %d/%d 期低于 %.3f" % (below, self.aged_window, self.ic_threshold)

        self.save_history()

        return FactorICReport(
            factor_id=factor_id,
            rank_ic=round(ic_val, 4),
            ic_ir=round(ic_ir, 4),
            ic_mean=round(ic_mean, 4),
            ic_std=round(ic_std, 4),
            ic_series=list(ic_series[-20:]),
            is_aged=is_aged,
            aged_reason=aged_reason,
        )

    def get_health_report(self, strategies: List[StrategyTemplate]) -> MonitorReport:
        factors: List[FactorHealth] = []
        aged_count = 0

        for tmpl in strategies:
            for factor in tmpl.factors:
                key = "%s:%s" % (tmpl.name, factor.id)
                ic_series = self.ic_history.get(tmpl.name, {}).get(factor.id, [])
                recent_ic = ic_series[-1] if ic_series else 0.0
                ic_mean = np.mean(ic_series[-self.aged_window:]) if len(ic_series) >= 2 else recent_ic
                ic_std = np.std(ic_series[-self.aged_window:]) if len(ic_series) >= 2 else 0.01
                ic_ir = ic_mean / ic_std if ic_std > 0 else 0.0

                ic_trend = 0.0
                if len(ic_series) >= 6:
                    x = np.arange(len(ic_series[-6:]))
                    y = np.array(ic_series[-6:])
                    if np.std(x) > 0 and np.std(y) > 0:
                        ic_trend = float(np.polyfit(x, y, 1)[0])

                is_aged = False
                aged_periods = 0
                status = "healthy"
                suggestion = ""

                if len(ic_series) >= self.aged_window:
                    recent = ic_series[-self.aged_window:]
                    aged_periods = sum(1 for v in recent if abs(v) < self.ic_threshold)
                    if aged_periods >= self.aged_window * 0.75:
                        is_aged = True
                        status = "aged"
                        suggestion = "建议轮换：尝试调整因子范围或更换因子"
                elif len(ic_series) >= 6:
                    recent_6 = ic_series[-6:]
                    if all(abs(v) < self.ic_threshold for v in recent_6):
                        status = "warning"
                        suggestion = "IC 偏低，持续观察"

                if is_aged:
                    aged_count += 1

                factors.append(FactorHealth(
                    factor_id=factor.id,
                    strategy_name=tmpl.name,
                    recent_ic=round(recent_ic, 4),
                    ic_ir=round(ic_ir, 4),
                    ic_trend=round(ic_trend, 6),
                    is_aged=is_aged,
                    aged_periods=aged_periods,
                    status=status,
                    suggestion=suggestion,
                ))

        factors.sort(key=lambda x: abs(x.recent_ic), reverse=True)
        healthy = sum(1 for f in factors if not f.is_aged)

        summary = "因子健康: %d/%d，老化: %d" % (healthy, len(factors), aged_count)
        if aged_count > 0:
            aged_names = [f.strategy_name + ":" + f.factor_id for f in factors if f.is_aged]
            summary += "，老化因子: %s" % ", ".join(aged_names[:5])

        return MonitorReport(
            total_factors=len(factors),
            healthy_count=healthy,
            aged_count=aged_count,
            factors=factors,
            summary=summary,
        )

    def suggest_rotation(self, strategies: List[StrategyTemplate]) -> List[Dict[str, Any]]:
        report = self.get_health_report(strategies)
        suggestions: List[Dict[str, Any]] = []

        for fh in report.factors:
            if fh.is_aged:
                tmpl = next((s for s in strategies if s.name == fh.strategy_name), None)
                if tmpl is None:
                    continue
                factor = next((f for f in tmpl.factors if f.id == fh.factor_id), None)
                if factor is None:
                    continue

                lo, hi = factor.range
                mid = (lo + hi) / 2
                suggestions.append({
                    "strategy": fh.strategy_name,
                    "factor": fh.factor_id,
                    "current_ic": fh.recent_ic,
                    "action": "widen_range",
                    "suggested_range": [max(lo * 1.5, lo - (hi - lo) * 0.5), min(hi * 0.5, hi + (hi - lo) * 0.5)],
                    "message": "调整搜索范围: [%.2f, %.2f] → 建议重新校准" % (lo, hi),
                })

        return suggestions
