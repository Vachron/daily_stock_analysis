# -*- coding: utf-8 -*-
"""AI 信号适配器 — 将 AnalysisHistory 转换为回测信号."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class AISignalAdapter:
    """AI 分析历史到回测信号的适配器."""

    @staticmethod
    def predictions_to_signals(
        predictions: List[Any],
        threshold: float = 0.55,
    ) -> Dict[str, List[dict]]:
        """将 AI 预测列表转换为按日期索引的信号字典.

        Args:
            predictions: AnalysisHistory 或类似对象列表
            threshold: 信号阈值

        Returns:
            {date_str: [signal_dict, ...]}
        """
        signals: Dict[str, List[dict]] = {}
        for p in predictions:
            date = getattr(p, "analysis_date", None)
            if date is None:
                continue
            date_str = str(date)[:10] if not isinstance(date, str) else date[:10]

            up_prob = float(getattr(p, "up_probability", 0.5) or 0.5)
            confidence = float(getattr(p, "confidence", 0.5) or 0.5)

            signal = {
                "up_probability": up_prob,
                "confidence": confidence,
                "avg_ret_5d": float(getattr(p, "expected_return_5d", 0) or 0),
            }
            signals.setdefault(date_str, []).append(signal)
        return signals

    @staticmethod
    def extract_stock_data(code: str, db_manager: Any = None) -> Optional[pd.DataFrame]:
        """从数据库提取股票的 OHLCV 数据."""
        import pandas as pd
        try:
            from src.storage import StockDaily, DatabaseManager
            from sqlalchemy import select, and_

            db = db_manager or DatabaseManager.get_instance()
            with db.get_session() as session:
                stmt = (
                    select(StockDaily)
                    .where(StockDaily.code == code)
                    .order_by(StockDaily.date.asc())
                )
                rows = session.execute(stmt).scalars().all()
                if not rows:
                    return None
                df = pd.DataFrame([{
                    "Date": r.date,
                    "Open": r.open,
                    "High": r.high,
                    "Low": r.low,
                    "Close": r.close,
                    "Volume": r.volume,
                } for r in rows])
                df = df.set_index("Date").sort_index()
                return df
        except Exception:
            return None
