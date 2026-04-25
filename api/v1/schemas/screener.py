# -*- coding: utf-8 -*-
"""Screener API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScreenerRunRequest(BaseModel):
    top_n: int = Field(10, ge=1, le=50, description="选出股票数量")
    strategy_tag: Optional[str] = Field(None, description="策略标签")
    min_market_cap: Optional[float] = Field(None, description="最小总市值（元）")
    max_market_cap: Optional[float] = Field(None, description="最大总市值（元）")
    min_price: Optional[float] = Field(None, description="最低股价")
    max_price: Optional[float] = Field(None, description="最高股价")
    min_turnover_rate: Optional[float] = Field(None, description="最小换手率（%）")
    max_turnover_rate: Optional[float] = Field(None, description="最大换手率（%）")
    scan_mode: Optional[str] = Field(
        "quality_only",
        description="扫描模式: premium/quality_only/standard/full",
    )
    use_optimized_weights: Optional[bool] = Field(
        True, description="是否使用优化后的策略权重",
    )


class DataFetchFailureItem(BaseModel):
    code: str
    name: str = ""
    reason: str = ""
    fallback: str = ""


class ScreenerCandidateItem(BaseModel):
    rank: int
    code: str
    name: str
    score: float
    price: float
    market_cap_yi: float = Field(..., description="总市值（亿元）")
    turnover_rate: float
    pe_ratio: float
    signals: Optional[Dict[str, Any]] = None
    strategy_scores: Optional[Dict[str, Any]] = None
    market_regime: Optional[str] = None
    market_regime_label: Optional[str] = None
    quality_tier: Optional[str] = None
    quality_tier_label: Optional[str] = None
    data_fetch_failed: Optional[bool] = None
    data_fetch_reason: Optional[str] = None


class ScreenerRunResponse(BaseModel):
    screened: int = Field(..., description="筛选出的候选数")
    saved: int = Field(..., description="持久化的记录数")
    screen_date: str = Field(..., description="选股日期")
    candidates: List[ScreenerCandidateItem] = Field(default_factory=list)
    data_failures: List[DataFetchFailureItem] = Field(default_factory=list)
    quality_summary: Optional[Dict[str, int]] = None
    market_regime: Optional[str] = None
    market_regime_label: Optional[str] = None
    optimized_weights_applied: Optional[bool] = None


class ScreenerPickItem(BaseModel):
    id: int
    screen_date: str
    code: str
    name: Optional[str] = None
    score: float
    rank: int
    strategy_tag: Optional[str] = None
    price_at_screen: Optional[float] = None
    market_cap: Optional[float] = None
    turnover_rate: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    signals: Optional[Dict[str, Any]] = None
    strategy_scores: Optional[Dict[str, Any]] = None
    market_regime: Optional[str] = None
    market_regime_label: Optional[str] = None
    quality_tier: Optional[str] = None
    quality_tier_label: Optional[str] = None
    data_fetch_failed: Optional[bool] = None
    data_fetch_reason: Optional[str] = None
    status: str = "watch"
    days_held: int = 0
    return_pct: Optional[float] = None
    max_return_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    exit_price: Optional[float] = None
    exit_date: Optional[str] = None
    exit_reason: Optional[str] = None
    backtest_verified: bool = False
    backtest_outcome: Optional[str] = None


class ScreenerPicksResponse(BaseModel):
    date: str
    total: int
    picks: List[ScreenerPickItem] = Field(default_factory=list)


class ScreenerWatchListResponse(BaseModel):
    total: int
    watch_list: List[ScreenerPickItem] = Field(default_factory=list)


class ScreenerPerformanceResponse(BaseModel):
    total: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    max_return: float = 0.0
    min_return: float = 0.0


class ScreenerTrackingUpdateResponse(BaseModel):
    updated: int = 0
    closed: int = 0


class ScreenerBacktestFeedbackResponse(BaseModel):
    verified: int = 0
    total_checked: int = 0
