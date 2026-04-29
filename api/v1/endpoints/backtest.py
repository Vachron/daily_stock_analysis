# -*- coding: utf-8 -*-
"""Backtest endpoints."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from api.deps import get_database_manager
from api.v1.schemas.backtest import (
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestResultItem,
    BacktestResultsResponse,
    EquityCurveResponse,
    PerformanceMetrics,
)
from api.v1.schemas.common import ErrorResponse
from src.services.backtest_service import BacktestService
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_analysis_date_range(
    analysis_date_from: Optional[date],
    analysis_date_to: Optional[date],
) -> None:
    if analysis_date_from and analysis_date_to and analysis_date_from > analysis_date_to:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_params",
                "message": "analysis_date_from cannot be after analysis_date_to",
            },
        )


@router.post(
    "/run",
    response_model=BacktestRunResponse,
    responses={
        200: {"description": "回测执行完成"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="触发回测",
    description="对历史分析记录进行回测评估，并写入 backtest_results/backtest_summaries",
)
def run_backtest(
    request: BacktestRunRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestRunResponse:
    try:
        service = BacktestService(db_manager)
        stats = service.run_backtest(
            code=request.code,
            codes=request.codes,
            force=request.force,
            eval_window_days=request.eval_window_days,
            min_age_days=request.min_age_days,
            limit=request.limit,
            auto_analyze=request.auto_analyze,
        )
        return BacktestRunResponse(**stats)
    except Exception as exc:
        logger.error(f"回测执行失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"回测执行失败: {str(exc)}"},
        )


@router.get(
    "/results",
    response_model=BacktestResultsResponse,
    responses={
        200: {"description": "回测结果列表"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取回测结果",
    description="分页获取回测结果，支持按股票代码过滤",
)
def get_backtest_results(
    code: Optional[str] = Query(None, description="股票代码筛选"),
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="评估窗口过滤"),
    analysis_date_from: Optional[date] = Query(None, description="分析日期起始（含）"),
    analysis_date_to: Optional[date] = Query(None, description="分析日期结束（含）"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=200, description="每页数量"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestResultsResponse:
    try:
        _validate_analysis_date_range(analysis_date_from, analysis_date_to)
        service = BacktestService(db_manager)
        data = service.get_recent_evaluations(
            code=code,
            eval_window_days=eval_window_days,
            limit=limit,
            page=page,
            analysis_date_from=analysis_date_from,
            analysis_date_to=analysis_date_to,
        )
        items = [BacktestResultItem(**item) for item in data.get("items", [])]
        return BacktestResultsResponse(
            total=int(data.get("total", 0)),
            page=page,
            limit=limit,
            items=items,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"查询回测结果失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询回测结果失败: {str(exc)}"},
        )


@router.get(
    "/performance",
    response_model=PerformanceMetrics,
    responses={
        200: {"description": "整体回测表现"},
        404: {"description": "无回测汇总", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取整体回测表现",
)
def get_overall_performance(
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="评估窗口过滤"),
    analysis_date_from: Optional[date] = Query(None, description="分析日期起始（含）"),
    analysis_date_to: Optional[date] = Query(None, description="分析日期结束（含）"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PerformanceMetrics:
    try:
        _validate_analysis_date_range(analysis_date_from, analysis_date_to)
        service = BacktestService(db_manager)
        summary = service.get_summary(
            scope="overall",
            code=None,
            eval_window_days=eval_window_days,
            analysis_date_from=analysis_date_from,
            analysis_date_to=analysis_date_to,
        )
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "未找到整体回测汇总"},
            )
        return PerformanceMetrics(**summary)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"查询整体表现失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询整体表现失败: {str(exc)}"},
        )


@router.get(
    "/performance/{code}",
    response_model=PerformanceMetrics,
    responses={
        200: {"description": "单股回测表现"},
        404: {"description": "无回测汇总", "model": ErrorResponse},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取单股回测表现",
)
def get_stock_performance(
    code: str,
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="评估窗口过滤"),
    analysis_date_from: Optional[date] = Query(None, description="分析日期起始（含）"),
    analysis_date_to: Optional[date] = Query(None, description="分析日期结束（含）"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PerformanceMetrics:
    try:
        _validate_analysis_date_range(analysis_date_from, analysis_date_to)
        service = BacktestService(db_manager)
        summary = service.get_summary(
            scope="stock",
            code=code,
            eval_window_days=eval_window_days,
            analysis_date_from=analysis_date_from,
            analysis_date_to=analysis_date_to,
        )
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"未找到 {code} 的回测汇总"},
            )
        return PerformanceMetrics(**summary)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"查询单股表现失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询单股表现失败: {str(exc)}"},
        )


@router.get(
    "/equity-curve",
    response_model=EquityCurveResponse,
    responses={
        200: {"description": "资金曲线数据"},
        500: {"description": "服务器错误", "model": ErrorResponse},
    },
    summary="获取资金曲线",
    description="获取回测资金曲线（累计收益率+回撤曲线），按分析日期排序",
)
def get_equity_curve(
    code: Optional[str] = Query(None, description="股票代码筛选"),
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="评估窗口过滤"),
    analysis_date_from: Optional[date] = Query(None, description="分析日期起始（含）"),
    analysis_date_to: Optional[date] = Query(None, description="分析日期结束（含）"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> EquityCurveResponse:
    try:
        _validate_analysis_date_range(analysis_date_from, analysis_date_to)
        service = BacktestService(db_manager)
        data = service.get_equity_curve(
            code=code,
            eval_window_days=eval_window_days,
            analysis_date_from=analysis_date_from,
            analysis_date_to=analysis_date_to,
        )
        return EquityCurveResponse(**data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"查询资金曲线失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"查询资金曲线失败: {str(exc)}"},
        )


@router.get(
    "/kline-stats",
    summary="获取K线数据库统计",
    description="返回本地K线Parquet数据库的导入状态和数据统计",
)
def get_kline_stats():
    try:
        from data_provider.kline_repo import KlineRepo
        repo = KlineRepo()
        return {"status": "ok", "stats": repo.get_statistics()}
    except Exception as exc:
        logger.error(f"K线统计失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": str(exc)},
        )


@router.get("/portfolio/stream", summary="SSE 流式组合回测进度")
async def stream_portfolio_backtest(
    request: Request,
    run_id: str = Query(..., description="回测任务 ID"),
):
    import asyncio
    import json as _json

    async def generate_events():
        try:
            from src.core.portfolio_backtest_engine import PortfolioBacktestEngine, BacktestParams

            engine = PortfolioBacktestEngine()
            if not engine.ready:
                yield f"event: error\ndata: {_json.dumps({'message': 'K-line data not available. Run import_kline.py first.'})}\n\n"
                return

            yield f"event: connected\ndata: {{}}\n\n"
            await asyncio.sleep(0)

            params = BacktestParams(
                initial_capital=100000,
                max_positions=10,
                rebalance_freq_days=5,
            )

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, engine.run, params)

            if result.success:
                nav_json = None
                if result.nav_df is not None and not result.nav_df.empty:
                    nav_records = result.nav_df.to_dict(orient="records")
                    nav_json = [
                        {k: (v.isoformat() if hasattr(v, 'isoformat') else (float(v) if isinstance(v, (float, int)) else v))
                         for k, v in r.items()}
                        for r in nav_records[-50:]
                    ]

                yield f"event: completed\ndata: {_json.dumps({
                    'run_id': run_id,
                    'success': True,
                    'error': None,
                    'metrics': result.metrics,
                    'nav': nav_json or [],
                    'trades': result.trades[-100:],
                    'elapsed_seconds': result.elapsed_seconds,
                })}\n\n"
            else:
                yield f"event: error\ndata: {_json.dumps({'message': result.error or '回测执行失败'})}\n\n"

        except Exception as exc:
            logger.error(f"SSE回测失败: {exc}", exc_info=True)
            yield f"event: error\ndata: {_json.dumps({'message': str(exc)})}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/portfolio",
    summary="运行策略因子回测",
    description="基于用户设定的参数和因子值，对历史全市场数据进行组合回测",
)
def run_portfolio_backtest(
    initial_capital: float = Query(100000, ge=10000, description="初始资金"),
    start_date: Optional[str] = Query(None, description="回测起始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="回测结束日期 YYYY-MM-DD"),
    max_positions: int = Query(10, ge=1, le=50, description="最大持仓数"),
    rebalance_days: int = Query(5, ge=1, le=60, description="调仓周期(交易日)"),
    factor_json: Optional[str] = Query(None, description="因子值 JSON 字符串"),
):
    import json as _json
    from datetime import date as _date

    try:
        from src.core.portfolio_backtest_engine import PortfolioBacktestEngine, BacktestParams

        engine = PortfolioBacktestEngine()
        if not engine.ready:
            raise HTTPException(
                status_code=503,
                detail={"error": "data_not_ready", "message": "K-line data not imported yet. Run import_kline.py first."},
            )

        params = BacktestParams(
            initial_capital=initial_capital,
            start_date=_date.fromisoformat(start_date) if start_date else None,
            end_date=_date.fromisoformat(end_date) if end_date else None,
            max_positions=max_positions,
            rebalance_freq_days=rebalance_days,
        )

        if factor_json:
            params.factor_values = _json.loads(factor_json)

        result = engine.run(params)

        nav_json = None
        if result.nav_df is not None and not result.nav_df.empty:
            nav_records = result.nav_df.to_dict(orient="records")
            nav_json = [
                {k: (v.isoformat() if hasattr(v, 'isoformat') else (float(v) if isinstance(v, (np.floating, float)) else v))
                 for k, v in r.items()}
                for r in nav_records[-50:]
            ]

        return {
            "status": "ok",
            "run_id": result.run_id,
            "success": result.success,
            "error": result.error,
            "metrics": result.metrics,
            "trades": result.trades[-100:],
            "nav": nav_json,
            "elapsed_seconds": result.elapsed_seconds,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"组合回测失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": str(exc)},
        )
