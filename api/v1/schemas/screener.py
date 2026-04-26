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
        description="扫描模式: premium/quality_only/standard/full/pool",
    )
    use_optimized_weights: Optional[bool] = Field(
        True, description="是否使用优化后的策略权重",
    )
    pool_boards: Optional[List[str]] = Field(None, description="股票池板块筛选（如：科创板,创业板）")
    pool_industries: Optional[List[str]] = Field(None, description="股票池行业筛选（如：半导体,新能源）")
    pool_qualities: Optional[List[str]] = Field(None, description="股票池质量筛选（如：premium,standard）")
    pool_tags: Optional[List[str]] = Field(None, description="股票池标签筛选（如：高分基线,活跃换手）")
    pool_min_base_score: Optional[float] = Field(None, description="股票池最低基础评分")


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


class PoolInitRequest(BaseModel):
    expire_days: int = Field(45, ge=7, le=90, description="股票池有效期（天）")


class PoolStatusResponse(BaseModel):
    has_pool: bool = False
    status: str = "none"
    pool_version: Optional[str] = None
    expires_at: Optional[str] = None
    days_remaining: Optional[int] = None
    total_stocks: int = 0
    filtered_stocks: int = 0
    tagged_stocks: int = 0
    excluded_stocks: int = 0
    progress_pct: float = 0.0
    eta_seconds: float = 0.0
    error_message: Optional[str] = None


class PoolSummaryResponse(BaseModel):
    boards: Dict[str, int] = Field(default_factory=dict)
    industries: Dict[str, int] = Field(default_factory=dict)
    qualities: Dict[str, int] = Field(default_factory=dict)
    total_active: int = 0


class PoolEntryItem(BaseModel):
    code: str
    name: str = ""
    board: str = ""
    industry: str = ""
    quality_tier: str = ""
    base_score: float = 0.0
    tags: List[str] = Field(default_factory=list)
    market_cap: float = 0.0
    pe_ratio: float = 0.0
    pb_ratio: float = 0.0
    price: float = 0.0
    turnover_rate: float = 0.0


class PoolCodesResponse(BaseModel):
    total: int = 0
    entries: List[PoolEntryItem] = Field(default_factory=list)


class PoolInitResponse(BaseModel):
    pool_version: str
    message: str = "初始化已启动"


class PoolCancelResponse(BaseModel):
    cancelled: bool = False
    message: str = ""
