# -*- coding: utf-8 -*-
"""Screener endpoints."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_database_manager
from api.v1.schemas.screener import (
    PoolCancelResponse,
    PoolCodesResponse,
    PoolInitRequest,
    PoolInitResponse,
    PoolStatusResponse,
    PoolSummaryResponse,
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
        if request.pool_boards:
            config_overrides['pool_boards'] = request.pool_boards
        if request.pool_industries:
            config_overrides['pool_industries'] = request.pool_industries
        if request.pool_qualities:
            config_overrides['pool_qualities'] = request.pool_qualities
        if request.pool_tags:
            config_overrides['pool_tags'] = request.pool_tags
        if request.pool_min_base_score is not None:
            config_overrides['pool_min_base_score'] = request.pool_min_base_score

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


@router.post(
    "/pool/init",
    response_model=PoolInitResponse,
    responses={
        200: {"description": "股票池初始化已启动"},
        409: {"description": "初始化正在进行中"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="初始化股票池",
    description="全量扫描A股，过滤垃圾股，分类打标签。后台异步执行，通过 /pool/status 查看进度",
)
def init_pool(
    request: PoolInitRequest = PoolInitRequest(),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PoolInitResponse:
    try:
        from src.core.stock_pool import StockPoolInitializer
        pool = StockPoolInitializer.get_instance(db_manager)
        progress = pool.get_progress()
        if progress.status == "running":
            raise HTTPException(
                status_code=409,
                detail={"error": "already_running", "message": f"初始化正在进行中 (version={progress.pool_version}, 进度={progress.progress_pct:.1f}%)"},
            )
        version = pool.start_init(expire_days=request.expire_days)
        return PoolInitResponse(pool_version=version, message="初始化已启动，请通过 /pool/status 查看进度")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"股票池初始化失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"初始化失败: {str(exc)}"},
        )


@router.get(
    "/pool/status",
    response_model=PoolStatusResponse,
    responses={
        200: {"description": "股票池状态"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票池状态",
    description="获取股票池初始化进度、过期倒计时等信息",
)
def get_pool_status(
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PoolStatusResponse:
    try:
        from src.core.stock_pool import StockPoolInitializer
        pool = StockPoolInitializer.get_instance(db_manager)
        result = pool.get_pool_status()

        progress = pool.get_progress()
        if progress.status == "running":
            result["status"] = "running"
            result["progress_pct"] = progress.progress_pct
            result["eta_seconds"] = progress.eta_seconds
            result["total_stocks"] = progress.total
            result["filtered_stocks"] = progress.filtered
            result["tagged_stocks"] = progress.tagged
            result["excluded_stocks"] = progress.excluded

        return PoolStatusResponse(**result)
    except Exception as exc:
        logger.error(f"查询股票池状态失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询失败: {str(exc)}"},
        )


@router.get(
    "/pool/summary",
    response_model=PoolSummaryResponse,
    responses={
        200: {"description": "股票池分布统计"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取股票池分布",
    description="统计股票池中板块、行业、质量等级分布",
)
def get_pool_summary(
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PoolSummaryResponse:
    try:
        from src.core.stock_pool import StockPoolInitializer
        pool = StockPoolInitializer.get_instance(db_manager)
        result = pool.get_pool_summary()
        return PoolSummaryResponse(**result)
    except Exception as exc:
        logger.error(f"查询股票池分布失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询失败: {str(exc)}"},
        )


@router.get(
    "/pool/codes",
    response_model=PoolCodesResponse,
    responses={
        200: {"description": "股票池条目列表"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="查询股票池条目",
    description="按板块/行业/质量/标签筛选股票池中的股票",
)
def get_pool_codes(
    boards: Optional[str] = Query(None, description="板块筛选，逗号分隔（如：科创板,创业板）"),
    industries: Optional[str] = Query(None, description="行业筛选，逗号分隔（如：半导体,新能源）"),
    qualities: Optional[str] = Query(None, description="质量筛选，逗号分隔（如：premium,standard）"),
    tags: Optional[str] = Query(None, description="标签筛选，逗号分隔（如：高分基线,活跃换手）"),
    min_base_score: float = Query(0, ge=0, le=100, description="最低基础评分"),
    limit: int = Query(500, ge=1, le=2000, description="最大返回数量"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PoolCodesResponse:
    try:
        from src.core.stock_pool import StockPoolInitializer
        pool = StockPoolInitializer.get_instance(db_manager)

        board_list = boards.split(",") if boards else None
        industry_list = industries.split(",") if industries else None
        quality_list = qualities.split(",") if qualities else None
        tag_list = tags.split(",") if tags else None

        entries = pool.get_pool_codes(
            boards=board_list,
            industries=industry_list,
            qualities=quality_list,
            tags=tag_list,
            min_base_score=min_base_score,
            limit=limit,
        )

        items = [
            {
                "code": e["code"],
                "name": e.get("name", ""),
                "board": e.get("board", ""),
                "industry": e.get("industry", ""),
                "quality_tier": e.get("quality_tier", ""),
                "base_score": e.get("base_score", 0),
                "tags": e.get("tags", []),
                "market_cap": e.get("market_cap", 0),
                "pe_ratio": e.get("pe_ratio", 0),
                "pb_ratio": e.get("pb_ratio", 0),
                "price": e.get("price", 0),
                "turnover_rate": e.get("turnover_rate", 0),
            }
            for e in entries
        ]

        return PoolCodesResponse(total=len(items), entries=items)
    except Exception as exc:
        logger.error(f"查询股票池条目失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询失败: {str(exc)}"},
        )


@router.post(
    "/pool/cancel",
    response_model=PoolCancelResponse,
    responses={
        200: {"description": "取消初始化"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="取消股票池初始化",
    description="取消正在进行的股票池初始化",
)
def cancel_pool_init(
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PoolCancelResponse:
    try:
        from src.core.stock_pool import StockPoolInitializer
        pool = StockPoolInitializer.get_instance(db_manager)
        progress = pool.get_progress()
        if progress.status != "running":
            return PoolCancelResponse(cancelled=False, message="没有正在进行的初始化")
        pool.cancel()
        return PoolCancelResponse(cancelled=True, message="已发送取消信号")
    except Exception as exc:
        logger.error(f"取消初始化失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"取消失败: {str(exc)}"},
        )
