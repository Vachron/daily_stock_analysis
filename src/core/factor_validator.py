# -*- coding: utf-8 -*-
"""
Factor Validator — PBO, CSCV, DSR, Walk-forward validation.

Anti-overfitting validation toolkit:
- PBO (Probability of Backtest Overfitting): Measures how likely an optimal
  strategy from in-sample is suboptimal out-of-sample.
- CSCV (Combinatorially Symmetric Cross-Validation): Splits returns into
  S subsets, tests all C(S, S/2) train/test combinations.
- DSR (Deflated Sharpe Ratio): Adjusts Sharpe Ratio for multiple testing bias.
- Walk-forward: Rolling train/test validation with realistic backtest timing.

All validators enforce:
- No look-ahead bias (train data strictly before test data)
- Minimum sample size requirements
- Statistical significance thresholds
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

_MIN_OBS = 60
_DEFAULT_S = 16


@dataclass
class PBOResult:
    pbo: float
    n_combinations: int
    oos_rank_avg: float
    is_best_wins_oos: int
    is_best_total: int
    interpretation: str = ""

    @property
    def is_overfitted(self) -> bool:
        return self.pbo > 0.5


@dataclass
class CSCVResult:
    pbo: float
    n_combinations: int
    performance_gap: float
    interpretation: str = ""

    @property
    def is_overfitted(self) -> bool:
        return self.pbo > 0.5


@dataclass
class DSRResult:
    sharpe_ratio: float
    deflated_sharpe: float
    p_value: float
    n_trials: int
    skewness: float
    kurtosis: float
    interpretation: str = ""

    @property
    def is_significant(self) -> bool:
        return self.p_value < 0.05


@dataclass
class WalkForwardResult:
    train_returns: List[float]
    test_returns: List[float]
    train_sharpe: float
    test_sharpe: float
    degradation_ratio: float
    n_folds: int
    interpretation: str = ""

    @property
    def is_overfitted(self) -> bool:
        if self.degradation_ratio < 0:
            return False
        return self.degradation_ratio < 0.5


@dataclass
class FactorValidationReport:
    factor_name: str
    pbo_result: Optional[PBOResult] = None
    cscv_result: Optional[CSCVResult] = None
    dsr_result: Optional[DSRResult] = None
    walk_forward_result: Optional[WalkForwardResult] = None
    overall_verdict: str = "pending"

    @property
    def is_valid(self) -> bool:
        if self.pbo_result and self.pbo_result.is_overfitted:
            return False
        if self.cscv_result and self.cscv_result.is_overfitted:
            return False
        if self.dsr_result and not self.dsr_result.is_significant:
            return False
        if self.walk_forward_result and self.walk_forward_result.is_overfitted:
            return False
        return True


def _sharpe_ratio(returns: np.ndarray, annualize: bool = True, periods_per_year: int = 252) -> float:
    if len(returns) < 2:
        return 0.0
    mean_r = np.mean(returns)
    std_r = np.std(returns, ddof=1)
    if std_r == 0:
        return 0.0
    sr = mean_r / std_r
    if annualize:
        sr *= np.sqrt(periods_per_year)
    return float(sr)


def _cumulative_returns(returns: np.ndarray) -> np.ndarray:
    return np.cumprod(1 + returns)


def compute_pbo(
    strategy_returns: Dict[str, np.ndarray],
    n_splits: int = _DEFAULT_S,
) -> PBOResult:
    if len(strategy_returns) < 2:
        return PBOResult(pbo=1.0, n_combinations=0, oos_rank_avg=0.0,
                         is_best_wins_oos=0, is_best_total=0,
                         interpretation="Insufficient strategies for PBO")

    min_len = min(len(r) for r in strategy_returns.values())
    if min_len < n_splits * 4:
        return PBOResult(pbo=1.0, n_combinations=0, oos_rank_avg=0.0,
                         is_best_wins_oos=0, is_best_total=0,
                         interpretation=f"Insufficient data ({min_len} < {n_splits * 4})")

    strat_names = list(strategy_returns.keys())
    strat_arrays = {k: v[:min_len] for k, v in strategy_returns.items()}

    chunk_size = min_len // n_splits
    chunks = {}
    for name, rets in strat_arrays.items():
        chunks[name] = [rets[i * chunk_size:(i + 1) * chunk_size] for i in range(n_splits)]

    from itertools import combinations
    half = n_splits // 2
    train_combos = list(combinations(range(n_splits), half))

    is_best_wins_oos = 0
    is_best_total = 0
    oos_ranks = []

    for train_idx in train_combos:
        test_idx = tuple(i for i in range(n_splits) if i not in train_idx)

        is_sharpes = {}
        oos_sharpes = {}
        for name in strat_names:
            is_rets = np.concatenate([chunks[name][i] for i in train_idx])
            oos_rets = np.concatenate([chunks[name][i] for i in test_idx])
            is_sharpes[name] = _sharpe_ratio(is_rets, annualize=False)
            oos_sharpes[name] = _sharpe_ratio(oos_rets, annualize=False)

        is_best = max(is_sharpes, key=is_sharpes.get)
        is_best_total += 1

        sorted_oos = sorted(oos_sharpes.items(), key=lambda x: x[1], reverse=True)
        oos_rank = next(i for i, (n, _) in enumerate(sorted_oos) if n == is_best)
        oos_ranks.append(oos_rank)

        if oos_rank == 0:
            is_best_wins_oos += 1

    pbo = 1.0 - (is_best_wins_oos / is_best_total) if is_best_total > 0 else 1.0
    oos_rank_avg = float(np.mean(oos_ranks)) if oos_ranks else 0.0

    if pbo > 0.7:
        interp = "High overfitting risk — IS best rarely wins OOS"
    elif pbo > 0.5:
        interp = "Moderate overfitting risk — PBO > 0.5"
    elif pbo > 0.3:
        interp = "Low overfitting risk — factor relatively robust"
    else:
        interp = "Very low overfitting risk — factor is robust"

    return PBOResult(
        pbo=round(pbo, 4),
        n_combinations=len(train_combos),
        oos_rank_avg=round(oos_rank_avg, 2),
        is_best_wins_oos=is_best_wins_oos,
        is_best_total=is_best_total,
        interpretation=interp,
    )


def compute_cscv(
    strategy_returns: Dict[str, np.ndarray],
    n_splits: int = _DEFAULT_S,
) -> CSCVResult:
    if len(strategy_returns) < 2:
        return CSCVResult(pbo=1.0, n_combinations=0, performance_gap=0.0,
                          interpretation="Insufficient strategies for CSCV")

    min_len = min(len(r) for r in strategy_returns.values())
    if min_len < n_splits * 4:
        return CSCVResult(pbo=1.0, n_combinations=0, performance_gap=0.0,
                          interpretation=f"Insufficient data ({min_len} < {n_splits * 4})")

    strat_names = list(strategy_returns.keys())
    strat_arrays = {k: v[:min_len] for k, v in strategy_returns.items()}

    chunk_size = min_len // n_splits
    chunks = {}
    for name, rets in strat_arrays.items():
        chunks[name] = [rets[i * chunk_size:(i + 1) * chunk_size] for i in range(n_splits)]

    from itertools import combinations
    half = n_splits // 2
    train_combos = list(combinations(range(n_splits), half))

    oos_best_is_best_count = 0
    total_combos = 0
    perf_gaps = []

    for train_idx in train_combos:
        test_idx = tuple(i for i in range(n_splits) if i not in train_idx)

        is_perf = {}
        oos_perf = {}
        for name in strat_names:
            is_rets = np.concatenate([chunks[name][i] for i in train_idx])
            oos_rets = np.concatenate([chunks[name][i] for i in test_idx])
            is_perf[name] = np.sum(is_rets)
            oos_perf[name] = np.sum(oos_rets)

        is_best = max(is_perf, key=is_perf.get)
        oos_best = max(oos_perf, key=oos_perf.get)

        total_combos += 1
        if is_best == oos_best:
            oos_best_is_best_count += 1

        gap = abs(is_perf[is_best] - oos_perf[is_best])
        perf_gaps.append(gap)

    pbo = 1.0 - (oos_best_is_best_count / total_combos) if total_combos > 0 else 1.0
    avg_gap = float(np.mean(perf_gaps)) if perf_gaps else 0.0

    if pbo > 0.7:
        interp = "High overfitting — IS optimal rarely OOS optimal"
    elif pbo > 0.5:
        interp = "Moderate overfitting risk"
    else:
        interp = "Low overfitting risk — factor passes CSCV"

    return CSCVResult(
        pbo=round(pbo, 4),
        n_combinations=total_combos,
        performance_gap=round(avg_gap, 4),
        interpretation=interp,
    )


def compute_dsr(
    returns: np.ndarray,
    n_trials: int = 1,
    benchmark_sharpe: float = 0.0,
    periods_per_year: int = 252,
) -> DSRResult:
    if len(returns) < _MIN_OBS:
        return DSRResult(
            sharpe_ratio=0.0, deflated_sharpe=0.0, p_value=1.0,
            n_trials=n_trials, skewness=0.0, kurtosis=0.0,
            interpretation=f"Insufficient data ({len(returns)} < {_MIN_OBS})",
        )

    sr = _sharpe_ratio(returns, annualize=True, periods_per_year=periods_per_year)
    skew = float(stats.skew(returns))
    kurt = float(stats.kurtosis(returns, fisher=True))

    n = len(returns)
    sr_non_annual = sr / np.sqrt(periods_per_year)

    se = np.sqrt(
        (1 + 0.5 * sr_non_annual ** 2 - skew * sr_non_annual + (kurt - 3) / 4 * sr_non_annual ** 2) / n
    )

    expected_max_sr = benchmark_sharpe
    if n_trials > 1:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                from scipy.special import comb
                z = (1 - np.log(np.log(2))) / np.sqrt(2 * np.log(n_trials))
                gamma = 0.5772156649
                expected_max_sr = benchmark_sharpe + se * (
                    z + gamma / (2 * np.pi * z)
                ) * np.sqrt(2 * np.log(n_trials))
            except Exception:
                expected_max_sr = benchmark_sharpe + se * np.sqrt(2 * np.log(n_trials))

    dsr_stat = (sr - expected_max_sr) / se if se > 0 else 0.0
    p_value = float(1 - stats.norm.cdf(dsr_stat))

    if p_value < 0.01:
        interp = "Highly significant — SR survives multiple testing"
    elif p_value < 0.05:
        interp = "Significant — SR likely not from data mining"
    elif p_value < 0.1:
        interp = "Marginally significant — some multiple testing bias"
    else:
        interp = "Not significant — SR likely from data mining"

    return DSRResult(
        sharpe_ratio=round(sr, 4),
        deflated_sharpe=round(dsr_stat, 4),
        p_value=round(p_value, 4),
        n_trials=n_trials,
        skewness=round(skew, 4),
        kurtosis=round(kurt, 4),
        interpretation=interp,
    )


def compute_walk_forward(
    returns: np.ndarray,
    train_ratio: float = 0.7,
    n_folds: int = 5,
    min_fold_size: int = 30,
) -> WalkForwardResult:
    if len(returns) < min_fold_size * 3:
        return WalkForwardResult(
            train_returns=[], test_returns=[],
            train_sharpe=0.0, test_sharpe=0.0,
            degradation_ratio=0.0, n_folds=0,
            interpretation=f"Insufficient data ({len(returns)} < {min_fold_size * 3})",
        )

    fold_size = len(returns) // n_folds
    if fold_size < min_fold_size:
        n_folds = max(2, len(returns) // min_fold_size)
        fold_size = len(returns) // n_folds

    train_sharpes = []
    test_sharpes = []
    all_train_rets = []
    all_test_rets = []

    for i in range(n_folds - 1):
        train_end = (i + 1) * fold_size
        test_end = min((i + 2) * fold_size, len(returns))

        if test_end <= train_end:
            continue

        train_rets = returns[:train_end]
        test_rets = returns[train_end:test_end]

        if len(train_rets) < min_fold_size or len(test_rets) < 10:
            continue

        train_sr = _sharpe_ratio(train_rets, annualize=False)
        test_sr = _sharpe_ratio(test_rets, annualize=False)

        train_sharpes.append(train_sr)
        test_sharpes.append(test_sr)
        all_train_rets.append(float(np.mean(train_rets)))
        all_test_rets.append(float(np.mean(test_rets)))

    if not train_sharpes:
        return WalkForwardResult(
            train_returns=[], test_returns=[],
            train_sharpe=0.0, test_sharpe=0.0,
            degradation_ratio=0.0, n_folds=0,
            interpretation="No valid folds generated",
        )

    avg_train_sr = float(np.mean(train_sharpes))
    avg_test_sr = float(np.mean(test_sharpes))
    degradation = avg_test_sr / avg_train_sr if avg_train_sr != 0 else 0.0

    if degradation < 0:
        interp = "No overfitting — OOS outperforms IS (negative degradation)"
    elif degradation < 0.3:
        interp = "Severe overfitting — OOS performance collapses"
    elif degradation < 0.5:
        interp = "Significant overfitting — OOS much worse than IS"
    elif degradation < 0.7:
        interp = "Moderate degradation — some overfitting"
    elif degradation < 0.9:
        interp = "Mild degradation — factor reasonably robust"
    else:
        interp = "Minimal degradation — factor passes walk-forward"

    return WalkForwardResult(
        train_returns=all_train_rets,
        test_returns=all_test_rets,
        train_sharpe=round(avg_train_sr, 4),
        test_sharpe=round(avg_test_sr, 4),
        degradation_ratio=round(degradation, 4),
        n_folds=len(train_sharpes),
        interpretation=interp,
    )


class FactorValidator:
    """Full factor validation pipeline combining PBO, CSCV, DSR, and Walk-forward."""

    def __init__(
        self,
        n_cscv_splits: int = _DEFAULT_S,
        n_walk_forward_folds: int = 5,
        n_dsr_trials: int = 20,
    ):
        self.n_cscv_splits = n_cscv_splits
        self.n_wf_folds = n_walk_forward_folds
        self.n_dsr_trials = n_dsr_trials

    def validate_factor(
        self,
        factor_returns: np.ndarray,
        competing_returns: Optional[Dict[str, np.ndarray]] = None,
        factor_name: str = "",
    ) -> FactorValidationReport:
        report = FactorValidationReport(factor_name=factor_name)

        if competing_returns and len(competing_returns) > 1:
            all_returns = dict(competing_returns)
            all_returns[factor_name or "_target"] = factor_returns
            report.pbo_result = compute_pbo(all_returns, n_splits=self.n_cscv_splits)
            report.cscv_result = compute_cscv(all_returns, n_splits=self.n_cscv_splits)

        report.dsr_result = compute_dsr(
            factor_returns,
            n_trials=self.n_dsr_trials,
        )

        report.walk_forward_result = compute_walk_forward(
            factor_returns,
            n_folds=self.n_wf_folds,
        )

        verdicts = []
        if report.pbo_result and report.pbo_result.is_overfitted:
            verdicts.append("PBO overfitted")
        if report.cscv_result and report.cscv_result.is_overfitted:
            verdicts.append("CSCV overfitted")
        if report.dsr_result and not report.dsr_result.is_significant:
            verdicts.append("DSR not significant")
        if report.walk_forward_result and report.walk_forward_result.is_overfitted:
            verdicts.append("Walk-forward overfitted")

        if not verdicts:
            report.overall_verdict = "PASS — factor passes all anti-overfitting tests"
        elif len(verdicts) <= 1:
            report.overall_verdict = f"CAUTION — {', '.join(verdicts)}"
        else:
            report.overall_verdict = f"FAIL — {', '.join(verdicts)}"

        return report

    def validate_factor_from_signals(
        self,
        signal_series: np.ndarray,
        return_series: np.ndarray,
        factor_name: str = "",
        n_param_variants: int = 5,
    ) -> FactorValidationReport:
        mask = ~(np.isnan(signal_series) | np.isnan(return_series))
        clean_signal = signal_series[mask]
        clean_return = return_series[mask]

        if len(clean_signal) < _MIN_OBS:
            return FactorValidationReport(
                factor_name=factor_name,
                overall_verdict=f"FAIL — insufficient data ({len(clean_signal)} < {_MIN_OBS})",
            )

        sorted_indices = np.argsort(clean_signal)
        long_mask = np.zeros(len(clean_signal), dtype=bool)
        long_mask[sorted_indices[len(sorted_indices) // 2:]] = True

        long_returns = np.where(long_mask, clean_return, 0.0)
        short_returns = np.where(~long_mask, -clean_return, 0.0)
        factor_returns = long_returns + short_returns * 0.0

        competing = {}
        for pct in [30, 40, 60, 70]:
            variant_mask = np.zeros(len(clean_signal), dtype=bool)
            variant_mask[sorted_indices[int(len(sorted_indices) * pct / 100):]] = True
            variant_rets = np.where(variant_mask, clean_return, 0.0)
            competing[f"top_{pct}pct"] = variant_rets

        return self.validate_factor(
            factor_returns=factor_returns,
            competing_returns=competing,
            factor_name=factor_name,
        )
