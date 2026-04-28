# -*- coding: utf-8 -*-
"""Strategy weight interpretation service — LLM-powered explanation of weight changes.

Takes StrategyOptimizer weight adjustment data + backtest performance data,
generates natural language explanations for why each strategy's weight changed.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

WEIGHT_INTERPRETATION_PROMPT = """你是一个量化策略分析师。请根据以下数据，用通俗易懂的中文（2-3句话）解释为什么某个策略的权重被调整了。

策略: {display_name} ({strategy_name})
权重变化: {original_weight} → {optimized_weight} ({direction}{change_pct}%)
调整来源: {source}

回测表现数据:
  - 最近回测次数: {total_signals}
  - 胜率: {win_rate}
  - 平均持仓收益: {avg_return}
  - 策略排名: {rank}/{total_strategies}
  - 过拟合风险: {overfit_risk}

当前市场状态: {market_regime}

请解释：
1. 为什么这个策略被加分/降权
2. 这个调整幅度是否合理
3. 有什么风险需要注意

要求：
- 输出纯文本，不要markdown
- 2-3句话即可
- 如果某指标不适用（如样本不足），说明原因
- 语气客观专业但易于理解"""


class WeightInterpretationService:

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 3600

    def generate(
        self,
        changes: List[Dict[str, Any]],
        backtest_context: Optional[Dict[str, Any]] = None,
        market_regime: str = "unknown",
    ) -> List[Dict[str, Any]]:
        interpretations = []

        for change in changes:
            strategy_name = change.get("strategy", "unknown")
            display_name = strategy_name
            try:
                from src.core.strategy_signal_extractor import StrategySignalExtractor
            except Exception:
                pass

            cache_key = f"{strategy_name}:{change.get('optimized_weight', 0)}"
            if cache_key in self._cache:
                entry = self._cache[cache_key]
                if time.time() - entry.get("ts", 0) < self._cache_ttl:
                    interpretations.append(entry["data"])
                    continue

            bp = backtest_context.get(strategy_name, {}) if backtest_context else {}
            direction = "↑" if change.get("direction") == "up" else "↓" if change.get("direction") == "down" else ""
            change_pct = abs(change.get("change_pct", 0))

            source = "回测反馈"
            perf_data = self._build_performance_summary(strategy_name, bp)

            prompt = WEIGHT_INTERPRETATION_PROMPT.format(
                display_name=display_name,
                strategy_name=strategy_name,
                original_weight=change.get("original_weight", 1.0),
                optimized_weight=change.get("optimized_weight", 1.0),
                direction=direction,
                change_pct=change_pct,
                source=source,
                total_signals=perf_data.get("total_signals", "N/A"),
                win_rate=perf_data.get("win_rate", "N/A"),
                avg_return=perf_data.get("avg_return", "N/A"),
                rank=perf_data.get("rank", "N/A"),
                total_strategies=perf_data.get("total_strategies", 26),
                overfit_risk=perf_data.get("overfit_risk", "N/A"),
                market_regime=market_regime,
            )

            llm_text = self._call_llm(prompt) if self._is_llm_available() else \
                self._rule_based_interpretation(strategy_name, change, perf_data, direction, change_pct)

            result = {
                "strategy": strategy_name,
                "display_name": display_name,
                "original_weight": change.get("original_weight", 0),
                "optimized_weight": change.get("optimized_weight", 0),
                "change_pct": change.get("change_pct", 0),
                "direction": change.get("direction", ""),
                "interpretation": llm_text,
                "performance_data": perf_data,
            }

            self._cache[cache_key] = {"ts": time.time(), "data": result}
            interpretations.append(result)

        return interpretations

    def _build_performance_summary(self, strategy_name: str, bp: Dict[str, Any]) -> Dict[str, Any]:
        summary = {"total_signals": "N/A", "win_rate": "N/A", "avg_return": "N/A",
                   "rank": "N/A", "total_strategies": 26, "overfit_risk": "N/A"}

        if bp.get("sample_count", 0) > 0:
            summary["total_signals"] = bp.get("sample_count", 0)
        if bp.get("win_rate") is not None:
            summary["win_rate"] = f"{bp['win_rate']:.1%}"
        if bp.get("avg_return") is not None:
            summary["avg_return"] = f"{bp['avg_return']:+.2f}%"

        if bp.get("degradation_ratio"):
            dr = bp["degradation_ratio"]
            if dr < 0.8:
                summary["overfit_risk"] = f"高 (验证/训练={dr:.2f})"
            elif dr < 0.95:
                summary["overfit_risk"] = f"中 (验证/训练={dr:.2f})"
            else:
                summary["overfit_risk"] = "低"

        if bp.get("rank"):
            summary["rank"] = bp["rank"]
            summary["total_strategies"] = bp.get("total", 26)

        return summary

    def _is_llm_available(self) -> bool:
        try:
            from src.config import get_config
            config = get_config()
            return bool(getattr(config, "gemini_api_key", None) or getattr(config, "openai_api_key", None))
        except Exception:
            return False

    def _call_llm(self, prompt: str) -> str:
        try:
            from src.analyzer import GeminiAnalyzer
            from src.config import get_config
            config = get_config()
            analyzer = GeminiAnalyzer(api_key=config.gemini_api_key)
            if analyzer.is_available():
                result = analyzer.generate_text(prompt, max_tokens=512, temperature=0.5)
                return result.strip() if result else self._rule_based_default()
        except Exception as e:
            logger.warning("LLM interpretation failed: %s", e)
        return self._rule_based_default()

    def _rule_based_default(self) -> str:
        return "暂无足够数据生成解读，请运行更多回测以获取策略表现数据。"

    def _rule_based_interpretation(
        self,
        strategy_name: str,
        change: Dict[str, Any],
        perf_data: Dict[str, Any],
        direction: str,
        change_pct: float,
    ) -> str:
        original = change.get("original_weight", 1.0)
        optimized = change.get("optimized_weight", 1.0)

        if abs(optimized - original) < 0.01:
            if perf_data.get("total_signals") == "N/A":
                return "该策略暂无足够回测数据（样本不足），保持默认权重不变。建议积累更多数据后再评估调整。"
            return "该策略回测表现中规中矩，维持现有权重不变。"

        if direction == "↑":
            wr = perf_data.get("win_rate", "N/A")
            if wr != "N/A":
                return f"该策略近30次回测胜率达{wr}，表现优于多数策略，因此权重从{original}上调至{optimized}（+{change_pct}%）。建议持续关注其在当前市场环境下的适应能力。"
            return f"该策略近期回测表现优异，因此权重从{original}上调至{optimized}（+{change_pct}%）。"
        else:
            overfit = perf_data.get("overfit_risk", "N/A")
            if overfit == "高":
                return f"该策略回测表现不稳定，且存在过拟合风险（验证集与训练集表现差异大），因此权重从{original}下调至{optimized}（-{change_pct}%）。建议暂时降低该策略在选股中的影响力。"
            return f"该策略近期回测表现不佳，因此权重从{original}下调至{optimized}（-{change_pct}%）。"
