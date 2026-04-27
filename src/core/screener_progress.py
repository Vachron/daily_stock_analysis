# -*- coding: utf-8 -*-
"""Screener progress broadcaster — SSE events for pool init and stock screening."""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScreenerStep:
    label: str
    status: str = "pending"
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"label": self.label, "status": self.status, "detail": self.detail}


@dataclass
class ScreenerProgress:
    task_type: str = ""
    status: str = "idle"
    progress_pct: float = 0.0
    message: str = ""
    stage: str = ""
    steps: List[ScreenerStep] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "taskType": self.task_type,
            "status": self.status,
            "progressPct": round(self.progress_pct, 1),
            "message": self.message,
            "stage": self.stage,
            "steps": [s.to_dict() for s in self.steps],
            "extra": self.extra,
            "updatedAt": self.updated_at,
        }


class ScreenerProgressBroadcaster:
    _instance: Optional["ScreenerProgressBroadcaster"] = None
    _lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "ScreenerProgressBroadcaster":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._subscribers: List[asyncio.Queue] = []
        self._subscribers_lock = threading.Lock()
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._pool_progress = ScreenerProgress(task_type="pool_init")
        self._screener_progress = ScreenerProgress(task_type="screener")
        self._data_lock = threading.Lock()
        self._initialized = True

    def get_pool_progress(self) -> ScreenerProgress:
        with self._data_lock:
            return ScreenerProgress(**self._pool_progress.__dict__)

    def get_screener_progress(self) -> ScreenerProgress:
        with self._data_lock:
            return ScreenerProgress(**self._screener_progress.__dict__)

    def update_pool_progress(self, **kwargs: Any) -> None:
        with self._data_lock:
            p = self._pool_progress
            for k, v in kwargs.items():
                if k == "steps" and isinstance(v, list):
                    p.steps = v
                else:
                    setattr(p, k, v)
            p.updated_at = datetime.now().isoformat()
            data = p.to_dict()
        self._broadcast_event("pool_progress", data)

    def update_screener_progress(self, **kwargs: Any) -> None:
        with self._data_lock:
            p = self._screener_progress
            for k, v in kwargs.items():
                if k == "steps" and isinstance(v, list):
                    p.steps = v
                else:
                    setattr(p, k, v)
            p.updated_at = datetime.now().isoformat()
            data = p.to_dict()
        self._broadcast_event("screener_progress", data)

    def reset_pool_progress(self) -> None:
        with self._data_lock:
            self._pool_progress = ScreenerProgress(task_type="pool_init")
        self._broadcast_event("pool_progress", self._pool_progress.to_dict())

    def reset_screener_progress(self) -> None:
        with self._data_lock:
            self._screener_progress = ScreenerProgress(task_type="screener")
        self._broadcast_event("screener_progress", self._screener_progress.to_dict())

    def subscribe(self, queue: asyncio.Queue) -> None:
        with self._subscribers_lock:
            self._subscribers.append(queue)
            try:
                self._main_loop = asyncio.get_running_loop()
            except RuntimeError:
                try:
                    self._main_loop = asyncio.get_event_loop()
                except RuntimeError:
                    pass

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        with self._subscribers_lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    def _broadcast_event(self, event_type: str, data: Dict[str, Any]) -> None:
        event = {"type": event_type, "data": data}
        with self._subscribers_lock:
            subscribers = self._subscribers.copy()
            loop = self._main_loop
        if not subscribers or loop is None:
            return
        for queue in subscribers:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, event)
            except Exception:
                pass


def get_screener_broadcaster() -> ScreenerProgressBroadcaster:
    return ScreenerProgressBroadcaster()
