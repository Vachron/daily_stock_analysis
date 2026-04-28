# -*- coding: utf-8 -*-
"""Portfolio backtest engine — strategy-driven multi-asset backtesting with local K-line data.

Reuses StrategySignalExtractor for scoring, PortfolioSimulator for rebalancing,
AlphaEvaluator for metrics. Adds user-configurable parameters.

Usage:
    engine = PortfolioBacktestEngine()
    result = engine.run(
        initial_capital=100_000,
        start_date=date(2024, 1, 1),
        end_date=date(2025, 12, 31),
        factor_values={...},
        max_positions=10,
        rebalance_freq_days=5,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BacktestParams:
    initial_capital: float = 100_000.0
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    max_positions: int = 10
    rebalance_freq_days: int = 5
    benchmark_code: str = "000300"
    factor_values: Optional[Dict[str, Dict[str, float]]] = None
    strategy_names: Optional[List[str]] = None
    pool_codes: Optional[List[str]] = None
    pool_size: int = 500
    commission_rate: float = 0.0003
    slippage_pct: float = 0.001


@dataclass
class BacktestResult:
    success: bool = False
    error: Optional[str] = None
    run_id: str = ""
    nav_df: Optional[pd.DataFrame] = None
    trades: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    params: Optional[BacktestParams] = None
    elapsed_seconds: float = 0.0


class PortfolioBacktestEngine:

    DEFAULT_STRATEGY_NAMES = [
        "bottom_volume", "bull_trend", "emotion_cycle",
        "momentum_reversal", "ma_golden_cross",
    ]

    def __init__(self):
        self._kline_repo = None

    @property
    def kline_repo(self):
        if self._kline_repo is None:
            from data_provider.kline_repo import KlineRepo
            self._kline_repo = KlineRepo()
        return self._kline_repo

    @property
    def ready(self) -> bool:
        return self.kline_repo.ready

    def run(self, params: BacktestParams) -> BacktestResult:
        import time
        t0 = time.time()

        if not self.kline_repo.ready:
            return BacktestResult(
                success=False,
                error="K-line data not available. Run import_kline.py first.",
                params=params,
            )

        try:
            from src.alpha.factor_model import FactorModel
            from src.core.screener_engine import ScreenerEngine
            from src.core.market_regime import MarketRegimeDetector, DynamicWeightAdjuster
            from src.alpha.alpha_scorer import AlphaScorer, AlphaPrediction
            from src.alpha.portfolio_simulator import PortfolioConfig, PortfolioSimulator
            from src.alpha.alpha_evaluator import AlphaEvaluator
            from data_provider.benchmark_fetcher import get_benchmark_nav_series
        except ImportError as e:
            return BacktestResult(success=False, error=f"Import error: {e}", params=params)

        start = params.start_date or date.today() - timedelta(days=365)
        end = params.end_date or date.today()
        strategy_names = params.strategy_names or self.DEFAULT_STRATEGY_NAMES

        strategy_dir = str(__import__('pathlib').Path(__file__).parent.parent.parent / "strategies")
        strategies = FactorModel.load_strategies(strategy_dir, names=strategy_names)
        scorer = AlphaScorer(pool_codes=params.pool_codes or [])

        factor_values = params.factor_values or {
            s.name: FactorModel.get_default_values(s) for s in strategies
        }

        trade_dates = self._get_trading_dates(start, end)
        if not trade_dates:
            return BacktestResult(success=False, error="No trading dates found", params=params)

        alphas_by_date: Dict[date, List] = {}
        for i, td in enumerate(trade_dates):
            if i % 50 == 0:
                logger.info("Backtest scoring: %d/%d (%s)", i + 1, len(trade_dates), td)

            market_df = self.kline_repo.get_cross_section(td.year, td.month, td.day)
            if market_df is None or market_df.empty:
                continue

            alphas = scorer.score_cross_section(
                target_date=td,
                strategies=strategies,
                factor_values=factor_values,
                market_data=market_df,
            )
            alphas_by_date[td] = alphas

        benchmark_nav = get_benchmark_nav_series(
            code=params.benchmark_code,
            start_date=start - timedelta(days=5),
            end_date=end,
        )

        config = PortfolioConfig(
            initial_capital=params.initial_capital,
            max_positions=params.max_positions,
            rebalance_freq_days=params.rebalance_freq_days,
            commission_rate=params.commission_rate,
            slippage_pct=params.slippage_pct,
        )

        price_data = {}
        if params.pool_codes:
            for code in params.pool_codes:
                df = self.kline_repo.get_history(code, start, end)
                if df is not None and not df.empty:
                    price_data[code] = df

        simulator = PortfolioSimulator(config=config)
        nav_df, snapshots, trade_records = simulator.simulate(
            alphas_by_date=alphas_by_date,
            price_data=price_data,
            benchmark_nav=benchmark_nav,
            start_date=start,
            end_date=end,
        )

        metrics = AlphaEvaluator.evaluate(nav_df, benchmark_nav)

        trades_list = []
        for tr in trade_records:
            trades_list.append({
                "date": tr.date.isoformat() if hasattr(tr, 'date') else str(tr.date),
                "code": tr.code,
                "action": tr.action,
                "shares": int(tr.shares) if hasattr(tr, 'shares') else 0,
                "price": float(tr.price) if hasattr(tr, 'price') else 0,
                "cost": float(tr.cost) if hasattr(tr, 'cost') else 0,
                "reason": tr.reason,
            })

        elapsed = time.time() - t0

        return BacktestResult(
            success=True,
            run_id=f"bt_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}",
            nav_df=nav_df,
            trades=trades_list,
            metrics={
                "total_return_pct": metrics.total_return_pct,
                "annualized_return_pct": metrics.annualized_return_pct,
                "max_drawdown_pct": metrics.max_drawdown_pct,
                "sharpe_ratio": metrics.sharpe_ratio,
                "excess_return_pct": metrics.excess_return_pct,
                "information_ratio": metrics.information_ratio,
                "tracking_error_pct": metrics.tracking_error_pct,
                "win_rate_pct": metrics.win_rate_pct,
            },
            params=params,
            elapsed_seconds=round(elapsed, 1),
        )

    def run_scan(self, base_params: BacktestParams, param_ranges: Dict[str, List[float]]) -> List[Dict]:
        results = []
        combinations = self._expand_combinations(param_ranges)
        total = len(combinations)

        for i, combo in enumerate(combinations):
            logger.info("Param scan: %d/%d", i + 1, total)
            params = BacktestParams(**base_params.__dict__)
            if params.factor_values is None:
                params.factor_values = {}
            for key, val in combo.items():
                parts = key.split(".")
                strategy_name = parts[0]
                factor_id = parts[1]
                if strategy_name not in params.factor_values:
                    params.factor_values[strategy_name] = {}
                params.factor_values[strategy_name][factor_id] = val

            result = self.run(params)
            if result.success:
                results.append({
                    "params": combo,
                    "metrics": result.metrics,
                    "trades": len(result.trades),
                    "elapsed": result.elapsed_seconds,
                })

        results.sort(key=lambda x: x["metrics"].get("sharpe_ratio", 0), reverse=True)
        for i, r in enumerate(results):
            r["rank"] = i + 1

        return results

    def _expand_combinations(self, param_ranges: Dict[str, List[float]]) -> List[Dict[str, float]]:
        if not param_ranges:
            return []

        keys = list(param_ranges.keys())
        values = [param_ranges[k] for k in keys]
        combinations = []

        def _recurse(idx, current):
            if idx == len(keys):
                combinations.append(dict(current))
                return
            for v in values[idx]:
                current[keys[idx]] = v
                _recurse(idx + 1, current)

        _recurse(0, {})
        return combinations

    def _get_trading_dates(self, start: date, end: date) -> List[date]:
        if not self.kline_repo.ready:
            from pandas.tseries.offsets import BDay
            return [d.date() for d in pd.date_range(start, end, freq=BDay())]

        try:
            from data_provider.kline_repo import DAILY_DIR
            from pathlib import Path

            meta = self.kline_repo.get_meta()
            if meta.empty:
                return []

            all_dates = set()
            for pp in DAILY_DIR.glob("code_*.parquet"):
                try:
                    pf = pd.read_parquet(str(pp), columns=["date"])
                    all_dates.update(pf["date"].unique())
                except Exception:
                    continue

            origin = date(2000, 1, 1)
            dates = sorted(
                origin + timedelta(days=int(d))
                for d in all_dates
                if start <= origin + timedelta(days=int(d)) <= end
            )
            return dates
        except Exception:
            from pandas.tseries.offsets import BDay
            return [d.date() for d in pd.date_range(start, end, freq=BDay())]

    def get_statistics(self) -> Dict[str, Any]:
        return self.kline_repo.get_statistics()
