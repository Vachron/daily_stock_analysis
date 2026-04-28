# -*- coding: utf-8 -*-
"""Alpha debug tools — Agent-callable tools for factor iteration and optimization.

Integrates with the existing ToolRegistry pattern from src/agent/tools/registry.py.
Each tool wraps an operation on the FactorDebugEnv.

Tools:
- alpha_env_reset: reset the debug environment with new config
- alpha_env_status: view current strategies, factors, and best metrics
- alpha_modify_factor: change a strategy factor value
- alpha_modify_weight: change a strategy weight
- alpha_run_simulation: run full alpha pipeline with current config
- alpha_get_comparison: compare current vs best run
- alpha_get_best_config: export best found config
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_debug_env_instance: Any = None


def _get_env() -> Any:
    global _debug_env_instance
    if _debug_env_instance is None:
        from src.alpha.factor_debug_env import FactorDebugEnv
        _debug_env_instance = FactorDebugEnv()
    return _debug_env_instance


def handle_alpha_env_reset(from_date: str = "2023-01-01", to_date: str = "2025-12-31",
                           benchmark: str = "000300", top_n: int = 20) -> Dict[str, Any]:
    env = _get_env()
    from src.alpha.factor_debug_env import EnvConfig
    from datetime import date as _date

    config = EnvConfig(
        start_date=_date.fromisoformat(from_date),
        end_date=_date.fromisoformat(to_date),
        benchmark_code=benchmark,
        top_n=top_n,
    )
    try:
        state = env.reset(config)
        return {
            "status": "ok",
            "strategies_loaded": len(state.strategies),
            "total_factors": sum(len(s.factors) for s in state.strategies.values()),
            "render": env.render(),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def handle_alpha_env_status() -> str:
    env = _get_env()
    if env.state is None:
        return "Environment not initialized. Call alpha_env_reset first."
    return env.render()


def handle_alpha_modify_factor(strategy_name: str, factor_id: str, new_value: float) -> Dict[str, Any]:
    env = _get_env()
    if env.state is None:
        return {"status": "error", "error": "Environment not initialized"}

    tmpl = env.state.strategies.get(strategy_name)
    if tmpl is None:
        return {"status": "error", "error": "Strategy '%s' not found. Available: %s" % (
            strategy_name, list(env.state.strategies.keys()),
        )}

    factor = next((f for f in tmpl.factors if f.id == factor_id), None)
    if factor is None:
        return {"status": "error", "error": "Factor '%s' not found. Available: %s" % (
            factor_id, [f.id for f in tmpl.factors],
        )}

    old_val = env.state.factor_values.get(strategy_name, {}).get(factor_id, factor.default)
    if strategy_name not in env.state.factor_values:
        env.state.factor_values[strategy_name] = {}
    env.state.factor_values[strategy_name][factor_id] = float(new_value)

    return {
        "status": "ok",
        "strategy": strategy_name,
        "factor": factor_id,
        "old_value": old_val,
        "new_value": new_value,
        "range": list(factor.range),
    }


def handle_alpha_modify_weight(strategy_name: str, new_weight: float) -> Dict[str, Any]:
    env = _get_env()
    if env.state is None:
        return {"status": "error", "error": "Environment not initialized"}

    if strategy_name not in env.state.strategies:
        return {"status": "error", "error": "Strategy '%s' not found" % strategy_name}

    old_weight = env.state.strategy_weights.get(strategy_name, env.state.strategies[strategy_name].weight)
    env.state.strategy_weights[strategy_name] = float(new_weight)

    return {
        "status": "ok",
        "strategy": strategy_name,
        "old_weight": old_weight,
        "new_weight": new_weight,
    }


def handle_alpha_run_simulation() -> Dict[str, Any]:
    env = _get_env()
    if env.state is None:
        return {"status": "error", "error": "Environment not initialized"}

    from src.alpha.factor_debug_env import AgentAction

    try:
        action = AgentAction(action_type="run_simulation")
        state, reward, info = env.step(action)
        if "error" in info:
            return {"status": "error", "error": info["error"]}

        result = {
            "status": "ok",
            "reward": reward,
            "iteration": state.iteration,
            "no_improvement": state.no_improvement_count,
            "is_done": env.is_done(),
            "metrics": info.get("metrics", {}),
            "best_metrics": {
                "information_ratio": getattr(state.best_metrics, 'information_ratio', 0) if state.best_metrics else 0,
                "excess_return_pct": getattr(state.best_metrics, 'excess_return_pct', 0) if state.best_metrics else 0,
                "sharpe_ratio": getattr(state.best_metrics, 'sharpe_ratio', 0) if state.best_metrics else 0,
            },
            "render": env.render(),
        }

        if env.is_done():
            result["message"] = "Optimization complete! %d iterations, best IR=%.4f" % (
                state.iteration, result["best_metrics"]["information_ratio"],
            )

        return result
    except Exception as e:
        logger.exception("Simulation failed")
        return {"status": "error", "error": str(e)}


def handle_alpha_get_best_config() -> Dict[str, Any]:
    env = _get_env()
    if env.state is None or env.state.best_factor_values is None:
        return {"status": "error", "error": "No best config yet. Run at least one simulation."}

    best_vals = env.state.best_factor_values
    result: Dict[str, Any] = {
        "status": "ok",
        "strategies": {},
    }
    for name, tmpl in env.state.strategies.items():
        vals = best_vals.get(name, {})
        result["strategies"][name] = {
            "weight": env.state.strategy_weights.get(name, tmpl.weight),
            "factors": {fid: vals.get(fid, f.default) for fid, f in {
                f.id: f for f in tmpl.factors
            }.items()},
        }

    return result


def handle_alpha_action_space() -> Dict[str, Any]:
    env = _get_env()
    if env.state is None:
        return {"status": "error", "error": "Environment not initialized"}

    return {
        "status": "ok",
        "actions": env.get_action_space(),
    }
