# -*- coding: utf-8 -*-
"""参数优化器 (FR-012/013/014)."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
import multiprocessing

import numpy as np
import pandas as pd

from src.backtest.engine import Backtest, BacktestResult

logger = logging.getLogger(__name__)


def _optimize_single(args: Tuple[Backtest, Dict[str, Any], str]) -> Optional[Tuple[float, Dict[str, float], Dict[str, Any]]]:
    """单个参数组合的优化评估 (多进程 worker)."""
    bt, params, metric = args
    try:
        result = bt.run(**params)
        value = float(result.stats.get(metric, 0))
        return (value, params, {k: v for k, v in result.stats.items() if pd.notna(v)})
    except Exception as exc:
        logger.warning("优化评估失败: params=%s, error=%s", params, exc)
        return None


def optimize(
    bt: Backtest,
    maximize: str = "Sharpe Ratio",
    method: str = "grid",
    max_tries: Optional[int] = None,
    constraint: Optional[Callable] = None,
    n_jobs: int = 1,
    return_heatmap: bool = False,
    return_optimization: bool = False,
    **kwargs: Any,
) -> pd.Series:
    """参数优化入口.

    Args:
        bt: Backtest 实例
        maximize: 优化目标指标名
        method: 'grid' 或 'bayesian'
        max_tries: 最大尝试次数
        constraint: 约束函数，接收参数字典返回 bool
        n_jobs: 并行进程数 (仅 grid 支持)
        return_heatmap: 是否返回热力图数据
        return_optimization: 是否返回优化过程
        **kwargs: 参数范围

    Returns:
        最优参数的 stats Series
    """
    param_names = list(kwargs.keys())
    param_values = list(kwargs.values())

    if method == "grid":
        results, all_iterations = _grid_search(
            bt, param_names, param_values, maximize, constraint, max_tries, n_jobs,
        )
    elif method == "bayesian":
        results, all_iterations = _bayesian_search(
            bt, param_names, param_values, maximize, max_tries,
        )
    else:
        raise ValueError(f"Unknown optimization method: {method}")

    if not results:
        raise RuntimeError("优化未产生有效结果")

    best = max(results, key=lambda x: x[0])
    best_value, best_params, best_stats_dict = best
    best_stats = pd.Series(best_stats_dict)
    best_stats["_best_params"] = best_params
    best_stats["_best_value"] = best_value
    if return_heatmap:
        best_stats["_heatmap"] = _build_heatmap(all_iterations, param_names, maximize)
    if return_optimization:
        best_stats["_optimization_history"] = all_iterations

    return best_stats


def _grid_search(
    bt: Backtest,
    param_names: List[str],
    param_ranges: List[Any],
    maximize: str,
    constraint: Optional[Callable],
    max_tries: Optional[int],
    n_jobs: int = 1,
) -> Tuple[List[Tuple[float, Dict[str, float], Dict[str, Any]]], List[Dict[str, Any]]]:
    from itertools import product

    grid_points = []
    for r in param_ranges:
        if isinstance(r, range):
            grid_points.append(list(r))
        elif isinstance(r, list):
            grid_points.append(r)
        else:
            grid_points.append([r])

    all_combinations = list(product(*grid_points))
    if constraint:
        all_combinations = [
            combo for combo in all_combinations
            if constraint(**dict(zip(param_names, combo)))
        ]

    if max_tries and len(all_combinations) > max_tries:
        rng = np.random.RandomState(42)
        indices = rng.choice(len(all_combinations), max_tries, replace=False)
        all_combinations = [all_combinations[i] for i in indices]

    param_combos = [dict(zip(param_names, combo)) for combo in all_combinations]

    results: List[Tuple[float, Dict[str, float], Dict[str, Any]]] = []
    all_iterations: List[Dict[str, Any]] = []

    if n_jobs > 1 and len(param_combos) > 1:
        with multiprocessing.Pool(n_jobs) as pool:
            work_items = [(bt, p, maximize) for p in param_combos]
            for res in pool.imap_unordered(_optimize_single, work_items):
                if res is not None:
                    value, params, stats = res
                    results.append((value, params, stats))
                    all_iterations.append({"params": params, "value": value, "stats": stats})
    else:
        for params in param_combos:
            res = _optimize_single((bt, params, maximize))
            if res is not None:
                value, p, stats = res
                results.append((value, p, stats))
                all_iterations.append({"params": p, "value": value, "stats": stats})

    return results, all_iterations


def _bayesian_search(
    bt: Backtest,
    param_names: List[str],
    param_ranges: List[Any],
    maximize: str,
    max_tries: Optional[int],
) -> Tuple[List[Tuple[float, Dict[str, float], Dict[str, Any]]], List[Dict[str, Any]]]:
    n_tries = max_tries or 50
    n_random = max(5, n_tries // 5)

    results: List[Tuple[float, Dict[str, float], Dict[str, Any]]] = []
    all_iterations: List[Dict[str, Any]] = []

    bounds = []
    for r in param_ranges:
        if isinstance(r, range):
            bounds.append((r.start, r.stop - 1))
        elif isinstance(r, list):
            bounds.append((min(r), max(r)))
        else:
            bounds.append((r, r))

    rng = np.random.RandomState(42)

    for _ in range(n_random):
        params = {}
        for name, b in zip(param_names, bounds):
            params[name] = float(int(rng.uniform(b[0], b[1] + 1)))
        res = _optimize_single((bt, params, maximize))
        if res is not None:
            value, p, stats = res
            results.append((value, p, stats))
            all_iterations.append({"params": p, "value": value, "stats": stats})

    for _ in range(n_random, n_tries):
        if len(results) < 3:
            break
        sorted_results = sorted(results, key=lambda x: x[0], reverse=True)
        top = sorted_results[:max(3, len(sorted_results) // 4)]

        params = {}
        for name, b in zip(param_names, bounds):
            vals = [r[1][name] for r in top]
            mu = np.mean(vals)
            sigma = np.std(vals) * 0.5 + 0.5
            proposed = rng.normal(mu, sigma)
            params[name] = float(np.clip(round(proposed), b[0], b[1]))

        res = _optimize_single((bt, params, maximize))
        if res is not None:
            value, p, stats = res
            results.append((value, p, stats))
            all_iterations.append({"params": p, "value": value, "stats": stats})

    return results, all_iterations


def _build_heatmap(
    iterations: List[Dict[str, Any]],
    param_names: List[str],
    metric: str,
) -> Dict[str, Any]:
    if len(param_names) < 2:
        return {}
    x_param = param_names[0]
    y_param = param_names[1]
    heatmap: Dict[float, Dict[float, float]] = {}
    for it in iterations:
        x = it["params"].get(x_param)
        y = it["params"].get(y_param)
        v = it["value"]
        if x is not None and y is not None:
            heatmap.setdefault(x, {})[y] = v
    return {
        "x_param": x_param,
        "y_param": y_param,
        "data": heatmap,
        "metric": metric,
    }
