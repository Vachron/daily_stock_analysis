# -*- coding: utf-8 -*-
"""Alpha system CLI — run alpha prediction, portfolio simulation, and evaluation."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.alpha.alpha_evaluator import AlphaEvaluator, AlphaMetrics
from src.alpha.alpha_scorer import AlphaScorer, AlphaPrediction, make_default_history_provider
from src.alpha.factor_model import FactorModel, StrategyTemplate
from src.alpha.portfolio_simulator import PortfolioConfig, PortfolioSimulator

logger = logging.getLogger(__name__)

DEFAULT_STRATEGY_DIR = str(Path(__file__).parent.parent.parent / "strategies")
DEFAULT_STRATEGY_NAMES = [
    "bottom_volume", "bull_trend", "emotion_cycle",
    "momentum_reversal", "ma_golden_cross",
]


def run_alpha_pipeline(
    start_date: date,
    end_date: date,
    strategy_dir: str = DEFAULT_STRATEGY_DIR,
    strategy_names: Optional[List[str]] = None,
    benchmark_code: str = "000300",
    top_n: int = 20,
    rebalance_days: int = 5,
    initial_capital: float = 1_000_000.0,
    pool_size: int = 500,
    progress_callback: Optional[callable] = None,
) -> Dict[str, Any]:
    names = strategy_names or DEFAULT_STRATEGY_NAMES

    if progress_callback:
        progress_callback(0, "Loading strategies...")
    strategies = FactorModel.load_strategies(strategy_dir, names=names)
    stats = FactorModel.get_factor_stats(strategies)
    logger.info("Loaded %d strategies, %d parameterized, %d total factors",
                stats["total_strategies"], stats["parameterized_strategies"], stats["total_factors"])

    if progress_callback:
        progress_callback(5, "Fetching benchmark data...")
    from data_provider.benchmark_fetcher import get_benchmark_nav_series
    benchmark_nav = get_benchmark_nav_series(
        code=benchmark_code, start_date=start_date - timedelta(days=5), end_date=end_date,
    )

    if progress_callback:
        progress_callback(10, "Building candidate pool...")
    try:
        from src.core.stock_pool import StockPoolInitializer
        pool = StockPoolInitializer.get_instance()
        entries = pool.get_pool_codes(limit=pool_size)
        pool_codes = [e["code"] for e in entries]
        name_map = {e["code"]: e.get("name", "") for e in entries}
    except Exception:
        logger.warning("Stock pool unavailable, using screener fallback")
        pool_codes = []
        name_map = {}

    neutralizer = None
    try:
        from src.alpha.risk_neutralizer import RiskNeutralizer
        neutralizer = RiskNeutralizer.from_stock_pool()
        logger.info("Risk neutralizer loaded: %d industries tracked",
                     len(set(neutralizer.industry_map.values())))
    except Exception as e:
        logger.warning("Risk neutralizer unavailable: %s", e)

    if progress_callback:
        progress_callback(15, "Fetching trading calendar...")
    trade_dates = _get_trading_calendar(start_date, end_date)

    scorer = AlphaScorer(pool_codes=pool_codes)
    history_provider = make_default_history_provider()

    default_values = {s.name: FactorModel.get_default_values(s) for s in strategies}

    alphas_by_date: Dict[date, List[AlphaPrediction]] = {}
    total_dates = len(trade_dates)
    for i, td in enumerate(trade_dates):
        if progress_callback and i % 10 == 0:
            pct = 15 + (i / total_dates) * 55
            progress_callback(pct, "Scoring: %s (%d/%d)" % (td, i + 1, total_dates))

        try:
            alphas = scorer.score_cross_section(
                target_date=td,
                strategies=strategies,
                factor_values=default_values,
                history_provider=history_provider,
                name_map=name_map,
            )
            if neutralizer is not None and alphas:
                alphas = neutralizer.neutralize(alphas)
            alphas_by_date[td] = alphas
        except Exception as e:
            logger.warning("Alpha scoring failed for %s: %s", td, e)

    if progress_callback:
        progress_callback(75, "Running portfolio simulation...")
    config = PortfolioConfig(
        initial_capital=initial_capital,
        max_positions=top_n,
        rebalance_freq_days=rebalance_days,
    )
    simulator = PortfolioSimulator(config=config)
    nav_df, snapshots, trades = simulator.simulate(
        alphas_by_date=alphas_by_date,
        price_data={},
        benchmark_nav=benchmark_nav,
        start_date=start_date,
        end_date=end_date,
    )

    if progress_callback:
        progress_callback(90, "Computing alpha metrics...")
    metrics = AlphaEvaluator.evaluate(nav_df, benchmark_nav)

    report = AlphaEvaluator.print_report(metrics)
    print(report)

    result: Dict[str, Any] = {
        "metrics": {
            "total_return_pct": metrics.total_return_pct,
            "annualized_return_pct": metrics.annualized_return_pct,
            "max_drawdown_pct": metrics.max_drawdown_pct,
            "sharpe_ratio": metrics.sharpe_ratio,
            "excess_return_pct": metrics.excess_return_pct,
            "information_ratio": metrics.information_ratio,
            "tracking_error_pct": metrics.tracking_error_pct,
        },
        "strategy_stats": stats,
        "num_trading_days": metrics.num_trading_days,
        "num_trades": len(trades),
        "final_nav": float(nav_df["nav"].iloc[-1]) if not nav_df.empty else 0.0,
        "risk_neutralization": {
            "enabled": neutralizer is not None,
            "industries_tracked": len(set(neutralizer.industry_map.values())) if neutralizer else 0,
        },
    }

    if neutralizer is not None and snapshots:
        last_snapshot_alphas = alphas_by_date.get(
            max(alphas_by_date.keys()), []
        ) if alphas_by_date else []
        if last_snapshot_alphas:
            exposures = neutralizer.get_industry_exposures(last_snapshot_alphas)
            result["industry_exposures"] = exposures
            if exposures:
                print("\n  行业暴露（中性化后）:")
                for ind, data in sorted(exposures.items(), key=lambda x: x[1]["mean_alpha"], reverse=True):
                    bar = "＋" * max(0, int(data["mean_alpha"] * 10)) if data["mean_alpha"] > 0 else "－" * min(0, int(abs(data["mean_alpha"]) * 10))
                    print("    %-10s n=%3d  α=%+6.4f  %s" % (ind, data["count"], data["mean_alpha"], bar))

    if progress_callback:
        progress_callback(100, "Complete")

    return result


def run_alpha_auto_optimize(
    start_date: date,
    end_date: date,
    strategy_dir: str = DEFAULT_STRATEGY_DIR,
    strategy_names: Optional[List[str]] = None,
    benchmark_code: str = "000300",
    top_n: int = 20,
    pool_size: int = 500,
    max_iterations: int = 50,
    early_stop_rounds: int = 10,
) -> Dict[str, Any]:
    """Bayesian-style auto-optimization of factor parameters."""
    from src.alpha.factor_debug_env import AgentAction, EnvConfig, FactorDebugEnv

    config = EnvConfig(
        start_date=start_date,
        end_date=end_date,
        strategies=strategy_names or DEFAULT_STRATEGY_NAMES,
        strategy_dir=strategy_dir,
        benchmark_code=benchmark_code,
        top_n=top_n,
        pool_size=pool_size,
        max_iterations=max_iterations,
        early_stop_rounds=early_stop_rounds,
    )

    env = FactorDebugEnv()
    state = env.reset(config)
    logger.info("Auto-optimize: %d strategies, %d total factors, %d max iterations",
                len(state.strategies), sum(len(s.factors) for s in state.strategies.values()), max_iterations)

    actions = env.get_action_space()
    print("\n  因子搜索空间 (%d 维度):" % len(actions))
    for a in actions:
        if a["action_type"] == "modify_factor":
            print("    %-30s %-20s %8.4f [%s..%s]" % (
                a["strategy"], a["factor_id"], a["current_value"], a["range"][0], a["range"][1],
            ))
    print()

    for iteration in range(max_iterations):
        if env.is_done():
            print("\n[EARLY STOP] No improvement for %d rounds" % env.state.no_improvement_count)
            break

        actions = env.get_action_space()
        factor_actions = [a for a in actions if a["action_type"] == "modify_factor"]
        weight_actions = [a for a in actions if a["action_type"] == "modify_weight"]

        import random
        import numpy as np

        n_changes = min(3, len(factor_actions))
        selected = random.sample(factor_actions, n_changes)

        for fa in selected:
            lo, hi = fa["range"]
            step = fa.get("step", 0.01)
            noise = np.random.normal(0, (hi - lo) * 0.1)
            new_val = fa["current_value"] + noise
            new_val = max(lo, min(hi, round(new_val / step) * step))
            env.step(AgentAction(
                action_type="modify_factor",
                strategy_name=fa["strategy"],
                factor_id=fa["factor_id"],
                new_value=new_val,
            ))

        state, reward, info = env.step(AgentAction(action_type="run_simulation"))

        best_ir = getattr(state.best_metrics, 'information_ratio', 0) if state.best_metrics else 0
        current_ir = info.get("metrics", {}).get("information_ratio", 0)
        print("  [Iter %3d/%d] IR=%.4f BestIR=%.4f Reward=%+.4f NoImpr=%d" % (
            state.iteration, max_iterations, current_ir, best_ir, reward, state.no_improvement_count,
        ))

    output_path = "data/optimized_strategies/alpha_best_config_%s.json" % datetime.now().strftime("%Y%m%d_%H%M%S")
    env.save_best_config(output_path)
    print("\n[OPTIMIZE DONE] Best config saved to: %s" % output_path)
    print(env.render())

    return {
        "status": "ok",
        "iterations": state.iteration,
        "best_ir": getattr(state.best_metrics, 'information_ratio', 0),
        "best_excess": getattr(state.best_metrics, 'excess_return_pct', 0),
        "config_path": output_path,
    }


def run_factor_health_check(
    strategy_dir: str = DEFAULT_STRATEGY_DIR,
    strategy_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    from src.alpha.factor_monitor import FactorMonitor
    from src.alpha.factor_model import FactorModel

    names = strategy_names or DEFAULT_STRATEGY_NAMES
    strategies = FactorModel.load_strategies(strategy_dir, names=names)

    monitor = FactorMonitor()
    monitor.load_history()
    report = monitor.get_health_report(strategies)
    rotations = monitor.suggest_rotation(strategies)

    print("\n" + "=" * 60)
    print("  因子健康检查报告")
    print("=" * 60)
    print("  %s" % report.summary)
    print("-" * 60)

    for fh in report.factors:
        icon = {"healthy": "[OK]", "warning": "[WARN]", "aged": "[AGED]"}.get(fh.status, "[?]")
        print("  %-6s %-15s %-25s IC=%+.4f  IR=%.2f  %s" % (
            icon, fh.strategy_name, fh.factor_id, fh.recent_ic, fh.ic_ir,
            "(aging %d periods)" % fh.aged_periods if fh.is_aged else "",
        ))

    if rotations:
        print("-" * 60)
        print("  轮换建议:")
        for r in rotations:
            print("    → %s:%s — %s" % (r["strategy"], r["factor"], r["message"]))

    print("=" * 60)

    return {
        "status": "ok",
        "healthy": report.healthy_count,
        "aged": report.aged_count,
        "total_factors": report.total_factors,
        "factors": [
            {"strategy": f.strategy_name, "factor": f.factor_id, "ic": f.recent_ic, "ic_ir": f.ic_ir, "status": f.status}
            for f in report.factors
        ],
        "rotations": rotations,
    }


def run_strategy_search(
    start_date: date,
    end_date: date,
    strategy_dir: str = DEFAULT_STRATEGY_DIR,
    max_strategies: int = 8,
    benchmark_code: str = "000300",
    top_n: int = 20,
    pool_size: int = 500,
) -> Dict[str, Any]:
    from src.alpha.factor_model import FactorModel
    from src.alpha.strategy_combiner import StrategyCombiner

    all_strategies = FactorModel.load_strategies(strategy_dir)

    print("\n" + "=" * 60)
    print("  多策略组合搜索")
    print("=" * 60)
    print("  候选策略: %d 个, 最大组合: %d" % (len(all_strategies), max_strategies))
    print("-" * 60)

    combiner = StrategyCombiner(max_strategies=max_strategies)
    result = combiner.search(
        all_strategies=all_strategies,
        start_date=start_date,
        end_date=end_date,
        benchmark_code=benchmark_code,
        top_n=top_n,
        pool_size=pool_size,
    )

    print("-" * 60)
    print("  最优组合 (%d 策略):" % len(result.strategies))
    for name in result.strategies:
        print("    %s (权重=%.2f)" % (name, result.weights.get(name, 0)))
    print("  IR=%.4f  Excess=%.2f%%  Sharpe=%.2f" % (
        result.information_ratio, result.excess_return_pct, result.sharpe_ratio,
    ))
    print("=" * 60)

    return {
        "status": "ok",
        "strategies": result.strategies,
        "weights": result.weights,
        "information_ratio": result.information_ratio,
        "excess_return_pct": result.excess_return_pct,
        "sharpe_ratio": result.sharpe_ratio,
        "iterations": result.iterations,
    }


def _get_trading_calendar(start: date, end: date) -> List[date]:
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        if df is None or df.empty:
            return _fallback_calendar(start, end)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        dates = df[(df["trade_date"] >= pd.Timestamp(start)) & (df["trade_date"] <= pd.Timestamp(end))]
        return sorted(dates["trade_date"].dt.date.tolist())
    except Exception:
        return _fallback_calendar(start, end)


def _fallback_calendar(start: date, end: date) -> List[date]:
    from pandas.tseries.offsets import BDay
    return [d.date() for d in pd.date_range(start, end, freq=BDay())]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    result = run_alpha_pipeline(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    print("\nResult:", json.dumps(result, ensure_ascii=False, indent=2, default=str))
