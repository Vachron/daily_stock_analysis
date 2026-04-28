# -*- coding: utf-8 -*-
"""Alpha evaluator — excess return metrics, information ratio, tracking error, factor IC."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AlphaMetrics:
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    excess_return_pct: float = 0.0
    information_ratio: float = 0.0
    tracking_error_pct: float = 0.0
    max_excess_drawdown_pct: float = 0.0
    win_rate_pct: float = 0.0
    turnover_rate_pct: float = 0.0
    num_trading_days: int = 0
    sample_warning: str = ""


@dataclass
class FactorICReport:
    factor_id: str
    rank_ic: float = 0.0
    ic_ir: float = 0.0
    ic_mean: float = 0.0
    ic_std: float = 0.0
    ic_series: List[float] = None
    is_aged: bool = False
    aged_reason: str = ""

    def __post_init__(self):
        self.ic_series = self.ic_series or []


class AlphaEvaluator:
    TRADING_DAYS_PER_YEAR = 250

    DEFAULT_RISK_FREE_RATE = 0.02

    @classmethod
    def evaluate(
        cls,
        nav_df: pd.DataFrame,
        benchmark_nav: Optional[pd.Series] = None,
        risk_free_rate: Optional[float] = None,
    ) -> AlphaMetrics:
        if nav_df.empty or "nav" not in nav_df.columns or len(nav_df) < 2:
            return AlphaMetrics(sample_warning="回测数据不足")

        rf = risk_free_rate if risk_free_rate is not None else cls.DEFAULT_RISK_FREE_RATE
        nav_series = nav_df["nav"].values
        daily_returns = nav_df["daily_return"].values if "daily_return" in nav_df.columns else np.diff(nav_series) / nav_series[:-1]

        num_days = len(nav_series)
        total_return_pct = (nav_series[-1] - nav_series[0]) / nav_series[0] * 100

        years = num_days / cls.TRADING_DAYS_PER_YEAR
        annualized_return_pct = ((1 + total_return_pct / 100) ** (1 / years) - 1) * 100 if years > 0 else 0.0

        max_dd = cls._max_drawdown(nav_series)
        daily_rf = rf / cls.TRADING_DAYS_PER_YEAR
        excess_daily = daily_returns - daily_rf
        sharpe = np.sqrt(cls.TRADING_DAYS_PER_YEAR) * np.mean(excess_daily) / (np.std(excess_daily) + 1e-10) if len(excess_daily) > 1 else 0.0

        win_rate_pct = np.sum(daily_returns > 0) / len(daily_returns) * 100 if len(daily_returns) > 0 else 0.0

        excess_return_pct = 0.0
        information_ratio = 0.0
        tracking_error_pct = 0.0
        max_excess_dd = 0.0

        if benchmark_nav is not None and not benchmark_nav.empty:
            bench_aligned = cls._align_benchmark(nav_df, benchmark_nav)
            if bench_aligned is not None and len(bench_aligned) > 1:
                bench_returns = np.diff(bench_aligned) / bench_aligned[:-1]
                port_returns_full = (nav_series[1:] - nav_series[:-1]) / nav_series[:-1]
                min_len = min(len(port_returns_full), len(bench_returns))
                port_ret = port_returns_full[:min_len]
                bench_ret = bench_returns[:min_len]
                excess = port_ret - bench_ret
                excess_return_pct = np.sum(excess) * 100
                tracking_error_pct = np.std(excess) * np.sqrt(cls.TRADING_DAYS_PER_YEAR) * 100
                information_ratio = np.mean(excess) / (np.std(excess) + 1e-10) * np.sqrt(cls.TRADING_DAYS_PER_YEAR)
                excess_cum = np.cumprod(1 + excess)
                max_excess_dd = cls._max_drawdown(excess_cum)

        sample_warning = ""
        if num_days < 60:
            sample_warning = "样本不足（<60日），年化指标仅供参考"

        return AlphaMetrics(
            total_return_pct=round(total_return_pct, 2),
            annualized_return_pct=round(annualized_return_pct, 2),
            max_drawdown_pct=round(max_dd, 2),
            sharpe_ratio=round(sharpe, 4),
            excess_return_pct=round(excess_return_pct, 2),
            information_ratio=round(information_ratio, 4),
            tracking_error_pct=round(tracking_error_pct, 2),
            max_excess_drawdown_pct=round(max_excess_dd, 2),
            win_rate_pct=round(win_rate_pct, 2),
            turnover_rate_pct=0.0,
            num_trading_days=num_days,
            sample_warning=sample_warning,
        )

    @classmethod
    def compute_factor_ic(
        cls,
        factor_values: pd.Series,
        forward_returns: pd.Series,
        aged_threshold: float = 0.02,
        aged_periods: int = 12,
    ) -> FactorICReport:
        factor_id = str(factor_values.name or "unknown")

        if len(factor_values) < 50 or len(forward_returns) < 50:
            return FactorICReport(factor_id=factor_id, aged_reason="样本不足（<50）")

        common_idx = factor_values.index.intersection(forward_returns.index)
        if len(common_idx) < 50:
            return FactorICReport(factor_id=factor_id, aged_reason="截面匹配样本不足")

        fv = factor_values.loc[common_idx]
        fr = forward_returns.loc[common_idx]

        from scipy.stats import spearmanr

        has_date_index = False
        per_period_ics: List[float] = []

        if isinstance(fv.index, pd.DatetimeIndex) or (
            hasattr(fv.index, 'dtype') and 'datetime' in str(fv.index.dtype)
        ):
            has_date_index = True
        elif fv.index.dtype == object:
            try:
                dates = pd.to_datetime(fv.index)
                unique_dates = sorted(set(dates.date))
                if len(unique_dates) > 1:
                    has_date_index = True
            except Exception:
                pass

        if has_date_index:
            dates = pd.to_datetime(fv.index)
            for dt in sorted(set(dates.date)):
                mask = dates.date == dt
                fv_d = fv[mask]
                fr_d = fr[fr.index.isin(fv_d.index)]
                common = fv_d.index.intersection(fr_d.index)
                if len(common) < 10:
                    continue
                ic, _ = spearmanr(fv_d.loc[common], fr_d.loc[common])
                if not np.isnan(ic):
                    per_period_ics.append(float(ic))

            if len(per_period_ics) >= 2:
                ic_mean = float(np.mean(per_period_ics))
                ic_std = float(np.std(per_period_ics, ddof=1))
                ic_ir = ic_mean / ic_std if ic_std > 0 else 0.0
                ic_series = per_period_ics
                rank_ic = ic_mean
            else:
                rank_ic, _ = spearmanr(fv, fr)
                ic_mean = rank_ic
                ic_std = 0.0
                ic_ir = 0.0
                ic_series = [rank_ic]
        else:
            rank_ic, _ = spearmanr(fv, fr)
            ic_mean = rank_ic
            ic_std = 0.0
            ic_ir = 0.0
            ic_series = [rank_ic]

        is_aged = abs(rank_ic) < aged_threshold
        aged_reason = "IC 低于阈值 %.3f" % aged_threshold if is_aged else ""

        return FactorICReport(
            factor_id=factor_id,
            rank_ic=round(rank_ic, 4),
            ic_ir=round(ic_ir, 4),
            ic_mean=round(ic_mean, 4),
            ic_std=round(ic_std, 4),
            ic_series=ic_series,
            is_aged=is_aged,
            aged_reason=aged_reason,
        )

    @classmethod
    def compute_rolling_ic(
        cls,
        factor_values: pd.DataFrame,
        forward_returns: pd.DataFrame,
        window: int = 20,
    ) -> pd.DataFrame:
        """Compute rolling window Rank IC for each factor."""
        from scipy.stats import spearmanr

        results: List[Dict] = []
        dates = sorted(set(factor_values.index) & set(forward_returns.index))
        for i in range(window, len(dates)):
            w_dates = dates[i - window:i]
            row: Dict[str, Any] = {"date": dates[i]}
            for col in factor_values.columns:
                if col not in forward_returns.columns:
                    continue
                fv = factor_values.loc[w_dates, col]
                fr = forward_returns.loc[w_dates, col]
                common = fv.dropna().index.intersection(fr.dropna().index)
                if len(common) < 10:
                    row[col] = np.nan
                    continue
                ic, _ = spearmanr(fv.loc[common], fr.loc[common])
                row[col] = ic
            results.append(row)

        return pd.DataFrame(results)

    @staticmethod
    def _max_drawdown(nav: np.ndarray) -> float:
        peak = np.maximum.accumulate(nav)
        dd = (nav - peak) / peak
        return float(np.min(dd) * 100)

    @staticmethod
    def _align_benchmark(nav_df: pd.DataFrame, benchmark_nav: pd.Series) -> Optional[np.ndarray]:
        try:
            if isinstance(benchmark_nav.index, pd.DatetimeIndex):
                bench_dates = benchmark_nav.index.date
            else:
                bench_dates = pd.to_datetime(benchmark_nav.index).date
            nav_dates = pd.to_datetime(nav_df["date"]).dt.date
            aligned = []
            prev_val = benchmark_nav.iloc[0]
            for nd in nav_dates:
                if nd in bench_dates:
                    idx = list(bench_dates).index(nd)
                    prev_val = benchmark_nav.iloc[idx]
                aligned.append(prev_val)
            return np.array(aligned, dtype=float)
        except Exception as e:
            logger.warning("Benchmark alignment failed: %s", e)
            return None

    @classmethod
    def print_report(cls, metrics: AlphaMetrics) -> str:
        lines = [
            "=" * 50,
            "  Alpha 超额收益评估报告",
            "=" * 50,
            "  总收益率:       %8.2f%%" % metrics.total_return_pct,
            "  年化收益率:     %8.2f%%" % metrics.annualized_return_pct,
            "  最大回撤:       %8.2f%%" % metrics.max_drawdown_pct,
            "  夏普比率:       %8.4f" % metrics.sharpe_ratio,
            "  超额收益:       %8.2f%%" % metrics.excess_return_pct,
            "  信息比率:       %8.4f" % metrics.information_ratio,
            "  跟踪误差:       %8.2f%%" % metrics.tracking_error_pct,
            "  超额最大回撤:   %8.2f%%" % metrics.max_excess_drawdown_pct,
            "  胜率:           %8.2f%%" % metrics.win_rate_pct,
            "  交易日数:       %8d" % metrics.num_trading_days,
            "-" * 50,
        ]
        if metrics.sample_warning:
            lines.append("  ⚠ %s" % metrics.sample_warning)
        lines.append("=" * 50)
        return "\n".join(lines)
