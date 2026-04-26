# -*- coding: utf-8 -*-
"""
Factor Rotation Monitor — dynamic factor weight adjustment based on IC/ICIR.

Monitors factor effectiveness over time and rotates weights:
- Factors with declining IC/ICIR get reduced weight
- Factors with stable/rising IC/ICIR get increased weight
- Smooth transition to avoid sudden portfolio shifts
- Minimum weight floor to prevent total exclusion

Rotation logic:
1. Compute rolling IC/ICIR for each factor
2. Score each factor: score = ICIR * positive_ratio * stability
3. Normalize scores to weights with min/max bounds
4. Apply exponential smoothing for gradual transitions
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_STATE_DIR = os.path.join("data", "factor_rotation")
_STATE_FILE = os.path.join(_STATE_DIR, "rotation_state.json")

_MIN_WEIGHT = 0.05
_MAX_WEIGHT = 0.25
_SMOOTHING_ALPHA = 0.3
_ICIR_THRESHOLD = 0.5
_POSITIVE_RATIO_THRESHOLD = 0.55
_LOOKBACK_DAYS = 60
_MONITOR_WINDOW = 20


@dataclass
class FactorHealth:
    factor_name: str
    current_ic: float = 0.0
    current_icir: float = 0.0
    positive_ratio: float = 0.5
    ic_trend: float = 0.0
    stability: float = 1.0
    health_score: float = 0.5
    status: str = "normal"

    @property
    def is_healthy(self) -> bool:
        return self.status in ("normal", "watch")


@dataclass
class RotationState:
    last_update: str = ""
    factor_weights: Dict[str, float] = field(default_factory=dict)
    factor_health_history: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    rotation_count: int = 0

    def save(self, path: str = _STATE_FILE) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "last_update": self.last_update,
                "factor_weights": self.factor_weights,
                "factor_health_history": {
                    k: v[-30:] for k, v in self.factor_health_history.items()
                },
                "rotation_count": self.rotation_count,
            }, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str = _STATE_FILE) -> "RotationState":
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                last_update=data.get("last_update", ""),
                factor_weights=data.get("factor_weights", {}),
                factor_health_history=data.get("factor_health_history", {}),
                rotation_count=data.get("rotation_count", 0),
            )
        except Exception:
            return cls()


def _compute_ic_series(
    factor_values: np.ndarray,
    returns: np.ndarray,
    window: int = _MONITOR_WINDOW,
) -> List[float]:
    if len(factor_values) < window or len(returns) < window:
        return []
    from scipy import stats as sp_stats
    ic_list = []
    for i in range(window, len(factor_values) + 1):
        f_slice = factor_values[i - window:i]
        r_slice = returns[i - window:i]
        mask = ~(np.isnan(f_slice) | np.isnan(r_slice))
        if mask.sum() < 10:
            ic_list.append(0.0)
            continue
        corr, _ = sp_stats.spearmanr(f_slice[mask], r_slice[mask])
        ic_list.append(float(corr) if not np.isnan(corr) else 0.0)
    return ic_list


def _compute_health_score(
    icir: float,
    positive_ratio: float,
    ic_trend: float,
    stability: float,
) -> float:
    score = 0.0
    score += min(abs(icir), 2.0) / 2.0 * 0.4
    score += positive_ratio * 0.25
    score += max(0, ic_trend) * 0.15
    score += stability * 0.2
    return min(max(score, 0.0), 1.0)


def _determine_status(health_score: float, icir: float, positive_ratio: float) -> str:
    if health_score >= 0.6 and icir >= _ICIR_THRESHOLD and positive_ratio >= _POSITIVE_RATIO_THRESHOLD:
        return "strong"
    elif health_score >= 0.4 and positive_ratio >= 0.5:
        return "normal"
    elif health_score >= 0.25:
        return "watch"
    else:
        return "weak"


class FactorRotationMonitor:
    """Monitor factor health and compute dynamic rotation weights."""

    def __init__(
        self,
        min_weight: float = _MIN_WEIGHT,
        max_weight: float = _MAX_WEIGHT,
        smoothing_alpha: float = _SMOOTHING_ALPHA,
    ):
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.smoothing_alpha = smoothing_alpha
        self.state = RotationState.load()

    def get_current_weights(self) -> Dict[str, float]:
        if self.state.factor_weights:
            return dict(self.state.factor_weights)
        return {}

    def assess_factor_health(
        self,
        factor_name: str,
        factor_values: np.ndarray,
        forward_returns: np.ndarray,
        window: int = _MONITOR_WINDOW,
    ) -> FactorHealth:
        ic_series = _compute_ic_series(factor_values, forward_returns, window)
        if not ic_series:
            return FactorHealth(
                factor_name=factor_name,
                status="insufficient_data",
            )

        mean_ic = float(np.mean(ic_series))
        std_ic = float(np.std(ic_series, ddof=1)) if len(ic_series) > 1 else 1.0
        icir = mean_ic / std_ic if std_ic > 0 else 0.0
        pos_ratio = sum(1 for v in ic_series if v > 0) / len(ic_series)

        if len(ic_series) >= 4:
            half = len(ic_series) // 2
            recent_ic = np.mean(ic_series[half:])
            older_ic = np.mean(ic_series[:half])
            ic_trend = float(recent_ic - older_ic)
        else:
            ic_trend = 0.0

        if len(ic_series) > 2:
            ic_changes = np.diff(ic_series)
            sign_consistency = sum(1 for d in ic_changes if d > 0) / len(ic_changes)
            stability = 1.0 - abs(sign_consistency - 0.5) * 2
        else:
            stability = 0.5

        health_score = _compute_health_score(icir, pos_ratio, ic_trend, stability)
        status = _determine_status(health_score, icir, pos_ratio)

        return FactorHealth(
            factor_name=factor_name,
            current_ic=round(mean_ic, 4),
            current_icir=round(icir, 4),
            positive_ratio=round(pos_ratio, 4),
            ic_trend=round(ic_trend, 4),
            stability=round(stability, 4),
            health_score=round(health_score, 4),
            status=status,
        )

    def compute_rotation_weights(
        self,
        health_reports: Dict[str, FactorHealth],
    ) -> Dict[str, float]:
        if not health_reports:
            return {}

        raw_weights = {}
        for name, health in health_reports.items():
            if health.status == "insufficient_data":
                raw_weights[name] = self.min_weight
            else:
                raw_weights[name] = max(health.health_score, self.min_weight)

        total = sum(raw_weights.values())
        if total == 0:
            n = len(raw_weights)
            return {k: 1.0 / n for k in raw_weights}

        normalized = {k: v / total for k, v in raw_weights.items()}

        clipped = {}
        for k, v in normalized.items():
            clipped[k] = max(self.min_weight, min(self.max_weight, v))

        total_clipped = sum(clipped.values())
        final = {k: round(v / total_clipped, 4) for k, v in clipped.items()}

        if self.state.factor_weights:
            smoothed = {}
            for k, v in final.items():
                old_v = self.state.factor_weights.get(k, v)
                smoothed[k] = round(
                    self.smoothing_alpha * v + (1 - self.smoothing_alpha) * old_v, 4
                )
            total_smoothed = sum(smoothed.values())
            if total_smoothed > 0:
                final = {k: round(v / total_smoothed, 4) for k, v in smoothed.items()}

        return final

    def update(
        self,
        factor_data: Dict[str, Tuple[np.ndarray, np.ndarray]],
    ) -> Dict[str, float]:
        health_reports = {}
        for name, (factor_vals, fwd_rets) in factor_data.items():
            health = self.assess_factor_health(name, factor_vals, fwd_rets)
            health_reports[name] = health

            if name not in self.state.factor_health_history:
                self.state.factor_health_history[name] = []
            self.state.factor_health_history[name].append({
                "date": date.today().isoformat(),
                "ic": health.current_ic,
                "icir": health.current_icir,
                "positive_ratio": health.positive_ratio,
                "health_score": health.health_score,
                "status": health.status,
            })

        new_weights = self.compute_rotation_weights(health_reports)

        self.state.factor_weights = new_weights
        self.state.last_update = date.today().isoformat()
        self.state.rotation_count += 1
        self.state.save()

        logger.info(
            "[FactorRotation] 更新完成: %d 因子, 权重=%s",
            len(new_weights),
            {k: round(v, 3) for k, v in new_weights.items()},
        )

        return new_weights

    def get_health_summary(self) -> Dict[str, Dict[str, Any]]:
        summary = {}
        for name, history in self.state.factor_health_history.items():
            if not history:
                continue
            latest = history[-1]
            summary[name] = {
                "status": latest.get("status", "unknown"),
                "health_score": latest.get("health_score", 0),
                "ic": latest.get("ic", 0),
                "icir": latest.get("icir", 0),
                "weight": self.state.factor_weights.get(name, 0),
            }
        return summary
