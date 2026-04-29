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
    description="手动或自动触发回测，计算AI预测与实际走势的偏差",
)
def run_backtest_endpoint(
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


@router.post(
    "/run/stream",
    summary="SSE 流式回测进度",
    description="与 /run 功能相同但通过 SSE 实时推送进度事件(自动分析+评估)",
)
async def run_backtest_stream(
    request: BacktestRunRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
):
    import asyncio
    import json as _json

    async def generate_events():
        try:
            service = BacktestService(db_manager)
            for sse_event in service.run_backtest_with_progress(
                code=request.code,
                codes=request.codes,
                force=request.force,
                eval_window_days=request.eval_window_days,
                min_age_days=request.min_age_days,
                limit=request.limit,
                auto_analyze=request.auto_analyze,
            ):
                yield sse_event
                await asyncio.sleep(0)
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


@router.get(
    "/run/stream",
    summary="SSE 流式回测进度 (GET)",
    description="通过 GET+Query 参数启动 SSE 回测进度流, 兼容 EventSource API",
)
async def run_backtest_stream_get(
    request: Request,
    code: Optional[str] = Query(None, description="股票代码"),
    codes: Optional[str] = Query(None, description="多股逗号分隔"),
    force: bool = Query(False, description="强制重跑"),
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="评估窗口"),
    min_age_days: Optional[int] = Query(None, description="最小分析天数"),
    limit: int = Query(200, ge=1, le=500, description="候选上限"),
    auto_analyze: bool = Query(False, description="无记录时自动分析"),
    db_manager: DatabaseManager = Depends(get_database_manager),
):
    import asyncio
    import json as _json

    code_list = [c.strip() for c in codes.split(",") if c.strip()] if codes else None

    async def generate_events():
        try:
            service = BacktestService(db_manager)
            for sse_event in service.run_backtest_with_progress(
                code=code,
                codes=code_list,
                force=force,
                eval_window_days=eval_window_days,
                min_age_days=min_age_days,
                limit=limit,
                auto_analyze=auto_analyze,
            ):
                yield sse_event
                await asyncio.sleep(0)
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


# ===== v2 策略回测端点 (FR-001~FR-021) =====

@router.post(
    "/strategy",
    summary="运行策略回测 (v2 引擎)",
    description="基于 YAML 策略和 K 线数据运行专业策略回测, 返回 25+ 绩效指标",
)
async def run_strategy_backtest(
    request: "StrategyBacktestRequest",
    db_manager: DatabaseManager = Depends(get_database_manager),
):
    try:
        from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
        from src.backtest.engine import Backtest
        from src.backtest.exit_rules import ExitRule
        from src.backtest.presets import BacktestPresets
        from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
        import pandas as pd
        from datetime import timedelta

        kline_repo = KlineRepo()
        dfs = []
        for code in (request.codes or []):
            df = kline_repo.get_history(code)
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "open": "Open", "high": "High", "low": "Low",
                    "close": "Close", "volume": "Volume",
                })
                if "date" in df.columns:
                    df["Date"] = pd.to_datetime(df["date"].apply(
                        lambda d: ORIGIN_DATE + timedelta(days=int(d))
                    ))
                    df = df.set_index("Date")
                df.attrs["symbol"] = code
                dfs.append(df)

        if not dfs:
            raise HTTPException(
                status_code=404,
                detail={"error": "data_not_found", "message": "未找到指定股票的K线数据"},
            )

        data_df = dfs[0]
        if request.start_date:
            data_df = data_df[data_df.index >= request.start_date]
        if request.end_date:
            data_df = data_df[data_df.index <= request.end_date]

        if len(data_df) < 50:
            raise HTTPException(
                status_code=400,
                detail={"error": "insufficient_data", "message": "K线数据不足(需至少50条)"},
            )

        exit_rule = None
        if request.exit_rules:
            er = request.exit_rules
            exit_rule = ExitRule(
                trailing_stop_pct=er.trailing_stop_pct,
                take_profit_pct=er.take_profit_pct,
                stop_loss_pct=er.stop_loss_pct,
                max_hold_days=er.max_hold_days,
                partial_exit_pct=er.partial_exit_pct if er.partial_exit_enabled else 1.0,
            )

        strategy_cls = yaml_to_strategy_class(request.strategy)
        bt = Backtest(
            data_df,
            strategy_cls,
            cash=request.cash,
            commission=request.commission,
            slippage=request.slippage,
            stamp_duty=request.stamp_duty,
        )

        factors = request.factors or {}
        result = bt.run(**factors)

        response = {
            "result_id": f"bt2_{request.strategy}_{request.codes[0] if request.codes else ''}",
            "strategy_name": result.strategy_name,
            "symbol": result.symbol or (request.codes[0] if request.codes else ""),
            "start_date": str(result.start_date) if result.start_date else None,
            "end_date": str(result.end_date) if result.end_date else None,
            "initial_cash": result.initial_cash,
            "stats": result.to_json().get("stats", {}),
            "trades": result.to_json().get("trades", []),
            "equity_curve": result.to_json().get("equity_curve", []),
            "engine_version": result.engine_version,
            "preset_name": request.preset,
            "elapsed_seconds": result._meta.get("elapsed_seconds", 0),
        }
        return response
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"策略回测失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"策略回测失败: {str(exc)}"},
        )


@router.get(
    "/strategies",
    summary="获取可用策略列表",
    description="扫描 strategies/*.yaml 返回所有 YAML 策略的元信息和因子定义",
)
async def list_strategies():
    try:
        from src.backtest.adapters.yaml_strategy import list_yaml_strategies
        strategies = list_yaml_strategies()
        return {"total": len(strategies), "items": strategies}
    except Exception as exc:
        logger.error(f"获取策略列表失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": str(exc)},
        )


@router.get(
    "/presets",
    summary="获取参数预设列表",
    description="获取 16 种 (活跃度 x 市值) 参数预设组合",
)
async def list_presets():
    try:
        from src.backtest.presets import BacktestPresets
        presets = BacktestPresets.all()
        return {
            "total": len(presets),
            "items": [
                {
                    "name": p.name,
                    "display_name": p.display_name,
                    "activity_level": p.activity_level.value,
                    "cap_size": p.cap_size.value,
                    "threshold": p.threshold,
                    "trailing_stop_pct": p.trailing_stop_pct,
                    "take_profit_pct": p.take_profit_pct,
                    "stop_loss_pct": p.stop_loss_pct,
                    "max_hold_days": p.max_hold_days,
                    "position_sizing": p.position_sizing,
                    "fee_rate": p.fee_rate,
                }
                for p in presets
            ],
        }
    except Exception as exc:
        logger.error(f"获取预设列表失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": str(exc)},
        )


@router.get(
    "/presets/{stock_code}",
    summary="根据股票代码匹配参数预设",
    description="根据股票活跃度和市值自动匹配最合适的参数预设",
)
async def get_preset_for_stock(stock_code: str):
    try:
        from src.backtest.presets import BacktestPresets
        preset = BacktestPresets.from_stock(stock_code)
        return {
            "name": preset.name,
            "display_name": preset.display_name,
            "activity_level": preset.activity_level.value,
            "cap_size": preset.cap_size.value,
            "threshold": preset.threshold,
            "trailing_stop_pct": preset.trailing_stop_pct,
            "take_profit_pct": preset.take_profit_pct,
            "stop_loss_pct": preset.stop_loss_pct,
            "max_hold_days": preset.max_hold_days,
            "position_sizing": preset.position_sizing,
            "fee_rate": preset.fee_rate,
        }
    except Exception as exc:
        logger.error(f"匹配预设失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": str(exc)},
        )


@router.post(
    "/optimize",
    summary="运行参数优化",
    description="对策略参数进行网格搜索或贝叶斯优化",
)
async def run_optimization(
    request: "OptimizeRequest",
    db_manager: DatabaseManager = Depends(get_database_manager),
):
    try:
        from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
        from src.backtest.engine import Backtest
        from src.backtest.optimizer import optimize
        from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
        import pandas as pd
        from datetime import timedelta

        kline_repo = KlineRepo()
        dfs = []
        for code in (request.codes or []):
            df = kline_repo.get_history(code)
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "open": "Open", "high": "High", "low": "Low",
                    "close": "Close", "volume": "Volume",
                })
                if "date" in df.columns:
                    df["Date"] = pd.to_datetime(df["date"].apply(
                        lambda d: ORIGIN_DATE + timedelta(days=int(d))
                    ))
                    df = df.set_index("Date")
                dfs.append(df)

        if not dfs:
            raise HTTPException(
                status_code=404,
                detail={"error": "data_not_found", "message": "未找到K线数据"},
            )

        data_df = dfs[0]
        if request.start_date:
            data_df = data_df[data_df.index >= request.start_date]
        if request.end_date:
            data_df = data_df[data_df.index <= request.end_date]

        strategy_cls = yaml_to_strategy_class(request.strategy)
        bt = Backtest(data_df, strategy_cls)

        factor_ranges = request.factor_ranges or {}
        optimize_kwargs = {}
        for k, v in factor_ranges.items():
            if len(v) >= 2:
                optimize_kwargs[k] = range(int(v[0]), int(v[-1]) + 1, max(1, (int(v[-1]) - int(v[0])) // max(1, len(v) - 1)))
            elif len(v) == 1:
                optimize_kwargs[k] = v

        result_stats = optimize(
            bt,
            maximize=request.maximize or "Sharpe Ratio",
            method=request.method or "grid",
            max_tries=request.max_tries,
            return_heatmap=True,
            return_optimization=True,
            **optimize_kwargs,
        )

        best_params = result_stats.get("_best_params", {})
        best_value = result_stats.get("_best_value", 0)
        heatmap = result_stats.get("_heatmap", {})
        history = result_stats.get("_optimization_history", [])

        return {
            "status": "completed",
            "best_params": best_params,
            "best_value": best_value,
            "best_stats": {k: v for k, v in result_stats.items() if not k.startswith("_")},
            "heatmap": heatmap,
            "total_trials": len(history),
            "elapsed_seconds": 0,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"参数优化失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"参数优化失败: {str(exc)}"},
        )


@router.post(
    "/montecarlo",
    summary="运行蒙特卡洛模拟",
    description="使用随机生成的价格数据测试策略鲁棒性",
)
async def run_montecarlo(
    request: "MontecarloRequest",
):
    try:
        from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
        from src.backtest.engine import Backtest
        from src.backtest.lib import random_ohlc_data
        from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
        import pandas as pd
        from datetime import timedelta
        import time as _time
        import numpy as np

        kline_repo = KlineRepo()
        dfs = []
        for code in (request.codes or []):
            df = kline_repo.get_history(code)
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "open": "Open", "high": "High", "low": "Low",
                    "close": "Close", "volume": "Volume",
                })
                if "date" in df.columns:
                    df["Date"] = pd.to_datetime(df["date"].apply(
                        lambda d: ORIGIN_DATE + timedelta(days=int(d))
                    ))
                    df = df.set_index("Date")
                dfs.append(df)

        if not dfs:
            raise HTTPException(status_code=404, detail={"error": "data_not_found", "message": "未找到K线数据"})

        data_df = dfs[0]
        if request.start_date:
            data_df = data_df[data_df.index >= request.start_date]
        if request.end_date:
            data_df = data_df[data_df.index <= request.end_date]

        strategy_cls = yaml_to_strategy_class(request.strategy)

        original_bt = Backtest(data_df, strategy_cls)
        original_result = original_bt.run()

        t0 = _time.time()
        results = []
        n = request.n_simulations

        for seed in range(n):
            try:
                gen = random_ohlc_data(data_df, frac=request.frac, random_state=seed * 42)
                sim_data = next(gen)
                bt = Backtest(sim_data, strategy_cls, cash=100000)
                r = bt.run()
                results.append({
                    "return_pct": float(r.stats.get("Return [%]", 0)),
                    "sharpe_ratio": float(r.stats.get("Sharpe Ratio", 0)),
                    "max_drawdown_pct": float(r.stats.get("Max Drawdown [%]", 0)),
                    "trade_count": int(r.stats.get("# Trades", 0)),
                })
            except Exception:
                continue

        if not results:
            raise HTTPException(status_code=500, detail={"error": "simulation_failed", "message": "所有模拟均失败"})

        returns = [r["return_pct"] for r in results]
        returns_sorted = sorted(returns)
        median_return = float(np.median(returns))
        p5 = returns_sorted[int(len(returns_sorted) * 0.05)]
        p95 = returns_sorted[int(len(returns_sorted) * 0.95)]
        ruin = sum(1 for r in returns if r < -50) / len(returns)

        return {
            "status": "completed",
            "n_simulations": len(results),
            "original_stats": {
                "return_pct": float(original_result.stats.get("Return [%]", 0)),
                "sharpe_ratio": float(original_result.stats.get("Sharpe Ratio", 0)),
                "max_drawdown_pct": float(original_result.stats.get("Max Drawdown [%]", 0)),
                "trade_count": int(original_result.stats.get("# Trades", 0)),
            },
            "median_return_pct": median_return,
            "p5_return_pct": float(p5),
            "p95_return_pct": float(p95),
            "ruin_probability": ruin,
            "results": results,
            "elapsed_seconds": _time.time() - t0,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"蒙特卡洛模拟失败: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"蒙特卡洛模拟失败: {str(exc)}"},
        )
