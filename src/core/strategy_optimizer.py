# -*- coding: utf-8 -*-
"""Strategy parameter optimizer with anti-overfitting mechanisms.

Uses historical backtest results to adjust strategy weights and thresholds.
Anti-overfitting is enforced via:
1. Walk-forward validation (train / validation split)
2. Parameter regularization (penalize extreme values)
3. Minimum sample size requirement
4. Out-of-sample degradation check
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

def _get_data_dir() -> str:
    from pathlib import Path
    db_path = os.getenv("DATABASE_PATH", "./data/stock_analysis.db")
    return str(Path(db_path).resolve().parent)


_OPTIMIZER_STATE_FILE = os.path.join(_get_data_dir(), "strategy_optimizer_state.json")

_MIN_TRAIN_SAMPLES = 30  # 推荐的最小训练集样本量，低于此值将触发低置信度降级
_MIN_VAL_SAMPLES = 15  # 推荐的最小验证集样本量，低于此值将触发低置信度降级
_ABS_MIN_TRAIN_SAMPLES = 10  # 训练集绝对最小样本量，低于此值跳过该策略优化
_ABS_MIN_VAL_SAMPLES = 5  # 验证集绝对最小样本量，低于此值跳过整体优化
_LOW_SAMPLE_CONFIDENCE_PENALTY = 0.5  # 低样本量时权重调整幅度的衰减系数
_MAX_WEIGHT_RATIO = 3.0
_REGULARIZATION_LAMBDA = 0.1
_DEGRADATION_THRESHOLD = 0.8


@dataclass
class StrategyPerformance:
    strategy_name: str
    total_signals: int = 0
    triggered_count: int = 0
    avg_score_when_triggered: float = 0.0
    win_rate: float = 0.0
    avg_return_when_triggered: float = 0.0
    avg_return_when_not_triggered: float = 0.0
    sample_count: int = 0


@dataclass
class OptimizationResult:
    strategy_name: str
    original_weight: float
    optimized_weight: float
    adjustment_reason: str = ""
    train_win_rate: float = 0.0
    val_win_rate: float = 0.0
    degradation_ratio: float = 1.0
    accepted: bool = True


@dataclass
class OptimizerState:
    last_optimization_date: str = ""
    optimization_count: int = 0
    strategy_weights: Dict[str, float] = field(default_factory=dict)
    optimization_history: List[Dict[str, Any]] = field(default_factory=list)

    def save(self, path: str = _OPTIMIZER_STATE_FILE) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "last_optimization_date": self.last_optimization_date,
                "optimization_count": self.optimization_count,
                "strategy_weights": self.strategy_weights,
                "optimization_history": self.optimization_history[-50:],
            }, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str = _OPTIMIZER_STATE_FILE) -> "OptimizerState":
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                last_optimization_date=data.get("last_optimization_date", ""),
                optimization_count=data.get("optimization_count", 0),
                strategy_weights=data.get("strategy_weights", {}),
                optimization_history=data.get("optimization_history", []),
            )
        except Exception as e:
            logger.warning("[Optimizer] 加载状态文件失败: %s", e)
            return cls()


class StrategyOptimizer:
    """Optimize strategy weights from backtest results with anti-overfitting."""

    def __init__(self, base_weights: Optional[Dict[str, float]] = None):
        from src.core.market_regime import STRATEGY_BASE_WEIGHTS
        self.base_weights = base_weights or dict(STRATEGY_BASE_WEIGHTS)
        self.state = OptimizerState.load()
        if self.state.strategy_weights:
            logger.info(
                "[Optimizer] 加载已有优化状态: %d 个策略权重 (上次优化: %s)",
                len(self.state.strategy_weights),
                self.state.last_optimization_date,
            )

    def get_effective_weights(self) -> Dict[str, float]:
        if self.state.strategy_weights:
            return dict(self.state.strategy_weights)
        return dict(self.base_weights)

    def get_optimization_details(self) -> Dict[str, Any]:
        before = dict(self.base_weights)
        after = dict(self.base_weights)
        modified = self.state.strategy_weights
        if modified:
            after.update(modified)

        changes = []
        for name, base_w in before.items():
            opt_w = after.get(name, base_w)
            if abs(opt_w - base_w) > 0.001:
                direction = "up" if opt_w > base_w else "down"
                change_pct = round((opt_w - base_w) / base_w * 100, 1) if base_w > 0 else 0
                changes.append({
                    "strategy": name,
                    "original_weight": round(base_w, 3),
                    "optimized_weight": round(opt_w, 3),
                    "change_pct": change_pct,
                    "direction": direction,
                })

        changes.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        total_param = len(before)
        changed_count = len(changes)

        return {
            "last_optimization_date": self.state.last_optimization_date,
            "optimization_count": self.state.optimization_count,
            "total_strategies": total_param,
            "modified_strategies": changed_count,
            "weights_before": {k: round(v, 3) for k, v in before.items()},
            "weights_after": {k: round(v, 3) for k, v in after.items()},
            "changes": changes,
            "history": self.state.optimization_history[-10:],
        }

    def optimize_from_backtest(
        self,
        backtest_records: List[Dict[str, Any]],
        current_regime: str = "sideways",
    ) -> Dict[str, OptimizationResult]:
        abs_min_total = _ABS_MIN_TRAIN_SAMPLES + _ABS_MIN_VAL_SAMPLES
        if len(backtest_records) < abs_min_total:
            logger.warning(
                "[Optimizer] 样本严重不足 (%d < %d)，跳过优化",
                len(backtest_records), abs_min_total,
            )
            return {}

        split_idx = int(len(backtest_records) * 0.7)
        train_set = backtest_records[:split_idx]
        val_set = backtest_records[split_idx:]

        if len(train_set) < _ABS_MIN_TRAIN_SAMPLES or len(val_set) < _ABS_MIN_VAL_SAMPLES:
            logger.warning(
                "[Optimizer] 训练/验证集样本不足 (train=%d, val=%d)，跳过优化",
                len(train_set), len(val_set),
            )
            return {}

        low_confidence = (
            len(train_set) < _MIN_TRAIN_SAMPLES or len(val_set) < _MIN_VAL_SAMPLES
        )
        if low_confidence:
            logger.warning(
                "[Optimizer] 样本低于推荐量 (train=%d<%d, val=%d<%d)，降级优化 (权重调整幅度 ×%.1f)",
                len(train_set), _MIN_TRAIN_SAMPLES,
                len(val_set), _MIN_VAL_SAMPLES,
                _LOW_SAMPLE_CONFIDENCE_PENALTY,
            )

        train_perf = self._compute_strategy_performance(train_set)
        val_perf = self._compute_strategy_performance(val_set)

        results: Dict[str, OptimizationResult] = {}
        new_weights: Dict[str, float] = {}

        for name, base_w in self.base_weights.items():
            train_p = train_perf.get(name)
            val_p = val_perf.get(name)

            if train_p is None or train_p.sample_count < _ABS_MIN_TRAIN_SAMPLES:
                new_weights[name] = base_w
                results[name] = OptimizationResult(
                    strategy_name=name,
                    original_weight=base_w,
                    optimized_weight=base_w,
                    adjustment_reason="样本不足，保持基础权重",
                    accepted=True,
                )
                continue

            raw_adjustment = self._compute_weight_adjustment(train_p, base_w)
            regularized = self._apply_regularization(raw_adjustment, base_w)

            if low_confidence:
                regularized = base_w + (regularized - base_w) * _LOW_SAMPLE_CONFIDENCE_PENALTY

            train_wr = train_p.win_rate
            val_wr = val_p.win_rate if val_p else 0.0
            degradation = val_wr / train_wr if train_wr > 0 else 1.0

            accepted = True
            reason = ""

            if degradation < _DEGRADATION_THRESHOLD:
                accepted = False
                reason = f"过拟合风险 (验证/训练={degradation:.2f}<{_DEGRADATION_THRESHOLD})"
                final_w = base_w
            else:
                final_w = regularized
                if final_w > base_w:
                    reason = f"表现优秀 (训练胜率={train_wr:.1%})"
                elif final_w < base_w:
                    reason = f"表现不佳 (训练胜率={train_wr:.1%})"
                else:
                    reason = "表现中性，维持基础权重"

            if low_confidence and accepted:
                reason += " [低样本降级]"

            new_weights[name] = round(final_w, 3)
            results[name] = OptimizationResult(
                strategy_name=name,
                original_weight=base_w,
                optimized_weight=round(final_w, 3),
                adjustment_reason=reason,
                train_win_rate=round(train_wr, 3),
                val_win_rate=round(val_wr, 3),
                degradation_ratio=round(degradation, 3),
                accepted=accepted,
            )

        self.state.strategy_weights = new_weights
        self.state.last_optimization_date = date.today().isoformat()
        self.state.optimization_count += 1
        self.state.optimization_history.append({
            "date": self.state.last_optimization_date,
            "regime": current_regime,
            "sample_count": len(backtest_records),
            "accepted_count": sum(1 for r in results.values() if r.accepted),
            "rejected_count": sum(1 for r in results.values() if not r.accepted),
        })
        self.state.save()

        logger.info(
            "[Optimizer] 优化完成: %d 策略接受, %d 策略拒绝",
            sum(1 for r in results.values() if r.accepted),
            sum(1 for r in results.values() if not r.accepted),
        )
        return results

    def initialize_from_history(
        self,
        days_back: int = 15,
        stock_codes: Optional[List[str]] = None,
    ) -> Dict[str, OptimizationResult]:
        logger.info("[Optimizer] 开始历史数据初始化 (回溯 %d 天)...", days_back)
        records = self._collect_historical_records(days_back, stock_codes)

        if not records:
            logger.warning("[Optimizer] 无法收集历史记录，使用默认权重")
            return {}

        from src.core.market_regime import MarketRegimeDetector
        detector = MarketRegimeDetector()
        regime_result = detector.detect()

        return self.optimize_from_backtest(records, current_regime=regime_result.regime)

    def _compute_strategy_performance(
        self,
        records: List[Dict[str, Any]],
    ) -> Dict[str, StrategyPerformance]:
        perf: Dict[str, StrategyPerformance] = {}

        for rec in records:
            strategy_scores = rec.get("strategy_scores", {})
            triggered = strategy_scores.get("triggered_strategies", [])
            return_pct = rec.get("return_pct")

            if return_pct is None:
                continue

            is_win = return_pct > 0

            triggered_names = set()
            for s in triggered:
                name = s.get("name", "")
                triggered_names.add(name)
                if name not in perf:
                    perf[name] = StrategyPerformance(strategy_name=name)
                p = perf[name]
                p.triggered_count += 1
                p.sample_count += 1
                p.avg_score_when_triggered = (
                    (p.avg_score_when_triggered * (p.triggered_count - 1) + s.get("score", 0))
                    / p.triggered_count
                )
                p.win_rate = (
                    (p.win_rate * (p.triggered_count - 1) + (1 if is_win else 0))
                    / p.triggered_count
                )
                p.avg_return_when_triggered = (
                    (p.avg_return_when_triggered * (p.triggered_count - 1) + return_pct)
                    / p.triggered_count
                )

            for name in self.base_weights:
                if name not in triggered_names:
                    if name not in perf:
                        perf[name] = StrategyPerformance(strategy_name=name)
                    perf[name].total_signals += 1
                    perf[name].sample_count += 1
                    perf[name].avg_return_when_not_triggered = (
                        (perf[name].avg_return_when_not_triggered * (perf[name].sample_count - 1) + return_pct)
                        / perf[name].sample_count
                    )

        return perf

    def _compute_weight_adjustment(
        self,
        perf: StrategyPerformance,
        base_weight: float,
    ) -> float:
        if perf.sample_count < _MIN_TRAIN_SAMPLES:
            return base_weight

        wr = perf.win_rate
        avg_ret = perf.avg_return_when_triggered

        score = 0.0
        if wr > 0.6:
            score += 0.3
        elif wr > 0.5:
            score += 0.1
        elif wr < 0.35:
            score -= 0.3

        if avg_ret > 3.0:
            score += 0.2
        elif avg_ret > 1.0:
            score += 0.1
        elif avg_ret < -3.0:
            score -= 0.2

        adjustment = base_weight * (1 + score)
        return max(0.1, adjustment)

    def _apply_regularization(self, raw_weight: float, base_weight: float) -> float:
        ratio = raw_weight / base_weight if base_weight > 0 else 1.0
        if ratio > _MAX_WEIGHT_RATIO:
            raw_weight = base_weight * _MAX_WEIGHT_RATIO
        elif ratio < 1.0 / _MAX_WEIGHT_RATIO:
            raw_weight = base_weight / _MAX_WEIGHT_RATIO

        regularized = raw_weight * (1 - _REGULARIZATION_LAMBDA) + base_weight * _REGULARIZATION_LAMBDA
        return regularized

    def _collect_historical_records(
        self,
        days_back: int,
        stock_codes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        try:
            from src.storage import DatabaseManager
            from src.storage import ScreenerResult
            from sqlalchemy import and_, select

            db = DatabaseManager.get_instance()
            cutoff = date.today() - timedelta(days=days_back)

            with db.get_session() as session:
                conditions = [
                    ScreenerResult.screen_date >= cutoff,
                    ScreenerResult.return_pct.isnot(None),
                ]
                if stock_codes:
                    conditions.append(ScreenerResult.code.in_(stock_codes))

                rows = session.execute(
                    select(ScreenerResult).where(and_(*conditions))
                    .order_by(ScreenerResult.screen_date.desc())
                    .limit(500)
                ).scalars().all()

                for r in rows:
                    signals = {}
                    if r.signals_json:
                        try:
                            signals = json.loads(r.signals_json)
                        except (TypeError, ValueError):
                            pass
                    records.append({
                        "code": r.code,
                        "screen_date": r.screen_date.isoformat() if r.screen_date else None,
                        "return_pct": r.return_pct,
                        "strategy_scores": signals.get("strategy_scores", {}),
                    })

            logger.info("[Optimizer] 从数据库收集到 %d 条历史记录", len(records))
        except Exception as e:
            logger.warning("[Optimizer] 收集历史记录失败: %s", e)

        if not records:
            records = self._simulate_historical_records(days_back, stock_codes)

        return records

    def _simulate_historical_records(
        self,
        days_back: int,
        stock_codes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        logger.info("[Optimizer] 数据库无历史记录，尝试模拟初始化...")
        records: List[Dict[str, Any]] = []

        try:
            from src.core.screener_engine import ScreenerEngine, ScreenerConfig
            from src.core.strategy_signal_extractor import StrategySignalExtractor
            from src.core.market_regime import MarketRegimeDetector

            codes = stock_codes or [
                "600519", "000858", "601318", "600036", "000333",
                "002415", "600276", "000651", "601888", "002352",
                "600809", "000568", "601012", "002475", "600690",
            ]

            detector = MarketRegimeDetector()
            regime_result = detector.detect()
            extractor = StrategySignalExtractor(market_regime=regime_result.regime)

            for code in codes:
                try:
                    hist_df = self._fetch_history_for_init(code, days_back + 90)
                    if hist_df is None or len(hist_df) < 30:
                        continue

                    for offset_day in range(0, min(days_back, len(hist_df) - 30)):
                        idx = len(hist_df) - 1 - offset_day
                        if idx < 30:
                            break
                        window = hist_df.iloc[max(0, idx - 60):idx + 1].copy()

                        if len(window) < 20:
                            continue

                        strat_signals = extractor.extract_all(window)
                        triggered = [
                            {
                                "name": s.strategy_name,
                                "score": s.score,
                                "weight": 1.0,
                            }
                            for s in strat_signals
                            if s.triggered and s.score > 0
                        ]

                        future_idx = min(idx + 5, len(hist_df) - 1)
                        if future_idx <= idx:
                            continue
                        current_close = float(hist_df.iloc[idx]["close"])
                        future_close = float(hist_df.iloc[future_idx]["close"])
                        ret_pct = round((future_close - current_close) / current_close * 100, 2)

                        records.append({
                            "code": code,
                            "screen_date": str(hist_df.iloc[idx].get("date", "")),
                            "return_pct": ret_pct,
                            "strategy_scores": {"triggered_strategies": triggered},
                        })
                except Exception as e:
                    logger.debug("[Optimizer] 模拟 %s 失败: %s", code, e)
                    continue

            logger.info("[Optimizer] 模拟生成 %d 条历史记录", len(records))
        except Exception as e:
            logger.warning("[Optimizer] 模拟初始化失败: %s", e)

        return records

    def _fetch_history_for_init(
        self,
        code: str,
        days: int,
    ) -> Optional[Any]:
        try:
            from data_provider.factory import DataProviderFactory
            factory = DataProviderFactory()
            end = date.today()
            start = end - timedelta(days=days)
            df = factory.get_daily_history(code, start_date=start, end_date=end)
            if df is not None and not df.empty:
                if 'date' in df.columns:
                    df = df.sort_values('date').reset_index(drop=True)
                return df
        except Exception as e:
            logger.debug("[Optimizer] 获取 %s 历史数据失败: %s", code, e)
        return None

    def optimize_from_ic(
        self,
        ic_summaries: Dict[str, Any],
        rotation_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, OptimizationResult]:
        logger.info("[Optimizer] 开始 IC 驱动优化: %d 个因子", len(ic_summaries))
        results: Dict[str, OptimizationResult] = {}
        new_weights: Dict[str, float] = {}

        for name, base_w in self.base_weights.items():
            ic_info = ic_summaries.get(name)
            if ic_info is None:
                new_weights[name] = base_w
                results[name] = OptimizationResult(
                    strategy_name=name,
                    original_weight=base_w,
                    optimized_weight=base_w,
                    adjustment_reason="无 IC 数据，保持基础权重",
                    accepted=True,
                )
                continue

            mean_ic = ic_info.get("mean_ic", 0) if isinstance(ic_info, dict) else getattr(ic_info, "mean_ic", 0)
            icir = ic_info.get("icir", 0) if isinstance(ic_info, dict) else getattr(ic_info, "icir", 0)
            is_effective = ic_info.get("is_effective", False) if isinstance(ic_info, dict) else getattr(ic_info, "is_effective", False)

            score = 0.0
            if is_effective:
                score += 0.2
            if abs(icir) > 0.5:
                score += 0.2
            elif abs(icir) > 0.3:
                score += 0.1
            elif abs(icir) < 0.1:
                score -= 0.2

            if mean_ic > 0.05:
                score += 0.15
            elif mean_ic < -0.03:
                score -= 0.3

            adjusted = base_w * (1 + score)
            adjusted = max(0.1, min(adjusted, base_w * _MAX_WEIGHT_RATIO))
            regularized = adjusted * (1 - _REGULARIZATION_LAMBDA) + base_w * _REGULARIZATION_LAMBDA

            if rotation_weights and name in rotation_weights:
                rot_w = rotation_weights[name]
                regularized = regularized * 0.7 + rot_w * base_w * 0.3

            new_weights[name] = round(regularized, 3)
            reason = f"IC={mean_ic:.3f}, ICIR={icir:.3f}"
            if is_effective:
                reason += ", 因子有效"
            else:
                reason += ", 因子效果不显著"

            results[name] = OptimizationResult(
                strategy_name=name,
                original_weight=base_w,
                optimized_weight=round(regularized, 3),
                adjustment_reason=reason,
                accepted=is_effective or abs(icir) > 0.3,
            )

        self.state.strategy_weights = new_weights
        self.state.last_optimization_date = date.today().isoformat()
        self.state.optimization_count += 1
        self.state.optimization_history.append({
            "date": self.state.last_optimization_date,
            "method": "ic_driven",
            "accepted_count": sum(1 for r in results.values() if r.accepted),
            "rejected_count": sum(1 for r in results.values() if not r.accepted),
        })
        self.state.save()

        logger.info(
            "[Optimizer] IC 驱动优化完成: %d 接受, %d 拒绝",
            sum(1 for r in results.values() if r.accepted),
            sum(1 for r in results.values() if not r.accepted),
        )
        return results

    def optimize_from_validation(
        self,
        validation_reports: Dict[str, Any],
    ) -> Dict[str, OptimizationResult]:
        logger.info("[Optimizer] 开始验证驱动优化: %d 个因子", len(validation_reports))
        results: Dict[str, OptimizationResult] = {}
        new_weights: Dict[str, float] = {}

        for name, base_w in self.base_weights.items():
            report = validation_reports.get(name)
            if report is None:
                new_weights[name] = base_w
                results[name] = OptimizationResult(
                    strategy_name=name,
                    original_weight=base_w,
                    optimized_weight=base_w,
                    adjustment_reason="无验证报告，保持基础权重",
                    accepted=True,
                )
                continue

            is_valid = report.get("is_valid", True) if isinstance(report, dict) else getattr(report, "is_valid", True)
            verdict = report.get("overall_verdict", "") if isinstance(report, dict) else getattr(report, "overall_verdict", "")

            pbo_val = report.get("pbo_result", {}) if isinstance(report, dict) else {}
            if hasattr(report, "pbo_result") and report.pbo_result:
                pbo_val = {"pbo": report.pbo_result.pbo}

            dsr_val = report.get("dsr_result", {}) if isinstance(report, dict) else {}
            if hasattr(report, "dsr_result") and report.dsr_result:
                dsr_val = {"p_value": report.dsr_result.p_value}

            if not is_valid:
                adjusted = base_w * 0.3
                reason = f"验证未通过: {verdict}"
                accepted = False
            else:
                score = 0.0
                pbo = pbo_val.get("pbo", 0) if isinstance(pbo_val, dict) else 0
                if pbo < 0.3:
                    score += 0.2
                elif pbo > 0.5:
                    score -= 0.2

                dsr_p = dsr_val.get("p_value", 1) if isinstance(dsr_val, dict) else 1
                if dsr_p < 0.05:
                    score += 0.15
                elif dsr_p > 0.2:
                    score -= 0.1

                adjusted = base_w * (1 + score)
                adjusted = max(0.1, min(adjusted, base_w * _MAX_WEIGHT_RATIO))
                regularized = adjusted * (1 - _REGULARIZATION_LAMBDA) + base_w * _REGULARIZATION_LAMBDA
                adjusted = regularized
                reason = f"PBO={pbo:.2f}, DSR_p={dsr_p:.3f}"
                accepted = True

            new_weights[name] = round(adjusted, 3)
            results[name] = OptimizationResult(
                strategy_name=name,
                original_weight=base_w,
                optimized_weight=round(adjusted, 3),
                adjustment_reason=reason,
                accepted=accepted,
            )

        self.state.strategy_weights = new_weights
        self.state.last_optimization_date = date.today().isoformat()
        self.state.optimization_count += 1
        self.state.optimization_history.append({
            "date": self.state.last_optimization_date,
            "method": "validation_driven",
            "accepted_count": sum(1 for r in results.values() if r.accepted),
            "rejected_count": sum(1 for r in results.values() if not r.accepted),
        })
        self.state.save()

        logger.info(
            "[Optimizer] 验证驱动优化完成: %d 接受, %d 拒绝",
            sum(1 for r in results.values() if r.accepted),
            sum(1 for r in results.values() if not r.accepted),
        )
        return results
