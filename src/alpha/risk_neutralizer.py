# -*- coding: utf-8 -*-
"""Risk neutralizer — eliminate systematic biases from raw alpha scores.

Implements cross-sectional regression-based risk neutralization (standard Barra approach):
1. Regress raw alpha against industry dummies + log(market_cap)
2. Residuals are the neutralized alpha
3. Re-standardize residuals to mean~0, std~1

This removes the systematic drift where certain industries or large/small caps
consistently score higher/lower regardless of true alpha signal.

Data sources:
- industry: from stock_pool._classify_industry(name) — 12 industry keywords
- market_cap: from StockPoolEntry.market_cap
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

import numpy as np

from src.alpha.alpha_scorer import AlphaPrediction

logger = logging.getLogger(__name__)


class RiskNeutralizer:
    """
    Cross-sectional risk neutralization for alpha predictions.

    Usage:
        neutralizer = RiskNeutralizer(industry_map={"000001": "金融", ...}, mcaps={"000001": 1.2e10, ...})
        neutralized = neutralizer.neutralize(alphas)
    """

    MIN_STOCKS_FOR_NEUTRALIZATION = 30

    MIN_INDUSTRY_COUNT = 2

    MIN_MCAP_FOR_LOG = 1e6

    def __init__(
        self,
        industry_map: Optional[Dict[str, str]] = None,
        market_caps: Optional[Dict[str, float]] = None,
    ):
        self.industry_map = industry_map or {}
        self.market_caps = market_caps or {}

    def neutralize(self, alphas: List[AlphaPrediction]) -> List[AlphaPrediction]:
        if len(alphas) < self.MIN_STOCKS_FOR_NEUTRALIZATION:
            logger.warning(
                "Insufficient stocks for neutralization: %d < %d, returning raw alphas",
                len(alphas), self.MIN_STOCKS_FOR_NEUTRALIZATION,
            )
            return alphas

        raw_scores = np.array([a.raw_score for a in alphas], dtype=float)
        codes = [a.code for a in alphas]

        industries = []
        mcaps = []
        for a in alphas:
            ind = self.industry_map.get(a.code, "其他")
            industries.append(ind)
            mcap = self.market_caps.get(a.code, 0.0)
            mcaps.append(max(mcap, self.MIN_MCAP_FOR_LOG))

        unique_industries = sorted(set(industries))

        if len(unique_industries) < self.MIN_INDUSTRY_COUNT:
            logger.warning("Only %d industries found, skipping industry neutralization", len(unique_industries))
            return alphas

        n = len(alphas)
        k = len(unique_industries)
        X = np.zeros((n, k), dtype=float)

        log_mcap = np.log(np.array(mcaps, dtype=float))
        log_mcap_mean = np.mean(log_mcap)
        log_mcap_std = np.std(log_mcap) or 1.0
        log_mcap_norm = (log_mcap - log_mcap_mean) / log_mcap_std

        ind_to_col = {ind: i for i, ind in enumerate(unique_industries)}
        for i, (_, ind) in enumerate(zip(codes, industries)):
            X[i, ind_to_col.get(ind, 0)] = 1.0

        X_augmented = np.column_stack([X, log_mcap_norm])

        try:
            beta = np.linalg.lstsq(X_augmented, raw_scores, rcond=None)[0]
        except np.linalg.LinAlgError:
            logger.warning("Linear regression failed during neutralization, returning raw alphas")
            return alphas

        predicted = X_augmented @ beta
        residuals = raw_scores - predicted

        res_mean = np.mean(residuals)
        res_std = np.std(residuals) or 1.0
        neutralized_scores = (residuals - res_mean) / res_std

        industry_bias = {}
        for idx, ind in enumerate(unique_industries):
            industry_bias[ind] = float(beta[idx])

        mcap_coef = float(beta[-1])
        explained_variance = 1.0 - np.var(residuals) / np.var(raw_scores) if np.var(raw_scores) > 0 else 0.0

        logger.info(
            "Risk neutralization: %d stocks, %d industries, "
            "R²_explained=%.4f, mcap_coef=%.6f, %s-biased industry count=%d",
            n, len(unique_industries), explained_variance, mcap_coef,
            "top" if mcap_coef > 0 else "bottom",
            sum(1 for b in industry_bias.values() if abs(b) > 1.0),
        )

        result = []
        for i, a in enumerate(alphas):
            new_alpha = float(neutralized_scores[i])
            result.append(AlphaPrediction(
                code=a.code,
                name=a.name,
                alpha_score=new_alpha,
                raw_score=float(residuals[i]),
                factor_scores=dict(a.factor_scores),
            ))

        result.sort(key=lambda x: x.alpha_score, reverse=True)
        return result

    def get_industry_exposures(self, alphas: List[AlphaPrediction]) -> Dict[str, Dict[str, float]]:
        if not self.industry_map:
            return {}

        industries: Dict[str, List[float]] = {}
        for a in alphas:
            ind = self.industry_map.get(a.code, "其他")
            if ind not in industries:
                industries[ind] = []
            industries[ind].append(a.alpha_score)

        return {
            ind: {
                "count": len(scores),
                "mean_alpha": float(np.mean(scores)),
                "std_alpha": float(np.std(scores)) if len(scores) > 1 else 0.0,
            }
            for ind, scores in sorted(industries.items())
            if len(scores) >= 3
        }

    @classmethod
    def from_stock_pool(cls) -> "RiskNeutralizer":
        try:
            from src.core.stock_pool import StockPoolInitializer
            pool = StockPoolInitializer.get_instance()
            entries = pool.get_pool_codes(limit=5000)
        except Exception as e:
            logger.warning("Failed to load stock pool: %s, using empty maps", e)
            return cls()

        industry_map: Dict[str, str] = {}
        market_caps: Dict[str, float] = {}

        for e in entries:
            code = e.get("code", "")
            if not code:
                continue
            name = e.get("name", "")
            industry_map[code] = pool._classify_industry(name)
            market_caps[code] = float(e.get("market_cap", 0) or 0)

        logger.info("Loaded %d stocks for risk neutralization (industry=%d unique)",
                     len(industry_map), len(set(industry_map.values())))

        return cls(industry_map=industry_map, market_caps=market_caps)
