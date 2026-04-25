# -*- coding: utf-8 -*-
"""Stock screener engine — scan full A-share market and rank candidates.

Workflow:
1. Fetch full-market realtime quotes via akshare/efinance
2. Apply multi-factor filters (market cap, PE, turnover, ST exclusion, etc.)
3. Compute technical signals from recent daily bars
4. Score and rank stocks
5. Return top-N candidates
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ScreenerConfig:
    top_n: int = 10
    min_market_cap: float = 30e8
    max_market_cap: float = 5000e8
    min_turnover_rate: float = 1.0
    max_turnover_rate: float = 25.0
    min_pe: float = 0.0
    max_pe: float = 200.0
    min_pb: float = 0.0
    max_pb: float = 20.0
    exclude_st: bool = True
    exclude_new_stock_days: int = 60
    min_price: float = 3.0
    max_price: float = 100.0
    strategy_tag: str = "daily_pick"
    scan_mode: str = "quality_only"
    use_optimized_weights: bool = True


@dataclass
class DataFetchFailure:
    code: str
    name: str = ""
    reason: str = ""
    fallback: str = ""


@dataclass
class ScreenerCandidate:
    code: str
    name: str
    score: float = 0.0
    rank: int = 0
    price: float = 0.0
    market_cap: float = 0.0
    turnover_rate: float = 0.0
    pe_ratio: float = 0.0
    pb_ratio: float = 0.0
    signals: Dict[str, Any] = field(default_factory=dict)
    strategy_scores: Dict[str, Any] = field(default_factory=dict)
    market_regime: str = ""
    market_regime_label: str = ""
    quality_tier: str = ""
    quality_tier_label: str = ""
    data_fetch_failed: bool = False
    data_fetch_reason: str = ""


@dataclass
class ScreenerRunResult:
    candidates: List[ScreenerCandidate] = field(default_factory=list)
    data_failures: List[DataFetchFailure] = field(default_factory=list)
    quality_summary: Dict[str, int] = field(default_factory=dict)
    market_regime: str = ""
    market_regime_label: str = ""
    optimized_weights_applied: bool = False


class ScreenerEngine:
    """Full-market A-share screener with multi-factor scoring."""

    _ST_KEYWORDS = ("ST", "*ST", "S*ST", "SST", "S")

    def __init__(self, config: Optional[ScreenerConfig] = None):
        self.config = config or ScreenerConfig()

    def run(self, demo: bool = False) -> ScreenerRunResult:
        """Execute the full screening pipeline."""
        logger.info("[Screener] 开始全市场选股扫描 (模式=%s)...", self.config.scan_mode)

        if demo:
            raw_df = self._generate_demo_data()
            logger.info("[Screener] [DEMO模式] 使用模拟数据，共 %d 只股票", len(raw_df))
        else:
            raw_df = self._fetch_full_market_quotes()
            if raw_df is None or raw_df.empty:
                logger.warning("[Screener] 无法获取全市场行情数据")
                return ScreenerRunResult()

        logger.info("[Screener] 获取到 %d 只股票行情数据", len(raw_df))

        filtered = self._apply_basic_filters(raw_df)
        logger.info("[Screener] 基础过滤后剩余 %d 只", len(filtered))

        if filtered.empty:
            return ScreenerRunResult()

        from src.core.stock_quality_classifier import StockQualityClassifier
        classifier = StockQualityClassifier(scan_mode=self.config.scan_mode)
        quality_df, quality_scores = classifier.classify_dataframe(filtered)
        quality_summary: Dict[str, int] = {}
        for qs in quality_scores:
            quality_summary[qs.tier] = quality_summary.get(qs.tier, 0) + 1

        logger.info(
            "[Screener] 质量分级后剩余 %d 只 (优质=%d, 标准=%d, 边缘=%d, 排除=%d)",
            len(quality_df),
            quality_summary.get("premium", 0),
            quality_summary.get("standard", 0),
            quality_summary.get("marginal", 0),
            quality_summary.get("excluded", 0),
        )

        if quality_df.empty:
            return ScreenerRunResult(quality_summary=quality_summary)

        regime_result = self._detect_market_regime()
        logger.info(
            "[Screener] 市场状态: %s (%s) 置信度=%.2f",
            regime_result.regime, regime_result.label, regime_result.confidence,
        )

        optimized_weights: Optional[Dict[str, float]] = None
        optimized_applied = False
        if self.config.use_optimized_weights:
            optimized_weights = self._load_optimized_weights()
            if optimized_weights:
                optimized_applied = True
                logger.info("[Screener] 使用优化后的策略权重 (%d 个策略)", len(optimized_weights))

        candidates, failures = self._score_and_rank(
            quality_df,
            quality_scores=quality_scores,
            regime_result=regime_result,
            optimized_weights=optimized_weights,
        )
        top = candidates[: self.config.top_n]

        logger.info("[Screener] 选出 Top %d 只股票", len(top))
        for c in top:
            logger.info("  #%d %s(%s) 评分=%.2f [%s]", c.rank, c.name, c.code, c.score, c.quality_tier_label)

        if failures:
            logger.warning("[Screener] %d 只股票历史数据获取失败", len(failures))

        return ScreenerRunResult(
            candidates=top,
            data_failures=failures,
            quality_summary=quality_summary,
            market_regime=regime_result.regime,
            market_regime_label=regime_result.label,
            optimized_weights_applied=optimized_applied,
        )

    def _fetch_full_market_quotes(self) -> Optional[pd.DataFrame]:
        """Fetch full-market A-share realtime quotes via akshare."""
        try:
            import akshare as ak
            logger.info("[Screener] 调用 ak.stock_zh_a_spot_em() 获取全市场行情...")
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                logger.info("[Screener] 获取成功: %d 只股票", len(df))
                return df
        except Exception as e:
            logger.warning("[Screener] akshare 获取失败: %s, 尝试 efinance...", e)

        try:
            import efinance as ef
            logger.info("[Screener] 调用 ef.stock.get_realtime_quotes() 获取全市场行情...")
            df = ef.stock.get_realtime_quotes()
            if df is not None and not df.empty:
                logger.info("[Screener] efinance 获取成功: %d 只股票", len(df))
                return df
        except Exception as e:
            logger.error("[Screener] efinance 也获取失败: %s", e)

        return None

    def _apply_basic_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply basic quantitative filters to the market DataFrame."""
        cfg = self.config
        result = df.copy()

        code_col = self._detect_column(result, ['代码', '股票代码', 'code'])
        name_col = self._detect_column(result, ['名称', '股票名称', 'name'])
        price_col = self._detect_column(result, ['最新价', '收盘价', 'price', 'close'])
        market_cap_col = self._detect_column(result, ['总市值', 'market_cap'])
        turnover_col = self._detect_column(result, ['换手率', 'turnover_rate'])
        pe_col = self._detect_column(result, ['市盈率-动态', 'pe_ratio', '市盈率'])
        pb_col = self._detect_column(result, ['市净率', 'pb_ratio'])
        pct_chg_col = self._detect_column(result, ['涨跌幅', 'change_pct'])

        if code_col is None:
            logger.warning("[Screener] 无法识别股票代码列")
            return pd.DataFrame()

        result['_code'] = result[code_col].astype(str).str.strip()
        result['_name'] = result[name_col].astype(str).str.strip() if name_col else ''

        if cfg.exclude_st and name_col:
            mask = ~result['_name'].apply(self._is_st_stock)
            result = result[mask]
            logger.debug("[Screener] 排除ST后剩余 %d", len(result))

        result = result[result['_code'].str.match(r'^[03689]\d{5}$')]
        logger.debug("[Screener] 仅保留沪深京A股后剩余 %d", len(result))

        if price_col:
            result['_price'] = pd.to_numeric(result[price_col], errors='coerce')
            result = result[
                (result['_price'] >= cfg.min_price) & (result['_price'] <= cfg.max_price)
            ]

        if market_cap_col:
            result['_market_cap'] = pd.to_numeric(result[market_cap_col], errors='coerce')
            result = result[
                (result['_market_cap'] >= cfg.min_market_cap) &
                (result['_market_cap'] <= cfg.max_market_cap)
            ]

        if turnover_col:
            result['_turnover_rate'] = pd.to_numeric(result[turnover_col], errors='coerce')
            result = result[
                (result['_turnover_rate'] >= cfg.min_turnover_rate) &
                (result['_turnover_rate'] <= cfg.max_turnover_rate)
            ]

        if pe_col:
            result['_pe_ratio'] = pd.to_numeric(result[pe_col], errors='coerce')
            result = result[
                (result['_pe_ratio'] >= cfg.min_pe) & (result['_pe_ratio'] <= cfg.max_pe)
            ]

        if pb_col:
            result['_pb_ratio'] = pd.to_numeric(result[pb_col], errors='coerce')
            result = result[
                (result['_pb_ratio'] >= cfg.min_pb) & (result['_pb_ratio'] <= cfg.max_pb)
            ]

        if pct_chg_col:
            result['_pct_chg'] = pd.to_numeric(result[pct_chg_col], errors='coerce')
            result = result[result['_pct_chg'].between(-10.5, 10.5)]

        result = result.dropna(subset=['_price'] if '_price' in result.columns else ['_code'])

        return result

    def _score_and_rank(
        self,
        df: pd.DataFrame,
        quality_scores: Optional[List[Any]] = None,
        regime_result: Optional[Any] = None,
        optimized_weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[List[ScreenerCandidate], List[DataFetchFailure]]:
        """Compute multi-factor score and rank candidates.

        The scoring combines:
        1. Base factor score (turnover, momentum, valuation, market cap)
        2. Strategy fusion score (all strategy signals with dynamic weights)
        """
        from src.core.strategy_signal_extractor import StrategySignalExtractor
        from src.core.market_regime import DynamicWeightAdjuster

        regime = regime_result.regime if regime_result else "sideways"
        regime_label = regime_result.label if regime_result else ""
        adjuster = DynamicWeightAdjuster()
        if optimized_weights:
            adjuster.base_weights = optimized_weights

        quality_map: Dict[str, Any] = {}
        if quality_scores:
            for qs in quality_scores:
                quality_map[qs.code] = qs

        candidates = []
        data_failures: List[DataFetchFailure] = []

        total = len(df)
        processed = 0

        for _, row in df.iterrows():
            code = str(row.get('_code', ''))
            name = str(row.get('_name', ''))
            price = float(row.get('_price', 0) or 0)
            market_cap = float(row.get('_market_cap', 0) or 0)
            turnover_rate = float(row.get('_turnover_rate', 0) or 0)
            pe_ratio = float(row.get('_pe_ratio', 0) or 0)
            pb_ratio = float(row.get('_pb_ratio', 0) or 0)
            pct_chg = float(row.get('_pct_chg', 0) or 0)

            base_score = 0.0
            signals: Dict[str, Any] = {}

            base_score += self._score_turnover(turnover_rate, signals)
            base_score += self._score_momentum(pct_chg, signals)
            base_score += self._score_valuation(pe_ratio, pb_ratio, signals)
            base_score += self._score_market_cap(market_cap, signals)

            strategy_scores: Dict[str, Any] = {}
            hist_df = self._fetch_stock_history(code)
            realtime_info = {
                "turnover_rate": turnover_rate,
                "pct_chg": pct_chg,
                "price": price,
                "market_cap": market_cap,
            }

            qs = quality_map.get(code)
            quality_tier = qs.tier if qs else ""
            quality_tier_label = qs.tier_label if qs else ""

            if hist_df is not None and len(hist_df) >= 20:
                extractor = StrategySignalExtractor(market_regime=regime)
                strat_signals = extractor.extract_all(hist_df, realtime=realtime_info)
                effective_weights = adjuster.adjust(regime, strat_signals)
                fusion_score, strategy_avg, category_breakdown = adjuster.compute_fusion_score(
                    strat_signals, effective_weights, base_factor_score=base_score,
                )

                strategy_scores = {
                    "fusion_score": round(fusion_score, 2),
                    "strategy_avg": round(strategy_avg, 2),
                    "base_factor_score": round(base_score, 2),
                    "regime": regime,
                    "regime_label": regime_label,
                    "category_breakdown": category_breakdown,
                    "triggered_strategies": [
                        {
                            "name": s.strategy_name,
                            "display_name": s.display_name,
                            "score": round(s.score, 1),
                            "weight": round(effective_weights.get(s.strategy_name, 0), 3),
                            "category": s.category,
                            "details": s.details,
                        }
                        for s in strat_signals
                        if s.triggered and s.score > 0
                    ],
                }
                final_score = fusion_score
            else:
                final_score = base_score
                fail_reason = "历史数据不足" if hist_df is None else f"数据条数不足({len(hist_df) if hist_df is not None else 0}<20)"
                strategy_scores = {
                    "fusion_score": round(base_score, 2),
                    "strategy_avg": 0,
                    "base_factor_score": round(base_score, 2),
                    "regime": regime,
                    "regime_label": regime_label,
                    "note": f"历史数据获取失败: {fail_reason}，仅使用基础因子评分",
                }
                data_failures.append(DataFetchFailure(
                    code=code,
                    name=name,
                    reason=fail_reason,
                    fallback="base_factor_only",
                ))

            candidates.append(ScreenerCandidate(
                code=code,
                name=name,
                score=round(final_score, 2),
                price=price,
                market_cap=market_cap,
                turnover_rate=turnover_rate,
                pe_ratio=pe_ratio,
                pb_ratio=pb_ratio,
                signals=signals,
                strategy_scores=strategy_scores,
                market_regime=regime,
                market_regime_label=regime_label,
                quality_tier=quality_tier,
                quality_tier_label=quality_tier_label,
                data_fetch_failed=hist_df is None or len(hist_df) < 20,
                data_fetch_reason="" if hist_df is not None and len(hist_df) >= 20 else fail_reason,
            ))

            processed += 1
            if processed % 200 == 0:
                logger.debug("[Screener] 已评分 %d/%d 只股票", processed, total)

        candidates.sort(key=lambda c: c.score, reverse=True)
        for i, c in enumerate(candidates, 1):
            c.rank = i

        return candidates, data_failures

    def _detect_market_regime(self) -> Any:
        from src.core.market_regime import MarketRegimeDetector
        detector = MarketRegimeDetector()
        return detector.detect()

    def _load_optimized_weights(self) -> Optional[Dict[str, float]]:
        try:
            from src.core.strategy_optimizer import StrategyOptimizer
            optimizer = StrategyOptimizer()
            weights = optimizer.get_effective_weights()
            if weights and len(weights) > 5:
                return weights
        except Exception as e:
            logger.debug("[Screener] 加载优化权重失败: %s", e)
        return None

    def _fetch_stock_history(self, code: str) -> Optional[pd.DataFrame]:
        try:
            from data_provider.factory import DataProviderFactory
            factory = DataProviderFactory()
            end = date.today()
            start = end - timedelta(days=120)
            df = factory.get_daily_history(code, start_date=start, end_date=end)
            if df is not None and not df.empty:
                if 'date' in df.columns:
                    df = df.sort_values('date').reset_index(drop=True)
                return df
        except Exception as e:
            logger.debug("[Screener] 获取 %s 历史数据失败: %s", code, e)
        return None

    def _score_turnover(self, turnover: float, signals: Dict) -> float:
        """Score based on turnover rate — moderate turnover preferred."""
        if turnover <= 0:
            return 0.0
        if 2.0 <= turnover <= 8.0:
            signals['turnover_signal'] = 'moderate_active'
            return 25.0
        if 1.0 <= turnover < 2.0:
            signals['turnover_signal'] = 'low_active'
            return 15.0
        if 8.0 < turnover <= 15.0:
            signals['turnover_signal'] = 'high_active'
            return 20.0
        signals['turnover_signal'] = 'extreme'
        return 5.0

    def _score_momentum(self, pct_chg: float, signals: Dict) -> float:
        """Score based on daily price change — slight positive momentum preferred."""
        if -2.0 <= pct_chg <= 3.0:
            signals['momentum_signal'] = 'gentle_up'
            return 25.0
        if 3.0 < pct_chg <= 7.0:
            signals['momentum_signal'] = 'strong_up'
            return 20.0
        if -5.0 <= pct_chg < -2.0:
            signals['momentum_signal'] = 'pullback'
            return 15.0
        if pct_chg > 7.0:
            signals['momentum_signal'] = 'chase_risk'
            return 5.0
        signals['momentum_signal'] = 'weak'
        return 5.0

    def _score_valuation(self, pe: float, pb: float, signals: Dict) -> float:
        """Score based on valuation — reasonable PE/PB preferred."""
        score = 0.0
        if 10.0 <= pe <= 40.0:
            score += 15.0
            signals['pe_signal'] = 'reasonable'
        elif 0 < pe < 10.0:
            score += 10.0
            signals['pe_signal'] = 'low_pe'
        elif 40.0 < pe <= 80.0:
            score += 8.0
            signals['pe_signal'] = 'high_pe'
        else:
            signals['pe_signal'] = 'extreme_pe'

        if 1.0 <= pb <= 5.0:
            score += 10.0
            signals['pb_signal'] = 'reasonable'
        elif 0 < pb < 1.0:
            score += 8.0
            signals['pb_signal'] = 'below_book'
        else:
            signals['pb_signal'] = 'high_pb'

        return score

    def _score_market_cap(self, market_cap: float, signals: Dict) -> float:
        """Score based on market cap — mid-cap preferred for growth."""
        if market_cap <= 0:
            return 0.0
        cap_yi = market_cap / 1e8
        if 50 <= cap_yi <= 500:
            signals['cap_signal'] = 'mid_cap'
            return 25.0
        if 500 < cap_yi <= 2000:
            signals['cap_signal'] = 'large_cap'
            return 20.0
        if 30 <= cap_yi < 50:
            signals['cap_signal'] = 'small_cap'
            return 15.0
        signals['cap_signal'] = 'mega_or_micro'
        return 10.0

    @classmethod
    def _is_st_stock(cls, name: str) -> bool:
        """Check if a stock name indicates ST status."""
        if not name:
            return False
        name_upper = name.upper().strip()
        for kw in cls._ST_KEYWORDS:
            if name_upper.startswith(kw):
                return True
        return False

    @staticmethod
    def _detect_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        """Detect which column name exists in the DataFrame."""
        for c in candidates:
            if c in df.columns:
                return c
        return None

    def _generate_demo_data(self) -> pd.DataFrame:
        """Generate realistic demo data for testing when market is closed."""
        import random

        random.seed(42)

        demo_stocks = [
            ("600519", "贵州茅台"), ("000858", "五粮液"), ("601318", "中国平安"),
            ("600036", "招商银行"), ("000333", "美的集团"), ("002415", "海康威视"),
            ("600276", "恒瑞医药"), ("000651", "格力电器"), ("601888", "中国中免"),
            ("002352", "顺丰控股"), ("600809", "山西汾酒"), ("000568", "泸州老窖"),
            ("601012", "隆基绿能"), ("002475", "立讯精密"), ("600690", "海尔智家"),
            ("000725", "京东方A"), ("002714", "牧原股份"), ("601166", "兴业银行"),
            ("600030", "中信证券"), ("000002", "万科A"), ("002230", "科大讯飞"),
            ("600585", "海螺水泥"), ("603259", "药明康德"), ("002460", "赣锋锂业"),
            ("600900", "长江电力"), ("601899", "紫金矿业"), ("000063", "中兴通讯"),
            ("002049", "紫光国微"), ("600436", "片仔癀"), ("300750", "宁德时代"),
            ("002594", "比亚迪"), ("600031", "三一重工"), ("000596", "古井贡酒"),
            ("601669", "中国电建"), ("002129", "中环股份"), ("600309", "万华化学"),
            ("000625", "长安汽车"), ("002371", "北方华创"), ("600570", "恒生电子"),
            ("300059", "东方财富"), ("601225", "陕西煤业"), ("000776", "广发证券"),
            ("600346", "恒力石化"), ("002032", "苏泊尔"), ("601088", "中国神华"),
            ("600887", "伊利股份"), ("002142", "宁波银行"), ("600196", "复星医药"),
            ("000538", "云南白药"), ("601633", "长城汽车"),
        ]

        rows = []
        for code, name in demo_stocks:
            price = round(random.uniform(8, 95), 2)
            pct_chg = round(random.uniform(-8, 7), 2)
            turnover_rate = round(random.uniform(0.5, 20), 2)
            market_cap = round(price * random.uniform(5e8, 80e8))
            pe_ratio = round(random.uniform(5, 120), 2)
            pb_ratio = round(random.uniform(0.5, 12), 2)

            rows.append({
                "代码": code,
                "名称": name,
                "最新价": price,
                "涨跌幅": pct_chg,
                "换手率": turnover_rate,
                "总市值": market_cap,
                "市盈率-动态": pe_ratio,
                "市净率": pb_ratio,
            })

        return pd.DataFrame(rows)
