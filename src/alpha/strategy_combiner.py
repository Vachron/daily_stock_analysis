# -*- coding: utf-8 -*-
"""Strategy combiner — search for optimal strategy subset and weight allocation.

Given N candidate strategies, search for the best combination that maximizes:
- Information Ratio (primary)
- Excess return (secondary)
- Subject to: max N strategies, min weight constraint

Uses greedy forward selection (efficient for large strategy space):
1. Start with 1 strategy, pick best
2. Add next best that improves IR the most
3. Stop when adding degrades IR or reaches max count
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.alpha.factor_model import FactorModel, StrategyTemplate

logger = logging.getLogger(__name__)


@dataclass
class CombinationResult:
    strategies: List[str] = field(default_factory=list)
    weights: Dict[str, float] = field(default_factory=dict)
    information_ratio: float = 0.0
    excess_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    iterations: int = 0


class StrategyCombiner:
    def __init__(
        self,
        max_strategies: int = 8,
        min_weight: float = 0.05,
        eval_sample_days: int = 60,
    ):
        self.max_strategies = max_strategies
        self.min_weight = min_weight
        self.eval_sample_days = eval_sample_days

    def search(
        self,
        all_strategies: List[StrategyTemplate],
        start_date: date,
        end_date: date,
        benchmark_code: str = "000300",
        top_n: int = 20,
        pool_size: int = 500,
        progress_callback: Optional[callable] = None,
    ) -> CombinationResult:
        from src.alpha.cli import run_alpha_pipeline

        n_total = len(all_strategies)
        logger.info("Strategy combiner: searching %d strategies, max=%d", n_total, self.max_strategies)

        if n_total <= 2:
            names = [s.name for s in all_strategies]
            n = len(names)
            weights = {name: 1.0 / n for name in names}

            if progress_callback:
                progress_callback(50, "Evaluating single combination...")
            result = run_alpha_pipeline(
                start_date=start_date, end_date=end_date,
                strategy_names=names, benchmark_code=benchmark_code,
                top_n=top_n, pool_size=pool_size,
            )
            metrics = result.get("metrics", {})
            return CombinationResult(
                strategies=names, weights=weights,
                information_ratio=metrics.get("information_ratio", 0),
                excess_return_pct=metrics.get("excess_return_pct", 0),
                sharpe_ratio=metrics.get("sharpe_ratio", 0),
                max_drawdown_pct=metrics.get("max_drawdown_pct", 0),
                iterations=1,
            )

        single_scores: List[Tuple[str, float]] = []
        for i, tmpl in enumerate(all_strategies):
            if progress_callback:
                progress_callback(10 + int(i / n_total * 30), "Evaluating: %s (%d/%d)" % (tmpl.name, i + 1, n_total))
            try:
                result = run_alpha_pipeline(
                    start_date=start_date, end_date=end_date,
                    strategy_names=[tmpl.name],
                    benchmark_code=benchmark_code,
                    top_n=top_n, pool_size=pool_size,
                )
                ir = result.get("metrics", {}).get("information_ratio", 0) or 0
                single_scores.append((tmpl.name, ir))
                logger.debug("  %s: IR=%.4f", tmpl.name, ir)
            except Exception as e:
                logger.warning("Failed to evaluate %s: %s", tmpl.name, e)

        single_scores.sort(key=lambda x: x[1], reverse=True)

        selected: List[str] = []
        best_ir = -999.0
        best_result: Optional[Dict[str, Any]] = None

        for i, (name, base_ir) in enumerate(single_scores):
            if len(selected) >= self.max_strategies:
                break

            initial = selected + [name]
            n_in = len(initial)
            weights = {n: 1.0 / n_in for n in initial}

            if progress_callback:
                progress_callback(40 + int(len(selected) / self.max_strategies * 50),
                                  "Combining: %d strategies (%s)" % (n_in, name))

            try:
                result = run_alpha_pipeline(
                    start_date=start_date, end_date=end_date,
                    strategy_names=initial,
                    benchmark_code=benchmark_code,
                    top_n=top_n, pool_size=pool_size,
                )
                current_ir = result.get("metrics", {}).get("information_ratio", 0) or 0

                if current_ir > best_ir:
                    best_ir = current_ir
                    selected.append(name)
                    best_result = result
                    logger.info("  Added %s: IR=%.4f (best=%.4f)", name, current_ir, best_ir)
                elif n_in <= 2:
                    selected.append(name)
                    if best_result is None:
                        best_result = result
                        best_ir = current_ir
                else:
                    logger.info("  Skipped %s: IR=%.4f < best=%.4f", name, current_ir, best_ir)
            except Exception as e:
                logger.warning("Combination failed for %s: %s", name, e)

        if progress_callback:
            progress_callback(90, "Search complete: %d strategies selected" % len(selected))

        if best_result is None or not selected:
            return CombinationResult(strategies=selected, weights={})

        metrics = best_result.get("metrics", {})
        n_selected = len(selected)
        weights = {n: 1.0 / n_selected for n in selected}

        logger.info("Best combination (%d strategies): IR=%.4f Excess=%.2f%%",
                     n_selected, metrics.get("information_ratio", 0), metrics.get("excess_return_pct", 0))
        for name in selected:
            score = next((s[1] for s in single_scores if s[0] == name), 0)
            logger.info("  %s: single IR=%.4f  weight=%.3f", name, score, weights[name])

        return CombinationResult(
            strategies=selected,
            weights=weights,
            information_ratio=metrics.get("information_ratio", 0),
            excess_return_pct=metrics.get("excess_return_pct", 0),
            sharpe_ratio=metrics.get("sharpe_ratio", 0),
            max_drawdown_pct=metrics.get("max_drawdown_pct", 0),
            iterations=len(single_scores),
        )

    def refine_weights(
        self,
        strategies: List[str],
        start_date: date,
        end_date: date,
        benchmark_code: str = "000300",
        samples: int = 10,
    ) -> Dict[str, float]:
        from src.alpha.cli import run_alpha_pipeline

        n = len(strategies)
        if n <= 1:
            return {strategies[0]: 1.0} if strategies else {}

        best_weights = {name: 1.0 / n for name in strategies}
        best_ir = -999.0

        for _ in range(samples):
            raw = np.random.dirichlet(np.ones(n), 1)[0]
            weights = {}
            for i, name in enumerate(strategies):
                w = max(self.min_weight, raw[i])
                weights[name] = w
            total = sum(weights.values())
            weights = {k: v / total for k, v in weights.items()}

            try:
                result = run_alpha_pipeline(
                    start_date=start_date, end_date=end_date,
                    strategy_names=list(weights.keys()),
                    benchmark_code=benchmark_code,
                )
                ir = result.get("metrics", {}).get("information_ratio", 0) or 0
                if ir > best_ir:
                    best_ir = ir
                    best_weights = weights
            except Exception:
                pass

        logger.info("Weight refinement: best IR=%.4f", best_ir)
        return best_weights
