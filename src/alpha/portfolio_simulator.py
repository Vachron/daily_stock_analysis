# -*- coding: utf-8 -*-
"""Portfolio simulator — daily portfolio simulation with transaction costs.

Simulates a long-only alpha-weighted portfolio:
- Rebalance on configured frequency (e.g., every 5 trading days)
- Apply commission + slippage on each trade
- Track daily NAV, positions, cash, trade records
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.alpha.alpha_scorer import AlphaPrediction

logger = logging.getLogger(__name__)


@dataclass
class PortfolioConfig:
    initial_capital: float = 1_000_000.0
    max_positions: int = 20
    max_single_weight: float = 0.10
    min_single_weight: float = 0.01
    commission_rate: float = 0.0003
    slippage_pct: float = 0.001
    rebalance_freq_days: int = 5


@dataclass
class PortfolioSnapshot:
    date: date
    nav: float
    positions: Dict[str, float]  # code → shares
    weights: Dict[str, float]    # code → weight in portfolio
    cash: float
    daily_return: float = 0.0


@dataclass
class TradeRecord:
    date: date
    code: str
    action: str  # "buy" | "sell"
    shares: int
    price: float
    cost: float
    reason: str = ""


class PortfolioSimulator:
    def __init__(self, config: Optional[PortfolioConfig] = None):
        self.config = config or PortfolioConfig()
        self.nav_history: pd.DataFrame = pd.DataFrame()
        self.snapshots: List[PortfolioSnapshot] = []
        self.trades: List[TradeRecord] = []
        self.trade_calendar: List[date] = []

    def simulate(
        self,
        alphas_by_date: Dict[date, List[AlphaPrediction]],
        price_data: Dict[str, pd.DataFrame],
        benchmark_nav: Optional[pd.Series] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Tuple[pd.DataFrame, List[PortfolioSnapshot], List[TradeRecord]]:
        self.nav_history = pd.DataFrame()
        self.snapshots = []
        self.trades = []

        sorted_dates = sorted(alphas_by_date.keys())
        if start_date:
            sorted_dates = [d for d in sorted_dates if d >= start_date]
        if end_date:
            sorted_dates = [d for d in sorted_dates if d <= end_date]

        if not sorted_dates:
            return pd.DataFrame(), [], []

        cash = self.config.initial_capital
        positions: Dict[str, float] = {}
        nav_series: List[Dict[str, Any]] = []

        for day_idx, day in enumerate(sorted_dates):
            day_alphas = alphas_by_date.get(day, [])
            is_rebalance = day_idx % self.config.rebalance_freq_days == 0

            if is_rebalance and day_idx == 0:
                target_weights = self._build_target_weights(day_alphas)
                cash, positions = self._execute_rebalance(
                    cash, positions, target_weights, day, price_data, is_initial=True,
                )
            elif is_rebalance:
                target_weights = self._build_target_weights(day_alphas)
                cash, positions = self._execute_rebalance(
                    cash, positions, target_weights, day, price_data, is_initial=False,
                )

            equity_value = cash + self._position_value(positions, day, price_data)
            prev_nav = nav_series[-1]["nav"] if nav_series else self.config.initial_capital
            daily_ret = (equity_value - prev_nav) / prev_nav if prev_nav > 0 else 0.0

            weights = {}
            for code, shares in positions.items():
                px = self._get_price(code, day, price_data)
                if px and px > 0:
                    weights[code] = (shares * px) / equity_value if equity_value > 0 else 0.0

            nav_series.append({
                "date": day,
                "nav": equity_value,
                "daily_return": daily_ret,
                "cash": cash,
                "num_positions": len(positions),
            })
            self.snapshots.append(PortfolioSnapshot(
                date=day,
                nav=equity_value,
                positions=dict(positions),
                weights=weights,
                cash=cash,
                daily_return=daily_ret,
            ))

        self.nav_history = pd.DataFrame(nav_series)
        if not self.nav_history.empty and benchmark_nav is not None:
            self._merge_benchmark(benchmark_nav)

        return self.nav_history, self.snapshots, self.trades

    def _build_target_weights(self, alphas: List[AlphaPrediction]) -> Dict[str, float]:
        if not alphas:
            return {}

        num_pos = self.config.max_positions
        valid_alphas = [a for a in alphas if a.alpha_score > -2.0]
        sorted_alphas = sorted(valid_alphas, key=lambda x: x.alpha_score, reverse=True)
        selected = sorted_alphas[:num_pos]

        abs_scores = {}
        for a in selected:
            abs_scores[a.code] = max(0.0, a.alpha_score + abs(min(ap.alpha_score for ap in selected)))

        total_abs = sum(abs_scores.values())
        if total_abs <= 0:
            return {}

        weights = {}
        for code, abs_sc in abs_scores.items():
            w = abs_sc / total_abs
            w = min(w, self.config.max_single_weight)
            if w >= self.config.min_single_weight:
                weights[code] = w

        remaining = 1.0 - sum(weights.values())
        if remaining > 0 and weights:
            top_code = max(weights, key=weights.get)
            weights[top_code] += remaining

        return weights

    def _execute_rebalance(
        self,
        cash: float,
        positions: Dict[str, float],
        target_weights: Dict[str, float],
        day: date,
        price_data: Dict[str, pd.DataFrame],
        is_initial: bool = False,
    ) -> Tuple[float, Dict[str, float]]:
        if is_initial and not target_weights:
            return cash, positions

        if not is_initial:
            for code in list(positions.keys()):
                if code not in target_weights:
                    px = self._get_price(code, day, price_data)
                    if px and px > 0 and positions[code] > 0:
                        shares = int(positions[code])
                        cost = shares * px * (1 - self.config.commission_rate) - shares * px * self.config.slippage_pct
                        cash += cost
                        self.trades.append(TradeRecord(
                            date=day, code=code, action="sell",
                            shares=shares, price=px, cost=cost, reason="rebalance_exit",
                        ))
                    del positions[code]

        total_equity = cash
        for code, shares in positions.items():
            px = self._get_price(code, day, price_data)
            if px and px > 0:
                total_equity += shares * px

        for code, weight in target_weights.items():
            px = self._get_price(code, day, price_data)
            if not px or px <= 0:
                continue
            target_value = total_equity * weight
            current_shares = positions.get(code, 0)
            current_value = current_shares * px
            diff = target_value - current_value
            if abs(diff) < target_value * 0.05:
                continue
            if diff > 0:
                trade_value = diff / (1 + self.config.commission_rate + self.config.slippage_pct)
                shares_to_buy = int(trade_value / px)
                if shares_to_buy <= 0:
                    continue
                cost = shares_to_buy * px * (1 + self.config.commission_rate + self.config.slippage_pct)
                if cost <= cash:
                    cash -= cost
                    positions[code] = positions.get(code, 0) + shares_to_buy
                    self.trades.append(TradeRecord(
                        date=day, code=code, action="buy",
                        shares=shares_to_buy, price=px, cost=cost, reason="rebalance_enter",
                    ))
            elif diff < 0:
                sell_value = min(abs(diff), current_value * 0.5)
                shares_to_sell = int(sell_value / px)
                if shares_to_sell <= 0:
                    continue
                if shares_to_sell > positions.get(code, 0):
                    shares_to_sell = int(positions.get(code, 0))
                cost = shares_to_sell * px * (1 - self.config.commission_rate - self.config.slippage_pct)
                cash += cost
                positions[code] = positions.get(code, 0) - shares_to_sell
                self.trades.append(TradeRecord(
                    date=day, code=code, action="sell",
                    shares=shares_to_sell, price=px, cost=cost, reason="rebalance_reduce",
                ))

        return cash, positions

    def _position_value(self, positions: Dict[str, float], day: date, price_data: Dict[str, pd.DataFrame]) -> float:
        value = 0.0
        for code, shares in positions.items():
            px = self._get_price(code, day, price_data)
            if px and px > 0:
                value += shares * px
        return value

    @staticmethod
    def _get_price(code: str, day: date, price_data: Dict[str, pd.DataFrame]) -> Optional[float]:
        df = price_data.get(code)
        if df is None or df.empty:
            return None
        day_str = str(day)
        if "date" in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df["date"]):
                day_dt = pd.Timestamp(day)
                row = df[df["date"].dt.date == day]
            else:
                row = df[df["date"].astype(str) == day_str]
        else:
            idx_date = pd.to_datetime(df.index)
            row = df[idx_date.date == day]
        if row.empty:
            return None
        return float(row["close"].iloc[-1])

    def _merge_benchmark(self, benchmark_nav: pd.Series) -> None:
        if self.nav_history.empty:
            return
        bench_aligned = benchmark_nav.reindex(self.nav_history.index, method="ffill")
        if bench_aligned.iloc[0] != 0:
            self.nav_history["benchmark_nav"] = bench_aligned.values
            self.nav_history["excess_return"] = (
                self.nav_history["nav"] / self.nav_history["nav"].iloc[0]
                - self.nav_history["benchmark_nav"] / self.nav_history["benchmark_nav"].iloc[0]
            )
