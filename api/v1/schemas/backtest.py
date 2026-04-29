# -*- coding: utf-8 -*-
"""Backtest API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BacktestRunRequest(BaseModel):
    code: Optional[str] = Field(None, description="仅回测指定股票")
    codes: Optional[List[str]] = Field(None, description="回测多只股票，优先于 code")
    force: bool = Field(False, description="强制重新计算")
    eval_window_days: Optional[int] = Field(None, ge=1, le=120, description="评估窗口（交易日数）")
    min_age_days: Optional[int] = Field(None, ge=0, le=365, description="分析记录最小天龄（0=不限）")
    limit: int = Field(200, ge=1, le=2000, description="最多处理的分析记录数")
    auto_analyze: bool = Field(False, description="无分析记录时自动触发分析（观察池回测一键反馈）")


class BacktestRunResponse(BaseModel):
    processed: int = Field(..., description="候选记录数")
    saved: int = Field(..., description="写入回测结果数")
    completed: int = Field(..., description="完成回测数")
    insufficient: int = Field(..., description="数据不足数")
    errors: int = Field(..., description="错误数")
    analyzed: int = Field(0, description="自动分析触发的股票数")


class BacktestResultItem(BaseModel):
    analysis_history_id: int
    code: str
    stock_name: Optional[str] = None
    analysis_date: Optional[str] = None
    eval_window_days: int
    engine_version: str
    eval_status: str
    evaluated_at: Optional[str] = None
    operation_advice: Optional[str] = None
    trend_prediction: Optional[str] = None
    position_recommendation: Optional[str] = None
    start_price: Optional[float] = None
    end_close: Optional[float] = None
    max_high: Optional[float] = None
    min_low: Optional[float] = None
    stock_return_pct: Optional[float] = None
    actual_return_pct: Optional[float] = None
    actual_movement: Optional[str] = None
    direction_expected: Optional[str] = None
    direction_correct: Optional[bool] = None
    outcome: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    hit_stop_loss: Optional[bool] = None
    hit_take_profit: Optional[bool] = None
    first_hit: Optional[str] = None
    first_hit_date: Optional[str] = None
    first_hit_trading_days: Optional[int] = None
    simulated_entry_price: Optional[float] = None
    simulated_exit_price: Optional[float] = None
    simulated_exit_reason: Optional[str] = None
    simulated_return_pct: Optional[float] = None


class BacktestResultsResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[BacktestResultItem] = Field(default_factory=list)


class PerformanceMetrics(BaseModel):
    scope: str
    code: Optional[str] = None
    eval_window_days: int
    engine_version: str
    computed_at: Optional[str] = None

    total_evaluations: int
    completed_count: int
    insufficient_count: int
    long_count: int
    cash_count: int
    win_count: int
    loss_count: int
    neutral_count: int

    direction_accuracy_pct: Optional[float] = None
    win_rate_pct: Optional[float] = None
    neutral_rate_pct: Optional[float] = None
    avg_stock_return_pct: Optional[float] = None
    avg_simulated_return_pct: Optional[float] = None

    stop_loss_trigger_rate: Optional[float] = None
    take_profit_trigger_rate: Optional[float] = None
    ambiguous_rate: Optional[float] = None
    avg_days_to_first_hit: Optional[float] = None

    sharpe_ratio: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    profit_factor: Optional[float] = None
    avg_win_pct: Optional[float] = None
    avg_loss_pct: Optional[float] = None

    advice_breakdown: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class EquityCurvePoint(BaseModel):
    date: str
    cumulative_return_pct: float
    drawdown_pct: float


class EquityCurveResponse(BaseModel):
    code: Optional[str] = None
    eval_window_days: int
    engine_version: str
    total_trades: int
    points: List[EquityCurvePoint] = Field(default_factory=list)


# ===== v2 策略回测 Schema (FR-001~FR-021) =====

class ExitRuleConfig(BaseModel):
    trailing_stop_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    max_hold_days: Optional[int] = None
    partial_exit_enabled: bool = False
    partial_exit_pct: float = 0.5
    signal_threshold: Optional[float] = None
    fixed_days: Optional[int] = None


class StrategyBacktestRequest(BaseModel):
    strategy: str = Field(..., description="策略名 (如 ma_golden_cross)")
    codes: List[str] = Field(default_factory=list, description="股票代码列表")
    cash: float = Field(100000, ge=10000, description="初始资金")
    commission: float = Field(0.0003, ge=0, description="佣金率")
    slippage: float = Field(0.001, ge=0, description="滑点率")
    stamp_duty: float = Field(0.001, ge=0, description="印花税率")
    start_date: Optional[str] = Field(None, description="开始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="结束日期 YYYY-MM-DD")
    factors: Optional[Dict[str, float]] = Field(None, description="因子覆盖")
    preset: Optional[str] = Field(None, description="参数预设名")
    exit_rules: Optional[ExitRuleConfig] = Field(None, description="平仓规则")


class OptimizeRequest(BaseModel):
    strategy: str = Field(..., description="策略名")
    codes: List[str] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    maximize: Optional[str] = Field("Sharpe Ratio", description="优化目标指标")
    method: Optional[str] = Field("grid", description="grid 或 bayesian")
    factor_ranges: Optional[Dict[str, List[float]]] = Field(None)
    constraint: Optional[str] = None
    max_tries: Optional[int] = None
