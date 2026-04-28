# -*- coding: utf-8 -*-
"""Alpha system API endpoints.

Provides REST endpoints and SSE stream for the Alpha excess return system.
Exposes factor debugging, auto-optimization, health checks, and pipeline results.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.deps import get_database_manager
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["alpha"])

ALPHA_BROADCASTER = None


def _get_broadcaster():
    global ALPHA_BROADCASTER
    if ALPHA_BROADCASTER is None:
        ALPHA_BROADCASTER = _AlphaBroadcaster()
    return ALPHA_BROADCASTER


class _AlphaBroadcaster:
    def __init__(self):
        self._queues: List[asyncio.Queue] = []
        self._lock = threading.Lock()
        self._progress: Dict[str, Any] = {"status": "idle", "progressPct": 0, "message": ""}

    def subscribe(self, queue: asyncio.Queue) -> None:
        with self._lock:
            self._queues.append(queue)

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        with self._lock:
            if queue in self._queues:
                self._queues.remove(queue)

    def get_current_progress(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._progress)

    def broadcast(self, event_type: str, data: Dict[str, Any]) -> None:
        with self._lock:
            self._progress = data
            queues = list(self._queues)
        for q in queues:
            try:
                q.put_nowait({"type": event_type, "data": data})
            except asyncio.QueueFull:
                pass


class AlphaRunRequest(BaseModel):
    start_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    strategy_names: Optional[List[str]] = Field(None, description="策略名称列表")
    benchmark_code: str = Field("000300", description="Benchmark代码")
    top_n: int = Field(20, ge=5, le=50, description="持仓股票数")
    pool_size: int = Field(500, ge=100, le=5000, description="候选池大小")


class AlphaAutoRequest(BaseModel):
    start_date: Optional[str] = Field(None)
    end_date: Optional[str] = Field(None)
    strategy_names: Optional[List[str]] = Field(None)
    benchmark_code: str = Field("000300")
    top_n: int = Field(20, ge=5, le=50)
    max_iterations: int = Field(50, ge=10, le=500, description="最大迭代次数")


class AlphaHealthResponse(BaseModel):
    status: str
    healthy: int
    aged: int
    total_factors: int
    factors: List[Dict[str, Any]]
    rotations: List[Dict[str, Any]]


class AlphaRunResponse(BaseModel):
    status: str
    metrics: Dict[str, Any]
    risk_neutralization: Dict[str, Any]
    num_trading_days: int
    final_nav: float


@router.get("/stream")
async def alpha_stream():
    broadcaster = _get_broadcaster()

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()
        yield f"event: connected\ndata: {json.dumps({'message': 'Connected to alpha stream'})}\n\n"

        current = broadcaster.get_current_progress()
        if current.get("status") not in ("idle", ""):
            yield f"event: alpha_progress\ndata: {json.dumps(current, ensure_ascii=False)}\n\n"

        broadcaster.subscribe(queue)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"event: {event['type']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.now().isoformat()})}\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


def _run_alpha_pipeline_bg(request: AlphaRunRequest, broadcaster: _AlphaBroadcaster):
    try:
        from src.alpha.cli import run_alpha_pipeline

        start = date.today().replace(year=date.today().year - 3) if not request.start_date else date.fromisoformat(request.start_date)
        end = date.today() if not request.end_date else date.fromisoformat(request.end_date)

        def progress_callback(pct: float, message: str):
            broadcaster.broadcast("alpha_progress", {
                "status": "running",
                "progressPct": round(pct, 1),
                "message": message,
                "stage": "scoring" if pct < 75 else "simulating",
            })

        broadcaster.broadcast("alpha_progress", {"status": "running", "progressPct": 0, "message": "Starting Alpha pipeline...", "stage": "init"})

        result = run_alpha_pipeline(
            start_date=start, end_date=end,
            strategy_names=request.strategy_names,
            benchmark_code=request.benchmark_code,
            top_n=request.top_n, pool_size=request.pool_size,
            progress_callback=progress_callback,
        )

        metrics = result.get("metrics", {})
        broadcaster.broadcast("alpha_progress", {
            "status": "completed",
            "progressPct": 100,
            "message": "Pipeline complete: IR=%.4f" % metrics.get("information_ratio", 0),
            "stage": "done",
            "metrics": metrics,
        })
    except Exception as e:
        logger.error("Alpha pipeline failed: %s", e, exc_info=True)
        broadcaster.broadcast("alpha_progress", {
            "status": "failed",
            "progressPct": 0,
            "message": str(e),
            "stage": "error",
        })


def _run_alpha_auto_bg(request: AlphaAutoRequest, broadcaster: _AlphaBroadcaster):
    try:
        from src.alpha.cli import run_alpha_auto_optimize

        start = date.today().replace(year=date.today().year - 3) if not request.start_date else date.fromisoformat(request.start_date)
        end = date.today() if not request.end_date else date.fromisoformat(request.end_date)

        def progress_callback(pct: float, message: str):
            broadcaster.broadcast("alpha_progress", {
                "status": "running", "progressPct": round(pct, 1), "message": message, "stage": "optimizing",
            })

        result = run_alpha_auto_optimize(
            start_date=start, end_date=end,
            strategy_names=request.strategy_names,
            benchmark_code=request.benchmark_code,
            top_n=request.top_n,
            max_iterations=request.max_iterations,
        )

        broadcaster.broadcast("alpha_progress", {
            "status": "completed",
            "progressPct": 100,
            "message": "Optimization complete: %d iterations, best IR=%.4f" % (result["iterations"], result["best_ir"]),
            "stage": "done",
            "metrics": {"best_ir": result["best_ir"], "best_excess": result["best_excess"], "iterations": result["iterations"]},
        })
    except Exception as e:
        logger.error("Alpha auto-optimize failed: %s", e, exc_info=True)
        broadcaster.broadcast("alpha_progress", {"status": "failed", "progressPct": 0, "message": str(e), "stage": "error"})


@router.post("/run", response_model=Dict[str, Any])
def run_alpha_pipeline_endpoint(
    request: AlphaRunRequest,
    background_tasks: BackgroundTasks,
):
    broadcaster = _get_broadcaster()
    background_tasks.add_task(_run_alpha_pipeline_bg, request, broadcaster)
    return {"status": "running", "message": "Alpha pipeline started, subscribe to /alpha/stream for progress"}


@router.post("/auto", response_model=Dict[str, Any])
def run_alpha_auto_endpoint(
    request: AlphaAutoRequest,
    background_tasks: BackgroundTasks,
):
    broadcaster = _get_broadcaster()
    background_tasks.add_task(_run_alpha_auto_bg, request, broadcaster)
    return {"status": "running", "message": "Auto-optimization started, subscribe to /alpha/stream for progress"}


@router.get("/health", response_model=AlphaHealthResponse)
def get_alpha_health():
    try:
        from src.alpha.cli import run_factor_health_check
        result = run_factor_health_check()
        return AlphaHealthResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": str(e)})


@router.get("/config/best")
def get_best_alpha_config():
    import glob
    files = sorted(glob.glob("data/optimized_strategies/alpha_best_config_*.json"), reverse=True)
    if not files:
        return {"status": "none", "message": "No optimized configs found. Run auto-optimization first."}
    try:
        with open(files[0], "r", encoding="utf-8") as f:
            return {"status": "ok", "path": files[0], "config": json.load(f)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
