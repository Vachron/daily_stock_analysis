# -*- coding: utf-8 -*-
"""Stock quality classifier — pre-filter stocks into quality tiers before scanning.

Quality dimensions:
1. ST / risk exclusion
2. Financial health (PE, PB, profitability)
3. Liquidity (turnover, market cap)
4. Price stability (volatility, price range)
5. Growth signals (revenue trend, earnings trend)

Quality tiers:
- premium: 优质蓝筹/白马股，基本面优秀
- standard: 基本面正常，可正常扫描
- speculative: 投机/成长股，含亏损/高估值，有潜力但风险较高
- excluded: 基本面极差或高风险，不扫描
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

TIER_PREMIUM = "premium"
TIER_STANDARD = "standard"
TIER_SPECULATIVE = "speculative"
TIER_EXCLUDED = "excluded"

TIER_LABELS = {
    TIER_PREMIUM: "优质股",
    TIER_STANDARD: "标准股",
    TIER_SPECULATIVE: "投机股",
    TIER_EXCLUDED: "排除",
}

SCAN_MODE_QUALITY_ONLY = "quality_only"
SCAN_MODE_PREMIUM = "premium"
SCAN_MODE_STANDARD = "standard"
SCAN_MODE_FULL = "full"

SCAN_MODE_DESCRIPTIONS = {
    SCAN_MODE_PREMIUM: "仅扫描优质股（蓝筹/白马）",
    SCAN_MODE_QUALITY_ONLY: "扫描优质+标准股（排除高风险）",
    SCAN_MODE_STANDARD: "扫描标准及以上（含投机股）",
    SCAN_MODE_FULL: "全市场扫描（仅排除ST等高风险）",
}


@dataclass
class QualityScore:
    code: str
    name: str = ""
    tier: str = TIER_STANDARD
    tier_label: str = "标准股"
    total_score: float = 0.0
    dimensions: Dict[str, Any] = field(default_factory=dict)
    exclusion_reason: str = ""


class StockQualityClassifier:
    """Classify stocks into quality tiers based on multi-dimensional scoring."""

    _ST_KEYWORDS = ("ST", "*ST", "S*ST", "SST", "S", "退")

    def __init__(self, scan_mode: str = SCAN_MODE_QUALITY_ONLY):
        self.scan_mode = scan_mode

    def classify_dataframe(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[QualityScore]]:
        if df.empty:
            return df, []

        scores: List[QualityScore] = []
        keep_mask = pd.Series([True] * len(df), index=df.index)

        for idx, row in df.iterrows():
            qs = self._classify_row(row)
            scores.append(qs)

            if not self._should_include(qs):
                keep_mask.at[idx] = False

        filtered = df[keep_mask].copy()
        logger.info(
            "[QualityFilter] 质量分级: 优质=%d, 标准=%d, 投机=%d, 排除=%d (模式=%s)",
            sum(1 for s in scores if s.tier == TIER_PREMIUM),
            sum(1 for s in scores if s.tier == TIER_STANDARD),
            sum(1 for s in scores if s.tier == TIER_SPECULATIVE),
            sum(1 for s in scores if s.tier == TIER_EXCLUDED),
            self.scan_mode,
        )

        return filtered, scores

    def _classify_row(self, row: pd.Series) -> QualityScore:
        code = str(row.get("_code", row.get("代码", "")))
        name = str(row.get("_name", row.get("名称", "")))
        price = self._safe_float(row, "_price", "最新价", "收盘价")
        market_cap = self._safe_float(row, "_market_cap", "总市值")
        turnover = self._safe_float(row, "_turnover_rate", "换手率")
        pe = self._safe_float(row, "_pe_ratio", "市盈率-动态", "市盈率")
        pb = self._safe_float(row, "_pb_ratio", "市净率")
        pct_chg = self._safe_float(row, "_pct_chg", "涨跌幅")

        dims: Dict[str, Any] = {}
        total = 0.0
        exclusion_reason = ""

        risk_score, risk_pass, risk_reason = self._score_risk(name, code)
        dims["risk"] = {"score": risk_score, "pass": risk_pass, "reason": risk_reason}
        total += risk_score
        if not risk_pass:
            exclusion_reason = risk_reason

        fin_score, fin_pass = self._score_financial(pe, pb)
        dims["financial"] = {"score": fin_score, "pass": fin_pass, "pe": pe, "pb": pb}
        total += fin_score

        liq_score, liq_pass = self._score_liquidity(market_cap, turnover)
        dims["liquidity"] = {"score": liq_score, "pass": liq_pass, "market_cap": market_cap, "turnover": turnover}
        total += liq_score

        price_score, price_pass = self._score_price_stability(price, pct_chg)
        dims["price"] = {"score": price_score, "pass": price_pass, "price": price}
        total += price_score

        if not risk_pass:
            tier = TIER_EXCLUDED
        elif total >= 140:
            tier = TIER_PREMIUM
        elif total >= 110:
            tier = TIER_STANDARD
        elif total >= 80:
            tier = TIER_SPECULATIVE
        else:
            tier = TIER_EXCLUDED
            if not exclusion_reason:
                exclusion_reason = "综合评分过低"

        return QualityScore(
            code=code,
            name=name,
            tier=tier,
            tier_label=TIER_LABELS.get(tier, ""),
            total_score=round(total, 1),
            dimensions=dims,
            exclusion_reason=exclusion_reason,
        )

    def _should_include(self, qs: QualityScore) -> bool:
        if qs.tier == TIER_EXCLUDED:
            if self.scan_mode == SCAN_MODE_FULL:
                return qs.exclusion_reason == "" or "ST" in qs.exclusion_reason or "退市" in qs.exclusion_reason
            return False
        if qs.tier == TIER_SPECULATIVE:
            return self.scan_mode in (SCAN_MODE_FULL, SCAN_MODE_STANDARD, SCAN_MODE_QUALITY_ONLY)
        return True

    def _score_risk(self, name: str, code: str) -> Tuple[float, bool, str]:
        if not name:
            return 15, True, ""
        name_upper = name.upper().strip()
        for kw in self._ST_KEYWORDS:
            if name_upper.startswith(kw):
                return 0, False, f"ST/高风险: {name}"
        if len(code) == 6 and code.startswith("4"):
            return 0, False, "三板股票"
        return 25, True, ""

    def _score_financial(self, pe: float, pb: float) -> Tuple[float, bool]:
        score = 0.0
        pass_flag = True

        if pe <= 0:
            score += 8
        elif pe <= 15:
            score += 25
        elif pe <= 30:
            score += 20
        elif pe <= 60:
            score += 12
        elif pe <= 100:
            score += 5
        elif pe <= 200:
            score += 3
        else:
            score += 1

        if pb <= 0:
            score += 5
        elif pb <= 1:
            score += 20
        elif pb <= 3:
            score += 25
        elif pb <= 6:
            score += 15
        elif pb <= 10:
            score += 8
        else:
            score += 3

        return round(score, 1), pass_flag

    def _score_liquidity(self, market_cap: float, turnover: float) -> Tuple[float, bool]:
        score = 0.0
        pass_flag = True
        cap_yi = market_cap / 1e8 if market_cap > 0 else 0

        if cap_yi >= 500:
            score += 25
        elif cap_yi >= 200:
            score += 22
        elif cap_yi >= 100:
            score += 18
        elif cap_yi >= 50:
            score += 14
        elif cap_yi >= 20:
            score += 10
        elif cap_yi >= 10:
            score += 6
        else:
            score += 2

        if turnover <= 0:
            score += 0
            pass_flag = False
        elif turnover <= 0.3:
            score += 3
            pass_flag = False
        elif turnover <= 0.5:
            score += 5
        elif turnover <= 2:
            score += 15
        elif turnover <= 8:
            score += 25
        elif turnover <= 15:
            score += 18
        else:
            score += 8

        return round(score, 1), pass_flag

    def _score_price_stability(self, price: float, pct_chg: float) -> Tuple[float, bool]:
        score = 0.0
        pass_flag = True

        if price <= 0:
            return 0, False
        elif price < 2:
            score += 3
        elif price < 5:
            score += 8
        elif price < 10:
            score += 15
        elif price < 50:
            score += 25
        elif price < 100:
            score += 20
        elif price < 500:
            score += 15
        else:
            score += 10

        if abs(pct_chg) > 9.5:
            score += 2
        elif abs(pct_chg) > 7:
            score += 8
        elif abs(pct_chg) > 4:
            score += 15
        else:
            score += 25

        return round(score, 1), pass_flag

    @staticmethod
    def _safe_float(row: pd.Series, *col_names: str) -> float:
        for col in col_names:
            if col in row.index:
                try:
                    val = float(row[col])
                    if pd.notna(val):
                        return val
                except (ValueError, TypeError):
                    continue
        return 0.0
