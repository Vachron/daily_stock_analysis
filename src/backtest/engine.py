# -*- coding: utf-8 -*-
"""Backtest 主类 (FR-001/002/006/012/013/021)."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import numpy as np
import pandas as pd

from src.backtest.order import Order, Trade, Position
from src.backtest.strategy import BacktestStrategy, _OHLCVData
from src.backtest.broker import _Broker
from src.backtest.stats import compute_stats
from src.backtest.exit_rules import ExitRule, ExitReason

logger = logging.getLogger(__name__)


class BacktestError(Exception):
    """回测引擎基类异常."""


class InsufficientDataError(BacktestError):
    """数据不足异常."""


class StrategyError(BacktestError):
    """策略执行错误."""


class BrokerError(BacktestError):
    """经纪商错误."""


class StatsError(BacktestError):
    """统计计算错误."""


@dataclass
class BacktestResult:
    """回测结果 (FR-009/010)."""

    strategy_name: str = ""
    symbol: str = ""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    initial_cash: float = 100000
    commission: float = 0.0003
    slippage: float = 0.001
    stamp_duty: float = 0.001
    preset_name: Optional[str] = None
    stats: pd.Series = field(default_factory=pd.Series)
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    trades: pd.DataFrame = field(default_factory=pd.DataFrame)
    engine_version: str = "v2"
    created_at: Optional[datetime] = None
    _meta: Dict[str, Any] = field(default_factory=dict)

    def to_html(self, filename: Optional[str] = None) -> str:
        from src.backtest.plotting import generate_html_report
        html = generate_html_report(self)
        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html)
        return html

    def to_json(self) -> dict:
        data = {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "initial_cash": self.initial_cash,
            "commission": self.commission,
            "slippage": self.slippage,
            "stamp_duty": self.stamp_duty,
            "preset_name": self.preset_name,
            "engine_version": self.engine_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if not self.stats.empty:
            stats_dict = {}
            for k, v in self.stats.items():
                if isinstance(v, (np.integer,)):
                    stats_dict[k] = int(v)
                elif isinstance(v, (np.floating,)):
                    stats_dict[k] = float(v)
                elif pd.isna(v):
                    stats_dict[k] = None
                elif isinstance(v, (datetime, pd.Timestamp)):
                    stats_dict[k] = str(v)
                else:
                    stats_dict[k] = v
            data["stats"] = stats_dict
        if not self.equity_curve.empty:
            data["equity_curve"] = self.equity_curve.to_dict(orient="records")
        if not self.trades.empty:
            data["trades"] = self.trades.to_dict(orient="records")
        return data

    def summary(self) -> dict:
        s = self.stats
        return {
            "strategy": self.strategy_name,
            "symbol": self.symbol,
            "return_pct": float(s.get("Return [%]", 0)),
            "sharpe_ratio": float(s.get("Sharpe Ratio", 0)),
            "max_drawdown_pct": float(s.get("Max Drawdown [%]", 0)),
            "win_rate_pct": float(s.get("Win Rate [%]", 0)),
            "trade_count": int(s.get("# Trades", 0)),
            "profit_factor": float(s.get("Profit Factor", 0)),
        }


class Backtest:
    """回测引擎主类 (FR-001).

    Usage:
        bt = Backtest(data_df, MyStrategy, cash=100000, commission=0.0003)
        result = bt.run()
        print(result.stats)
        result.to_html("report.html")
    """

    def __init__(
        self,
        data: pd.DataFrame,
        strategy: Type[BacktestStrategy],
        cash: float = 100000,
        commission: float = 0.0003,
        slippage: float = 0.001,
        stamp_duty: float = 0.001,
        min_commission: float = 5.0,
        margin: float = 1.0,
        trade_on_close: bool = False,
        hedging: bool = False,
        exclusive_orders: bool = False,
        exit_rule: Optional[ExitRule] = None,
    ) -> None:
        self._data_df = data.copy()
        self._strategy_cls = strategy
        self._cash = float(cash)
        self._commission = float(commission)
        self._slippage = float(slippage)
        self._stamp_duty = float(stamp_duty)
        self._min_commission = float(min_commission)
        self._margin = float(margin)
        self._trade_on_close = trade_on_close
        self._hedging = hedging
        self._exclusive_orders = exclusive_orders
        self._exit_rule = exit_rule

        self._validate_data()

    def _validate_data(self) -> None:
        required = ["Open", "High", "Low", "Close"]
        for col in required:
            if col not in self._data_df.columns:
                raise ValueError(f"Data must contain column: {col}")
        self._data_df = self._data_df.sort_index()
        self._data_df = self._data_df.ffill()

    def run(self, **kwargs: Any) -> BacktestResult:
        """执行回测 (FR-001).

        Args:
            **kwargs: 传递给策略 __init__ 的参数

        Returns:
            BacktestResult 包含统计、权益曲线、交易记录
        """
        start_time = time.time()
        result_meta: Dict[str, Any] = {"error": None, "error_stage": None}

        try:
            data = _OHLCVData(self._data_df)
        except Exception as exc:
            raise InsufficientDataError(f"OHLCV 数据初始化失败: {exc}") from exc

        broker = _Broker(
            cash=self._cash,
            data=data,
            commission=self._commission,
            slippage=self._slippage,
            stamp_duty=self._stamp_duty,
            min_commission=self._min_commission,
            margin=self._margin,
            trade_on_close=self._trade_on_close,
            hedging=self._hedging,
            exclusive_orders=self._exclusive_orders,
            exit_rule=self._exit_rule,
        )

        try:
            strategy = self._strategy_cls(**kwargs) if kwargs else self._strategy_cls()
        except Exception as exc:
            raise StrategyError(f"策略实例化失败 [{self._strategy_cls.__name__}]: {exc}") from exc

        strategy._broker = broker
        strategy._data = data

        try:
            strategy.init()
        except Exception as exc:
            raise StrategyError(f"策略 init() 执行失败 [{self._strategy_cls.__name__}]: {exc}") from exc

        try:
            strategy._compute_indicators(data)
        except Exception as exc:
            raise StrategyError(f"指标计算失败 [{self._strategy_cls.__name__}]: {exc}") from exc

        equity_curve: List[float] = []
        total_bars = len(data)

        result_meta["skipped_bars"] = 0
        result_meta["error_bars"] = 0

        for i in range(total_bars):
            broker._current_bar = i

            try:
                broker._process_orders(i)
            except Exception as exc:
                logger.warning("订单处理失败 @ bar %d (code: %s): %s", i,
                               getattr(self._data_df, "attrs", {}).get("symbol", "?"), exc)
                result_meta["error_bars"] = result_meta.get("error_bars", 0) + 1
                result_meta.setdefault("error_details", []).append(
                    {"bar": i, "stage": "process_orders", "error": str(exc)}
                )

            try:
                broker._check_sl_tp(i)
            except Exception as exc:
                logger.warning("止损止盈检查失败 @ bar %d: %s", i, exc)

            try:
                strategy.next(i)
            except Exception as exc:
                logger.warning("策略 next(%d) 执行失败: %s", i, exc)
                result_meta["error_bars"] = result_meta.get("error_bars", 0) + 1
                result_meta.setdefault("error_details", []).append(
                    {"bar": i, "stage": "strategy_next", "error": str(exc)}
                )

            equity = broker._equity
            equity_curve.append(equity)

            if broker._check_ruin():
                logger.warning("破产检测: 权益归零或为负，停止回测")
                break

        try:
            broker._finalize(total_bars - 1)
        except Exception as exc:
            logger.warning("收尾平仓失败: %s", exc)

        equity_curve.append(broker._equity)

        all_trades = broker._closed_trades + [
            t for t in broker._trades if not t._is_closed
        ]

        try:
            stats = compute_stats(
                trades=all_trades,
                equity_curve=np.array(equity_curve, dtype=float),
                data_df=self._data_df,
                cash=self._cash,
            )
        except Exception as exc:
            logger.warning("统计计算失败: %s", exc)
            stats = pd.Series({"Error": str(exc)})

        eq_df = self._build_equity_df(equity_curve, data)
        trade_df = self._build_trades_df(all_trades)

        elapsed = time.time() - start_time
        logger.info("回测完成: %s, %d bars, %.2fs", self._strategy_cls.__name__, total_bars, elapsed)

        result_meta["elapsed_seconds"] = elapsed
        result_meta["total_bars"] = total_bars

        result = BacktestResult(
            strategy_name=self._strategy_cls.__name__,
            symbol=getattr(self._data_df, "attrs", {}).get("symbol", ""),
            start_date=data.index[0] if len(data.index) > 0 else None,
            end_date=data.index[-1] if len(data.index) > 0 else None,
            initial_cash=self._cash,
            commission=self._commission,
            slippage=self._slippage,
            stamp_duty=self._stamp_duty,
            stats=stats,
            equity_curve=eq_df,
            trades=trade_df,
            engine_version="v2",
            created_at=datetime.now(),
            _meta=result_meta,
        )
        return result

    def _build_equity_df(self, equity: List[float], data: _OHLCVData) -> pd.DataFrame:
        peak = np.maximum.accumulate(equity)
        dd = (np.array(equity) - peak) / peak * 100
        n = min(len(equity), len(data.index))
        result = pd.DataFrame({
            "Equity": equity[:n],
            "DrawdownPct": dd[:n],
        }, index=data.index[:n])
        dd_duration = np.zeros(n)
        dur = 0
        for i in range(n):
            if dd[i] < 0:
                dur += 1
            else:
                dur = 0
            dd_duration[i] = dur
        result["DrawdownDuration"] = dd_duration
        return result

    def _build_trades_df(self, trades: List[Trade]) -> pd.DataFrame:
        if not trades:
            return pd.DataFrame()
        records = []
        for t in trades:
            records.append({
                "Size": t.size,
                "EntryBar": t.entry_bar,
                "ExitBar": t.exit_bar,
                "EntryPrice": t.entry_price,
                "ExitPrice": t.exit_price,
                "SL": t.sl,
                "TP": t.tp,
                "PnL": t.pl,
                "ReturnPct": t.pl_pct,
                "EntryTime": t.entry_time,
                "ExitTime": t.exit_time,
                "Duration": str(t.exit_bar - t.entry_bar) if t.exit_bar is not None and t.entry_bar is not None else None,
                "Tag": t.tag,
                "ExitReason": t.exit_reason,
                "PositionPct": t.position_pct,
            })
        return pd.DataFrame(records)

    def optimize(
        self,
        maximize: str = "Sharpe Ratio",
        method: str = "grid",
        max_tries: Optional[int] = None,
        constraint: Optional[Callable] = None,
        return_heatmap: bool = False,
        return_optimization: bool = False,
        **kwargs: Any,
    ) -> pd.Series:
        """参数优化 (FR-012/014).

        Args:
            maximize: 优化目标指标名
            method: 'grid' 或 'bayesian'
            max_tries: 最大尝试次数
            constraint: 约束函数，接收参数 dict 返回 bool
            return_heatmap: 是否返回热力图数据
            return_optimization: 是否返回优化过程数据
            **kwargs: 参数范围，如 short_window=range(3, 15)

        Returns:
            最优参数对应的 stats Series
        """
        param_names = list(kwargs.keys())
        param_values = list(kwargs.values())

        if method == "grid":
            results, all_iterations = self._grid_search(
                param_names, param_values, maximize, constraint, max_tries,
            )
        elif method == "bayesian":
            results, all_iterations = self._bayesian_search(
                param_names, param_values, maximize, max_tries,
            )
        else:
            raise ValueError(f"Unknown optimization method: {method}")

        if not results:
            raise RuntimeError("优化未产生有效结果")

        best = max(results, key=lambda x: x[0])
        best_value, best_params, best_stats = best

        best_stats["_best_params"] = best_params
        best_stats["_best_value"] = best_value
        if return_heatmap:
            best_stats["_heatmap"] = self._build_heatmap(all_iterations, param_names, maximize)
        if return_optimization:
            best_stats["_optimization_history"] = all_iterations

        return best_stats

    def _grid_search(
        self,
        param_names: List[str],
        param_ranges: List[Any],
        maximize: str,
        constraint: Optional[Callable],
        max_tries: Optional[int],
    ) -> Tuple[List[Tuple[float, Dict[str, float], pd.Series]], List[Dict[str, Any]]]:
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
            all_combinations = all_combinations[:max_tries]

        results: List[Tuple[float, Dict[str, float], pd.Series]] = []
        all_iterations: List[Dict[str, Any]] = []

        for combo in all_combinations:
            params = dict(zip(param_names, combo))
            try:
                result = self.run(**params)
                value = float(result.stats.get(maximize, 0))
                results.append((value, params, result.stats))
                all_iterations.append({
                    "params": params,
                    "value": value,
                    "stats": {k: v for k, v in result.stats.items()},
                })
            except Exception as exc:
                logger.warning("优化迭代失败: %s, error=%s", params, exc)

        return results, all_iterations


class MultiBacktest:
    """多标的并行回测引擎 (FR-021).

    共享内存优化大数据场景，支持多品种独立回测和结果汇总.
    """

    def __init__(
        self,
        dfs: List[pd.DataFrame],
        strategy_cls: Type[BacktestStrategy],
        cash: float = 100000,
        commission: float = 0.0003,
        slippage: float = 0.001,
        stamp_duty: float = 0.001,
        **kwargs: Any,
    ) -> None:
        self._dfs = dfs
        self._strategy_cls = strategy_cls
        self._cash = cash
        self._commission = commission
        self._slippage = slippage
        self._stamp_duty = stamp_duty
        self._kwargs = kwargs

    def run(self, **factor_kwargs: Any) -> pd.DataFrame:
        """逐个品种执行回测，汇总结果."""
        rows: List[Dict[str, Any]] = []
        for df in self._dfs:
            symbol = getattr(df, "attrs", {}).get("symbol", "")
            try:
                bt = Backtest(
                    df,
                    self._strategy_cls,
                    cash=self._cash,
                    commission=self._commission,
                    slippage=self._slippage,
                    stamp_duty=self._stamp_duty,
                    **self._kwargs,
                )
                result = bt.run(**factor_kwargs)
                row = {
                    "Symbol": symbol,
                    "Return [%]": float(result.stats.get("Return [%]", 0)),
                    "Sharpe Ratio": float(result.stats.get("Sharpe Ratio", 0)),
                    "Max Drawdown [%]": float(result.stats.get("Max Drawdown [%]", 0)),
                    "Win Rate [%]": float(result.stats.get("Win Rate [%]", 0)),
                    "# Trades": int(result.stats.get("# Trades", 0)),
                    "Profit Factor": float(result.stats.get("Profit Factor", 0)),
                    "Bars": len(df),
                }
                rows.append(row)
            except Exception as exc:
                logger.warning("MultiBacktest失败 [%s]: %s", symbol, exc)
                rows.append({"Symbol": symbol, "Error": str(exc)})
        return pd.DataFrame(rows)

    def optimize(self, maximize: str = "Sharpe Ratio", method: str = "grid",
                 max_tries: Optional[int] = None, **factor_ranges: Any) -> pd.DataFrame:
        """对每个品种执行参数优化，返回各品种最优结果."""
        rows: List[Dict[str, Any]] = []
        for df in self._dfs:
            symbol = getattr(df, "attrs", {}).get("symbol", "")
            try:
                bt = Backtest(
                    df,
                    self._strategy_cls,
                    cash=self._cash,
                    commission=self._commission,
                    slippage=self._slippage,
                    stamp_duty=self._stamp_duty,
                    **self._kwargs,
                )
                result_stats = bt.optimize(
                    maximize=maximize,
                    method=method,
                    max_tries=max_tries,
                    return_heatmap=False,
                    return_optimization=False,
                    **factor_ranges,
                )
                row = {
                    "Symbol": symbol,
                    "Best Value": float(result_stats.get("_best_value", 0)),
                    "Best Params": result_stats.get("_best_params", {}),
                    "Return [%]": float(result_stats.get("Return [%]", 0)),
                    "Sharpe Ratio": float(result_stats.get("Sharpe Ratio", 0)),
                    "Max Drawdown [%]": float(result_stats.get("Max Drawdown [%]", 0)),
                }
                rows.append(row)
            except Exception as exc:
                logger.warning("MultiBacktest优化失败 [%s]: %s", symbol, exc)
                rows.append({"Symbol": symbol, "Error": str(exc)})
        return pd.DataFrame(rows)

    def _bayesian_search(
        self,
        param_names: List[str],
        param_ranges: List[Any],
        maximize: str,
        max_tries: Optional[int],
    ) -> Tuple[List[Tuple[float, Dict[str, float], pd.Series]], List[Dict[str, Any]]]:
        n_tries = max_tries or 50
        n_random = max(5, n_tries // 5)

        results: List[Tuple[float, Dict[str, float], pd.Series]] = []
        all_iterations: List[Dict[str, Any]] = []

        bounds = []
        for r in param_ranges:
            if isinstance(r, range):
                bounds.append((r.start, r.stop - 1))
            elif isinstance(r, list):
                bounds.append((min(r), max(r)))
            else:
                bounds.append((r, r))

        for _ in range(n_random):
            params = {}
            for name, b in zip(param_names, bounds):
                params[name] = float(np.random.randint(int(b[0]), int(b[1]) + 1))
            try:
                result = self.run(**params)
                value = float(result.stats.get(maximize, 0))
                results.append((value, params, result.stats))
                all_iterations.append({"params": params, "value": value, "stats": {k: v for k, v in result.stats.items()}})
            except Exception as exc:
                logger.warning("贝叶斯随机阶段失败: %s, error=%s", params, exc)

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
                proposed = np.random.normal(mu, sigma)
                params[name] = float(np.clip(round(proposed), b[0], b[1]))

            try:
                result = self.run(**params)
                value = float(result.stats.get(maximize, 0))
                results.append((value, params, result.stats))
                all_iterations.append({"params": params, "value": value, "stats": {k: v for k, v in result.stats.items()}})
            except Exception as exc:
                logger.warning("贝叶斯搜索阶段失败: %s, error=%s", params, exc)

        return results, all_iterations

    def _build_heatmap(
        self,
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
