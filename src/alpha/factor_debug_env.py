# -*- coding: utf-8 -*-
"""Factor debug environment — RL-style interface for alpha strategy iteration.

Wraps the Alpha pipeline (scoring → neutralization → simulation → evaluation)
as an env with reset/step/render, enabling Agent to:
- Modify factor values per strategy
- Run simulation with modified factors
- Compare metrics between runs
- Auto-optimize via Bayesian optimization

Agent Action Types:
  modify_factor(strategy_name, factor_id, new_value)
  modify_strategy_weight(strategy_name, weight)
  run_simulation() → AlphaMetrics
  compare_runs(run_id_a, run_id_b)

Reward = α * IR_improvement + β * excess_return_improvement - γ * turnover_penalty
"""

from __future__ import annotations

import copy
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.alpha.alpha_evaluator import AlphaMetrics
from src.alpha.alpha_scorer import AlphaPrediction
from src.alpha.factor_model import FactorModel, StrategyTemplate

logger = logging.getLogger(__name__)

DEFAULT_REWARD_ALPHA = 1.0
DEFAULT_REWARD_BETA = 0.5
DEFAULT_REWARD_GAMMA = 0.3


@dataclass
class EnvConfig:
    start_date: date
    end_date: date
    strategies: List[str] = field(default_factory=lambda: [
        "bottom_volume", "bull_trend", "emotion_cycle",
        "momentum_reversal", "ma_golden_cross",
    ])
    strategy_dir: str = "strategies"
    benchmark_code: str = "000300"
    top_n: int = 20
    initial_capital: float = 1_000_000.0
    pool_size: int = 500
    max_iterations: int = 50
    early_stop_rounds: int = 10
    reward_alpha: float = DEFAULT_REWARD_ALPHA
    reward_beta: float = DEFAULT_REWARD_BETA
    reward_gamma: float = DEFAULT_REWARD_GAMMA


@dataclass
class EnvState:
    strategies: Dict[str, StrategyTemplate]
    factor_values: Dict[str, Dict[str, float]]
    strategy_weights: Dict[str, float]
    iteration: int = 0
    best_metrics: Optional[AlphaMetrics] = None
    best_factor_values: Optional[Dict[str, Dict[str, float]]] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    no_improvement_count: int = 0
    current_run_id: str = ""


@dataclass
class AgentAction:
    action_type: str  # "modify_factor" | "modify_weight" | "run_simulation" | "reset"
    strategy_name: str = ""
    factor_id: str = ""
    new_value: float = 0.0
    new_weight: float = 0.0


class FactorDebugEnv:
    def __init__(self):
        self.config: Optional[EnvConfig] = None
        self.state: Optional[EnvState] = None
        self._run_cache: Dict[str, Dict[str, Any]] = {}
        self._pipeline_fn: Optional[Callable] = None

    def reset(self, config: Optional[EnvConfig] = None) -> EnvState:
        if config:
            self.config = config

        if self.config is None:
            raise ValueError("No config provided")

        strategies = FactorModel.load_strategies(
            self.config.strategy_dir, names=self.config.strategies,
        )
        factor_values = {s.name: FactorModel.get_default_values(s) for s in strategies}
        strategy_weights = {s.name: s.weight for s in strategies}

        self.state = EnvState(
            strategies={s.name: s for s in strategies},
            factor_values=factor_values,
            strategy_weights=strategy_weights,
            current_run_id=str(uuid.uuid4())[:8],
        )
        return self.state

    def _run_pipeline(self) -> Dict[str, Any]:
        if self.state is None:
            raise RuntimeError("Environment not initialized")

        from src.alpha.cli import run_alpha_pipeline

        strategy_names = [s.name for s in self.state.strategies.values()]

        result = run_alpha_pipeline(
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            strategy_dir=self.config.strategy_dir,
            strategy_names=strategy_names,
            benchmark_code=str(self.config.benchmark_code),
            top_n=self.config.top_n,
            pool_size=self.config.pool_size,
            initial_capital=self.config.initial_capital,
        )

        self.state.current_run_id = str(uuid.uuid4())[:8]
        self._run_cache[self.state.current_run_id] = {
            "metrics": result.get("metrics", {}),
            "factor_values": copy.deepcopy(self.state.factor_values),
            "weights": copy.deepcopy(self.state.strategy_weights),
            "timestamp": datetime.now().isoformat(),
        }
        return result

    def step(self, action: AgentAction) -> Tuple[EnvState, float, Dict[str, Any]]:
        if self.state is None:
            raise RuntimeError("Environment not initialized")

        info: Dict[str, Any] = {"action": action.action_type}

        if action.action_type == "modify_factor":
            self._modify_factor(action.strategy_name, action.factor_id, action.new_value)
            info["message"] = "Factor %s.%s → %.4f" % (action.strategy_name, action.factor_id, action.new_value)
        elif action.action_type == "modify_weight":
            self._modify_weight(action.strategy_name, action.new_weight)
            info["message"] = "Weight %s → %.4f" % (action.strategy_name, action.new_weight)
        elif action.action_type == "run_simulation":
            try:
                result = self._run_pipeline()
                metrics_dict = result.get("metrics", {})
                info["metrics"] = metrics_dict
                info["message"] = "Simulation complete, IR=%.4f" % metrics_dict.get("information_ratio", 0)

                reward, prev_best, current = self._compute_reward(metrics_dict)
                info["reward"] = reward
                info["prev_best"] = prev_best

                self.state.history.append({
                    "iteration": self.state.iteration,
                    "metrics": metrics_dict,
                    "factor_values": copy.deepcopy(self.state.factor_values),
                    "reward": reward,
                })
                self.state.iteration += 1

                if current > prev_best:
                    self.state.best_metrics = self._dict_to_metrics(metrics_dict)
                    self.state.best_factor_values = copy.deepcopy(self.state.factor_values)
                    self.state.no_improvement_count = 0
                else:
                    self.state.no_improvement_count += 1

                info["no_improvement"] = self.state.no_improvement_count
                return self.state, reward, info
            except Exception as e:
                info["error"] = str(e)
                return self.state, -1.0, info
        elif action.action_type == "reset":
            self.reset()
            info["message"] = "Environment reset"

        return self.state, 0.0, info

    def _modify_factor(self, strategy_name: str, factor_id: str, new_value: float) -> None:
        if self.state is None:
            return
        tmpl = self.state.strategies.get(strategy_name)
        if tmpl is None:
            raise ValueError("Strategy '%s' not found" % strategy_name)
        factor = next((f for f in tmpl.factors if f.id == factor_id), None)
        if factor is None:
            raise ValueError("Factor '%s' not found in strategy '%s'" % (factor_id, strategy_name))
        clamped = factor.clamp(new_value)
        if strategy_name not in self.state.factor_values:
            self.state.factor_values[strategy_name] = {}
        self.state.factor_values[strategy_name][factor_id] = clamped
        if clamped != new_value:
            logger.info("Factor %s.%s clamped: %.4f → %.4f", strategy_name, factor_id, new_value, clamped)

    def _modify_weight(self, strategy_name: str, new_weight: float) -> None:
        if self.state is None:
            return
        self.state.strategy_weights[strategy_name] = max(0.1, min(new_weight, 5.0))

    def _compute_reward(self, metrics_dict: Dict[str, Any]) -> Tuple[float, float, float]:
        best_ir = getattr(self.state.best_metrics, 'information_ratio', 0) if self.state.best_metrics else 0
        best_excess = getattr(self.state.best_metrics, 'excess_return_pct', 0) if self.state.best_metrics else 0

        current_ir = metrics_dict.get("information_ratio", 0)
        current_excess = metrics_dict.get("excess_return_pct", 0)

        ir_improvement = current_ir - best_ir
        excess_improvement = (current_excess - best_excess) / max(abs(best_excess), 1.0)

        reward = (
            self.config.reward_alpha * ir_improvement * 100
            + self.config.reward_beta * excess_improvement * 10
        )
        return reward, best_ir, current_ir

    def render(self, format_type: str = "text") -> str:
        if self.state is None:
            return "Environment not initialized"

        lines = [
            "=" * 50,
            "  Factor Debug Environment",
            "=" * 50,
            "  Iteration: %d / %d" % (self.state.iteration, self.config.max_iterations),
            "  No-improvement: %d / %d" % (self.state.no_improvement_count, self.config.early_stop_rounds),
            "-" * 50,
            "  Strategies & Factors:",
        ]
        for name, tmpl in self.state.strategies.items():
            vals = self.state.factor_values.get(name, {})
            weight = self.state.strategy_weights.get(name, tmpl.weight)
            lines.append("    %s (weight=%.2f):" % (name, weight))
            for factor in tmpl.factors:
                val = vals.get(factor.id, factor.default)
                lines.append("      %-30s = %8.4f  [%.4f..%.4f]" % (
                    factor.id, val, factor.range[0], factor.range[1],
                ))
        lines.append("-" * 50)
        if self.state.best_metrics:
            lines.append("  Best Metrics:")
            lines.append("    IR: %.4f  Excess: %.2f%%" % (
                self.state.best_metrics.information_ratio,
                self.state.best_metrics.excess_return_pct,
            ))
        lines.append("-" * 50)
        if self.state.history:
            last = self.state.history[-1]
            m = last["metrics"]
            lines.append("  Last Run: IR=%.4f Excess=%.2f%% Reward=%.4f" % (
                m.get("information_ratio", 0),
                m.get("excess_return_pct", 0),
                last["reward"],
            ))
        lines.append("=" * 50)
        return "\n".join(lines)

    def is_done(self) -> bool:
        if self.state is None:
            return False
        if self.state.iteration >= self.config.max_iterations:
            return True
        if self.state.no_improvement_count >= self.config.early_stop_rounds:
            return True
        return False

    def get_action_space(self) -> List[Dict[str, Any]]:
        if self.state is None:
            return []

        actions: List[Dict[str, Any]] = []
        for name, tmpl in self.state.strategies.items():
            for factor in tmpl.factors:
                actions.append({
                    "action_type": "modify_factor",
                    "strategy": name,
                    "factor_id": factor.id,
                    "display_name": factor.display_name,
                    "factor_type": factor.type,
                    "range": list(factor.range),
                    "step": factor.step,
                    "current_value": self.state.factor_values.get(name, {}).get(factor.id, factor.default),
                })
            actions.append({
                "type": "modify_weight",
                "strategy": name,
                "current_weight": self.state.strategy_weights.get(name, tmpl.weight),
            })
        return actions

    def save_best_config(self, output_path: str) -> None:
        if self.state is None or self.state.best_factor_values is None:
            logger.warning("No best config to save")
            return

        config_data = {
            "timestamp": datetime.now().isoformat(),
            "iterations": self.state.iteration,
            "best_metrics": {
                "information_ratio": getattr(self.state.best_metrics, 'information_ratio', 0),
                "excess_return_pct": getattr(self.state.best_metrics, 'excess_return_pct', 0),
                "sharpe_ratio": getattr(self.state.best_metrics, 'sharpe_ratio', 0),
                "max_drawdown_pct": getattr(self.state.best_metrics, 'max_drawdown_pct', 0),
            },
            "strategies": {},
        }

        for name, vals in self.state.best_factor_values.items():
            tmpl = self.state.strategies[name]
            config_data["strategies"][name] = {
                "factor_values": vals,
                "weight": self.state.strategy_weights.get(name, tmpl.weight),
            }

        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        logger.info("Best config saved to %s", output_path)

    @staticmethod
    def _dict_to_metrics(d: Dict[str, Any]) -> AlphaMetrics:
        return AlphaMetrics(
            total_return_pct=float(d.get("total_return_pct", 0) or 0),
            annualized_return_pct=float(d.get("annualized_return_pct", 0) or 0),
            max_drawdown_pct=float(d.get("max_drawdown_pct", 0) or 0),
            sharpe_ratio=float(d.get("sharpe_ratio", 0) or 0),
            excess_return_pct=float(d.get("excess_return_pct", 0) or 0),
            information_ratio=float(d.get("information_ratio", 0) or 0),
            tracking_error_pct=float(d.get("tracking_error_pct", 0) or 0),
            max_excess_drawdown_pct=float(d.get("max_drawdown_pct", 0) or 0),
        )
