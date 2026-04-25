# -*- coding: utf-8 -*-
"""Screener endpoints."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_database_manager
from api.v1.schemas.screener import (
    ScreenerBacktestFeedbackResponse,
    ScreenerPicksResponse,
    ScreenerPerformanceResponse,
    ScreenerRunRequest,
    ScreenerRunResponse,
    ScreenerTrackingUpdateResponse,
    ScreenerWatchListResponse,
)
from api.v1.schemas.common import ErrorResponse
from src.services.screener_service import ScreenerService
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/run",
    response_model=ScreenerRunResponse,
    responses={
        200: {"description": "选股执行完成"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="触发每日选股",
    description="从全市场A股中筛选Top N股票，结果写入 screener_results 表",
)
def run_screener(
    request: ScreenerRunRequest = ScreenerRunRequest(),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> ScreenerRunResponse:
    try:
        service = ScreenerService(db_manager)
        config_overrides = {}
        if request.min_market_cap is not None:
            config_overrides['min_market_cap'] = request.min_market_cap
        if request.max_market_cap is not None:
            config_overrides['max_market_cap'] = request.max_market_cap
        if request.min_price is not None:
            config_overrides['min_price'] = request.min_price
        if request.max_price is not None:
            config_overrides['max_price'] = request.max_price
        if request.min_turnover_rate is not None:
            config_overrides['min_turnover_rate'] = request.min_turnover_rate
        if request.max_turnover_rate is not None:
            config_overrides['max_turnover_rate'] = request.max_turnover_rate
        if request.scan_mode is not None:
            config_overrides['scan_mode'] = request.scan_mode
        if request.use_optimized_weights is not None:
            config_overrides['use_optimized_weights'] = request.use_optimized_weights

        result = service.run_daily_screen(
            top_n=request.top_n,
            strategy_tag=request.strategy_tag,
            config_overrides=config_overrides,
        )
        return ScreenerRunResponse(**result)
    except Exception as exc:
        logger.error(f"选股执行失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"选股执行失败: {str(exc)}"},
        )


@router.get(
    "/today",
    response_model=ScreenerPicksResponse,
    responses={
        200: {"description": "今日选股结果"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取今日选股",
)
def get_today_picks(
    strategy_tag: Optional[str] = Query(None, description="策略标签筛选"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> ScreenerPicksResponse:
    try:
        service = ScreenerService(db_manager)
        result = service.get_today_picks(strategy_tag=strategy_tag)
        return ScreenerPicksResponse(**result)
    except Exception as exc:
        logger.error(f"查询今日选股失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询失败: {str(exc)}"},
        )


@router.get(
    "/picks/{screen_date}",
    response_model=ScreenerPicksResponse,
    responses={
        200: {"description": "指定日期选股结果"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取指定日期选股",
)
def get_picks_by_date(
    screen_date: date,
    strategy_tag: Optional[str] = Query(None, description="策略标签筛选"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> ScreenerPicksResponse:
    try:
        service = ScreenerService(db_manager)
        result = service.get_picks_by_date(screen_date, strategy_tag=strategy_tag)
        return ScreenerPicksResponse(**result)
    except Exception as exc:
        logger.error(f"查询选股结果失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询失败: {str(exc)}"},
        )


@router.get(
    "/watch",
    response_model=ScreenerWatchListResponse,
    responses={
        200: {"description": "观察池列表"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取观察池",
    description="获取当前处于观察状态的股票列表，含收益追踪数据",
)
def get_watch_list(
    days: int = Query(30, ge=1, le=90, description="观察天数范围"),
    strategy_tag: Optional[str] = Query(None, description="策略标签筛选"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> ScreenerWatchListResponse:
    try:
        service = ScreenerService(db_manager)
        result = service.get_watch_list(days=days, strategy_tag=strategy_tag)
        return ScreenerWatchListResponse(**result)
    except Exception as exc:
        logger.error(f"查询观察池失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询失败: {str(exc)}"},
        )


@router.post(
    "/tracking/update",
    response_model=ScreenerTrackingUpdateResponse,
    responses={
        200: {"description": "追踪更新完成"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="更新观察追踪",
    description="更新观察池中股票的实时收益、最大收益、最大回撤，并自动止损/止盈/到期关闭",
)
def update_tracking(
    strategy_tag: Optional[str] = Query(None, description="策略标签筛选"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> ScreenerTrackingUpdateResponse:
    try:
        service = ScreenerService(db_manager)
        result = service.update_tracking_from_market(strategy_tag=strategy_tag)
        return ScreenerTrackingUpdateResponse(**result)
    except Exception as exc:
        logger.error(f"追踪更新失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"追踪更新失败: {str(exc)}"},
        )


@router.post(
    "/backtest-feedback",
    response_model=ScreenerBacktestFeedbackResponse,
    responses={
        200: {"description": "回测反馈完成"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="回测结果反馈",
    description="将回测引擎的结果交叉验证到选股记录，标记 backtest_verified",
)
def apply_backtest_feedback(
    strategy_tag: Optional[str] = Query(None, description="策略标签筛选"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> ScreenerBacktestFeedbackResponse:
    try:
        service = ScreenerService(db_manager)
        result = service.apply_backtest_feedback(strategy_tag=strategy_tag)
        return ScreenerBacktestFeedbackResponse(**result)
    except Exception as exc:
        logger.error(f"回测反馈失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"回测反馈失败: {str(exc)}"},
        )


@router.get(
    "/performance",
    response_model=ScreenerPerformanceResponse,
    responses={
        200: {"description": "选股表现统计"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取选股表现",
    description="统计选股的胜率、平均收益、最大收益、最大亏损",
)
def get_performance(
    days: int = Query(90, ge=1, le=365, description="统计天数范围"),
    strategy_tag: Optional[str] = Query(None, description="策略标签筛选"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> ScreenerPerformanceResponse:
    try:
        service = ScreenerService(db_manager)
        result = service.get_performance_summary(strategy_tag=strategy_tag, days=days)
        return ScreenerPerformanceResponse(**result)
    except Exception as exc:
        logger.error(f"查询选股表现失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询失败: {str(exc)}"},
        )
