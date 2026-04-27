# -*- coding: utf-8 -*-
"""Screener endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

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
    WatchCloseRequest,
    WatchCloseResponse,
    WatchRemoveRequest,
    WatchRemoveResponse,
)
from api.v1.schemas.common import ErrorResponse
from src.services.screener_service import ScreenerService
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()

_screener_lock = threading.Lock()
_screener_running = False
_screener_result = None


def _set_state(running=None, result=None):
    global _screener_running, _screener_result
    with _screener_lock:
        if running is not None:
            _screener_running = running
        if result is not None:
            _screener_result = result


def _get_state():
    with _screener_lock:
        return _screener_running, _screener_result


def _run_screener_bg(service, top_n, strategy_tag, config_overrides, demo, db_manager=None):
    try:
        result = service.run_daily_screen(
            top_n=top_n,
            strategy_tag=strategy_tag,
            config_overrides=config_overrides,
            demo=demo,
        )
        _set_state(result=result)

        if result.get("status") == "completed" and db_manager:
            _trigger_insight_generation(result, db_manager)
    except Exception as exc:
        logger.error("[Screener] 后台选股失败: %s", exc, exc_info=True)
        _set_state(result={"status": "failed", "message": str(exc)})
    finally:
        _set_state(running=False)


def _trigger_insight_generation(screener_result, db_manager):
    candidates = screener_result.get("candidates", [])
    if not candidates:
        return
    screen_date_str = screener_result.get("screen_date")
    target_date = date.fromisoformat(screen_date_str) if screen_date_str else date.today()

    candidate_dicts = []
    for c in candidates:
        candidate_dicts.append({
            "code": c.code,
            "name": c.name,
            "score": c.score,
            "quality_tier": getattr(c, "quality_tier", ""),
            "quality_tier_label": getattr(c, "quality_tier_label", ""),
            "price": c.price_at_screen if hasattr(c, "price_at_screen") else getattr(c, "price", 0),
            "market_cap": getattr(c, "market_cap", 0),
            "pe_ratio": getattr(c, "pe_ratio", None),
            "turnover_rate": getattr(c, "turnover_rate", None),
            "signals": getattr(c, "signals", {}),
            "strategy_scores": getattr(c, "strategy_scores", {}),
        })

    def _run_insight_bg():
        try:
            from src.services.screener_insight_service import ScreenerInsightService
            insight_service = ScreenerInsightService(db_manager)
            insight_result = insight_service.generate_insights(
                candidates=candidate_dicts,
                screen_date=target_date,
                market_regime=screener_result.get("market_regime"),
                market_regime_label=screener_result.get("market_regime_label"),
            )
            logger.info("[ScreenerInsight] 自动洞察生成完成: %s", insight_result)
        except Exception as exc:
            logger.error("[ScreenerInsight] 自动洞察生成失败: %s", exc, exc_info=True)

    t = threading.Thread(target=_run_insight_bg, daemon=True)
    t.start()
    logger.info("[ScreenerInsight] 已启动自动洞察生成，共 %d 只股票", len(candidate_dicts))


@router.post(
    "/run",
    response_model=ScreenerRunResponse,
    responses={
        200: {"description": "选股任务已提交或已完成"},
        409: {"description": "选股任务正在执行中", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="触发每日选股",
    description="从全市场A股中筛选Top N股票，后台异步执行，通过 /run/status 查看进度",
)
def run_screener(
    request: ScreenerRunRequest = ScreenerRunRequest(),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> ScreenerRunResponse:
    running, _ = _get_state()

    if running:
        raise HTTPException(
            status_code=409,
            detail={"error": "already_running", "message": "选股任务正在执行中，请稍后查询结果"},
        )

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

    service = ScreenerService(db_manager)
    _set_state(running=True, result=None)

    t = threading.Thread(
        target=_run_screener_bg,
        args=(service, request.top_n, request.strategy_tag, config_overrides, False, db_manager),
        daemon=True,
    )
    t.start()

    return ScreenerRunResponse(
        screened=0,
        saved=0,
        screen_date=date.today().isoformat(),
        status="running",
        message="选股任务已提交，请通过 /run/status 查看进度",
    )


@router.get(
    "/run/status",
    response_model=ScreenerRunResponse,
    summary="查询选股任务状态",
    description="查询当前选股任务的执行状态和结果",
)
def get_screener_status() -> ScreenerRunResponse:
    running, result = _get_state()

    if running:
        return ScreenerRunResponse(
            screened=0,
            saved=0,
            screen_date=date.today().isoformat(),
            status="running",
            message="选股任务执行中...",
        )

    if result is None:
        return ScreenerRunResponse(
            screened=0,
            saved=0,
            screen_date="",
            status="idle",
            message="暂无选股任务",
        )

    if result.get("status") == "failed":
        return ScreenerRunResponse(
            screened=0,
            saved=0,
            screen_date=date.today().isoformat(),
            status="failed",
            message=result.get("message", "选股失败"),
        )

    return ScreenerRunResponse(
        screened=result.get("screened", 0),
        saved=result.get("saved", 0),
        screen_date=result.get("screen_date", ""),
        candidates=result.get("candidates", []),
        data_failures=result.get("data_failures", []),
        quality_summary=result.get("quality_summary"),
        market_regime=result.get("market_regime"),
        market_regime_label=result.get("market_regime_label"),
        optimized_weights_applied=result.get("optimized_weights_applied"),
        status="completed",
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
    "/watch/close",
    response_model=WatchCloseResponse,
    responses={
        200: {"description": "关闭成功"},
        404: {"description": "股票不在观察池中"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="关闭观察",
    description="将观察池中的股票标记为已关闭（保留历史记录）",
)
def close_watch_stock(
    request: WatchCloseRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> WatchCloseResponse:
    try:
        service = ScreenerService(db_manager)
        result = service.close_watch_stock(
            code=request.code,
            exit_reason=request.exit_reason,
            strategy_tag=request.strategy_tag,
        )
        if result["closed"] == 0:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"股票 {request.code} 不在观察池中"},
            )
        return WatchCloseResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"关闭观察失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"关闭失败: {str(exc)}"},
        )


@router.post(
    "/watch/remove",
    response_model=WatchRemoveResponse,
    responses={
        200: {"description": "移除成功"},
        404: {"description": "股票不在观察池中"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="移除观察",
    description="从观察池中彻底移除股票（删除记录）",
)
def remove_watch_stock(
    request: WatchRemoveRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> WatchRemoveResponse:
    try:
        service = ScreenerService(db_manager)
        result = service.remove_watch_stock(
            code=request.code,
            strategy_tag=request.strategy_tag,
        )
        if result["removed"] == 0:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"股票 {request.code} 不在观察池中"},
            )
        return WatchRemoveResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"移除观察失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"移除失败: {str(exc)}"},
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


@router.get(
    "/insight",
    summary="获取选股 AI 洞察",
    description="获取指定日期所有候选股的 AI 增强分析结果",
)
def get_insights(
    screen_date: Optional[str] = Query(None, description="选股日期 (YYYY-MM-DD)"),
    db_manager: DatabaseManager = Depends(get_database_manager),
):
    try:
        target_date = date.fromisoformat(screen_date) if screen_date else date.today()
        from src.services.screener_insight_service import ScreenerInsightService
        service = ScreenerInsightService(db_manager)
        insights = service.get_insights_by_date(target_date)
        return {"insights": insights, "total": len(insights)}
    except Exception as exc:
        logger.error(f"获取洞察失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"获取洞察失败: {str(exc)}"},
        )


@router.get(
    "/insight/{code}",
    summary="获取单只股票 AI 洞察",
    description="获取指定日期和股票代码的 AI 增强分析结果",
)
def get_insight_by_code(
    code: str,
    screen_date: Optional[str] = Query(None, description="选股日期 (YYYY-MM-DD)"),
    db_manager: DatabaseManager = Depends(get_database_manager),
):
    try:
        target_date = date.fromisoformat(screen_date) if screen_date else date.today()
        from src.services.screener_insight_service import ScreenerInsightService
        service = ScreenerInsightService(db_manager)
        insight = service.get_insight(target_date, code)
        if not insight:
            return {"insight": None}
        return {"insight": insight}
    except Exception as exc:
        logger.error(f"获取洞察失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"获取洞察失败: {str(exc)}"},
        )


@router.post(
    "/insight/generate",
    summary="生成选股 AI 洞察",
    description="对最新选股结果批量生成 AI 增强分析（异步执行）",
)
def generate_insights(
    screen_date: Optional[str] = Query(None, description="指定选股日期 (YYYY-MM-DD)，默认取最近一次"),
    db_manager: DatabaseManager = Depends(get_database_manager),
):
    target_date = date.fromisoformat(screen_date) if screen_date else None
    candidate_dicts = []
    market_regime = None
    market_regime_label = None

    _, screener_result = _get_state()
    if screener_result and screener_result.get("status") == "completed":
        candidates = screener_result.get("candidates", [])
        if candidates:
            screen_date_str = screener_result.get("screen_date")
            target_date = target_date or (date.fromisoformat(screen_date_str) if screen_date_str else date.today())
            market_regime = screener_result.get("market_regime")
            market_regime_label = screener_result.get("market_regime_label")
            for c in candidates:
                candidate_dicts.append({
                    "code": c.code,
                    "name": c.name,
                    "score": c.score,
                    "quality_tier": getattr(c, "quality_tier", ""),
                    "quality_tier_label": getattr(c, "quality_tier_label", ""),
                    "price": c.price_at_screen if hasattr(c, "price_at_screen") else getattr(c, "price", 0),
                    "market_cap": getattr(c, "market_cap", 0),
                    "pe_ratio": getattr(c, "pe_ratio", None),
                    "turnover_rate": getattr(c, "turnover_rate", None),
                    "signals": getattr(c, "signals", {}),
                    "strategy_scores": getattr(c, "strategy_scores", {}),
                })

    if not candidate_dicts:
        from src.services.screener_service import ScreenerService
        service = ScreenerService(db_manager)
        if not target_date:
            latest = service.get_today_picks()
            if not latest.get("picks"):
                raise HTTPException(
                    status_code=400,
                    detail={"error": "no_results", "message": "没有已完成的选股结果，请先运行选股"},
                )
            target_date = date.fromisoformat(latest["screen_date"]) if latest.get("screen_date") else date.today()
        else:
            latest = service.get_picks_by_date(target_date)

        picks = latest.get("picks", [])
        if not picks:
            raise HTTPException(
                status_code=400,
                detail={"error": "no_candidates", "message": "选股结果为空"},
            )

        for p in picks:
            p_any = p if isinstance(p, dict) else p.__dict__ if hasattr(p, '__dict__') else {}
            candidate_dicts.append({
                "code": p_any.get("code", ""),
                "name": p_any.get("name", ""),
                "score": p_any.get("score", 0),
                "quality_tier": p_any.get("qualityTier", p_any.get("quality_tier", "")),
                "quality_tier_label": p_any.get("qualityTierLabel", p_any.get("quality_tier_label", "")),
                "price": p_any.get("priceAtScreen", p_any.get("price_at_screen", p_any.get("price", 0))),
                "market_cap": p_any.get("marketCap", p_any.get("market_cap", 0)),
                "pe_ratio": p_any.get("peRatio", p_any.get("pe_ratio", None)),
                "turnover_rate": p_any.get("turnoverRate", p_any.get("turnover_rate", None)),
                "signals": p_any.get("signals", {}),
                "strategy_scores": p_any.get("strategyScores", p_any.get("strategy_scores", {})),
            })
        market_regime = latest.get("market_regime")
        market_regime_label = latest.get("market_regime_label")

    def _run_bg():
        try:
            from src.services.screener_insight_service import ScreenerInsightService
            service = ScreenerInsightService(db_manager)
            result = service.generate_insights(
                candidates=candidate_dicts,
                screen_date=target_date,
                market_regime=market_regime,
                market_regime_label=market_regime_label,
            )
            logger.info("[ScreenerInsight] 洞察生成完成: %s", result)
        except Exception as exc:
            logger.error("[ScreenerInsight] 洞察生成失败: %s", exc, exc_info=True)

    t = threading.Thread(target=_run_bg, daemon=True)
    t.start()

    return {"status": "generating", "message": f"正在为 {len(candidate_dicts)} 只股票生成 AI 洞察，请稍后通过 /insight 查看"}


@router.get(
    "/stream",
    responses={
        200: {"description": "SSE 事件流", "content": {"text/event-stream": {}}},
    },
    summary="选股进度 SSE 流",
    description="通过 Server-Sent Events 实时推送股票池初始化和选股进度",
)
async def screener_stream():
    from src.core.screener_progress import get_screener_broadcaster

    broadcaster = get_screener_broadcaster()

    async def event_generator():
        event_queue: asyncio.Queue = asyncio.Queue()

        yield f"event: connected\ndata: {json.dumps({'message': 'Connected to screener stream'})}\n\n"

        pool_progress = broadcaster.get_pool_progress()
        if pool_progress.status not in ("idle", ""):
            yield f"event: pool_progress\ndata: {json.dumps(pool_progress.to_dict())}\n\n"

        screener_progress = broadcaster.get_screener_progress()
        if screener_progress.status not in ("idle", ""):
            yield f"event: screener_progress\ndata: {json.dumps(screener_progress.to_dict())}\n\n"

        broadcaster.subscribe(event_queue)

        try:
            while True:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=30)
                    event_type = event.get("type", "unknown")
                    event_data = event.get("data", {})
                    yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.now().isoformat()})}\n\n"
        except asyncio.CancelledError:
            logger.debug("SSE client disconnected from screener stream")
            raise
        finally:
            broadcaster.unsubscribe(event_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
