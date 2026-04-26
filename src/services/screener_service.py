# -*- coding: utf-8 -*-
"""Screener service — orchestrate screening, tracking, rotation, and backtest feedback."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from src.config import get_config
from src.core.screener_engine import ScreenerCandidate, ScreenerConfig, ScreenerEngine
from src.repositories.screener_repo import ScreenerRepository
from src.storage import DatabaseManager, ScreenerResult

logger = logging.getLogger(__name__)


class ScreenerService:
    """Service layer for stock screening operations."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()
        self.repo = ScreenerRepository(self.db)

    def run_daily_screen(
        self,
        top_n: int = 10,
        strategy_tag: Optional[str] = None,
        config_overrides: Optional[Dict[str, Any]] = None,
        demo: bool = False,
    ) -> Dict[str, Any]:
        """Execute a daily screening run and persist results.

        Returns summary dict with count and top candidates.
        """
        cfg = ScreenerConfig(top_n=top_n)
        if strategy_tag:
            cfg.strategy_tag = strategy_tag
        if config_overrides:
            for k, v in config_overrides.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)

        engine = ScreenerEngine(cfg)
        run_result = engine.run(demo=demo)

        candidates = run_result.candidates
        if not candidates:
            return {
                "screened": 0,
                "saved": 0,
                "screen_date": date.today().isoformat(),
                "candidates": [],
                "data_failures": [],
                "quality_summary": run_result.quality_summary,
                "market_regime": run_result.market_regime,
                "market_regime_label": run_result.market_regime_label,
                "optimized_weights_applied": run_result.optimized_weights_applied,
            }

        today = date.today()
        results = []
        for c in candidates:
            results.append(ScreenerResult(
                screen_date=today,
                code=c.code,
                name=c.name,
                score=c.score,
                rank=c.rank,
                strategy_tag=cfg.strategy_tag,
                price_at_screen=c.price,
                market_cap=c.market_cap,
                turnover_rate=c.turnover_rate,
                pe_ratio=c.pe_ratio,
                pb_ratio=c.pb_ratio,
                signals_json=json.dumps(
                    {
                        **c.signals,
                        "strategy_scores": c.strategy_scores,
                        "quality_tier": c.quality_tier,
                        "quality_tier_label": c.quality_tier_label,
                        "data_fetch_failed": c.data_fetch_failed,
                        "data_fetch_reason": c.data_fetch_reason,
                    },
                    ensure_ascii=False,
                ) if c.signals or c.strategy_scores else None,
                status='watch',
            ))

        saved = self.repo.save_results_batch(results)

        return {
            "screened": len(candidates),
            "saved": saved,
            "screen_date": today.isoformat(),
            "candidates": [
                {
                    "rank": c.rank,
                    "code": c.code,
                    "name": c.name,
                    "score": c.score,
                    "price": c.price,
                    "market_cap_yi": round(c.market_cap / 1e8, 2) if c.market_cap else 0,
                    "turnover_rate": c.turnover_rate,
                    "pe_ratio": c.pe_ratio,
                    "signals": c.signals,
                    "strategy_scores": c.strategy_scores,
                    "market_regime": c.market_regime,
                    "market_regime_label": c.market_regime_label,
                    "quality_tier": c.quality_tier,
                    "quality_tier_label": c.quality_tier_label,
                    "data_fetch_failed": c.data_fetch_failed,
                    "data_fetch_reason": c.data_fetch_reason,
                }
                for c in candidates
            ],
            "data_failures": [
                {
                    "code": f.code,
                    "name": f.name,
                    "reason": f.reason,
                    "fallback": f.fallback,
                }
                for f in run_result.data_failures
            ],
            "quality_summary": run_result.quality_summary,
            "market_regime": run_result.market_regime,
            "market_regime_label": run_result.market_regime_label,
            "optimized_weights_applied": run_result.optimized_weights_applied,
        }

    def get_today_picks(
        self,
        strategy_tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get today's screening results."""
        today = date.today()
        rows = self.repo.get_results_by_date(today, strategy_tag=strategy_tag)
        if not rows:
            return {"date": today.isoformat(), "picks": [], "total": 0}
        return {
            "date": today.isoformat(),
            "total": len(rows),
            "picks": [self._result_to_dict(r) for r in rows],
        }

    def get_picks_by_date(
        self,
        screen_date: date,
        strategy_tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get screening results for a specific date."""
        rows = self.repo.get_results_by_date(screen_date, strategy_tag=strategy_tag)
        return {
            "date": screen_date.isoformat(),
            "total": len(rows),
            "picks": [self._result_to_dict(r) for r in rows],
        }

    def get_watch_list(
        self,
        days: int = 30,
        strategy_tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get all stocks currently in watch status."""
        rows = self.repo.get_watch_list(status='watch', days=days, strategy_tag=strategy_tag)
        return {
            "total": len(rows),
            "watch_list": [self._result_to_dict(r) for r in rows],
        }

    def update_tracking_from_market(self, strategy_tag: Optional[str] = None) -> Dict[str, Any]:
        """Update tracking data (return %, max return, drawdown) for all watched stocks.

        Fetches current prices and computes performance metrics since screen date.
        """
        watch_rows = self.repo.get_watch_list(status='watch', days=60, strategy_tag=strategy_tag)
        if not watch_rows:
            return {"updated": 0, "closed": 0}

        updated = 0
        closed = 0
        today = date.today()

        for row in watch_rows:
            try:
                current_price = self._fetch_current_price(row.code)
                if current_price is None:
                    continue

                entry_price = row.price_at_screen
                if not entry_price or entry_price <= 0:
                    continue

                return_pct = round((current_price - entry_price) / entry_price * 100, 2)
                days_held = (today - row.screen_date).days

                max_return_pct = row.max_return_pct
                if max_return_pct is None or return_pct > max_return_pct:
                    max_return_pct = return_pct

                drawdown_from_peak = 0.0
                if max_return_pct and max_return_pct > 0:
                    drawdown_from_peak = round(return_pct - max_return_pct, 2)

                max_drawdown_pct = row.max_drawdown_pct
                if max_drawdown_pct is None or drawdown_from_peak < max_drawdown_pct:
                    max_drawdown_pct = drawdown_from_peak

                should_close = False
                exit_reason = None

                stop_loss_pct, take_profit_pct = self._compute_adaptive_stops(row.code, entry_price)

                if return_pct <= stop_loss_pct:
                    should_close = True
                    exit_reason = 'stop_loss'
                elif return_pct >= take_profit_pct:
                    should_close = True
                    exit_reason = 'take_profit'
                elif days_held >= 30:
                    should_close = True
                    exit_reason = 'window_expired'

                update_data: Dict[str, Any] = {
                    'days_held': days_held,
                    'return_pct': return_pct,
                    'max_return_pct': max_return_pct,
                    'max_drawdown_pct': max_drawdown_pct,
                }

                if should_close:
                    update_data['status'] = 'closed'
                    update_data['exit_price'] = current_price
                    update_data['exit_date'] = today
                    update_data['exit_reason'] = exit_reason
                    closed += 1

                self.repo.update_tracking(
                    screen_date=row.screen_date,
                    code=row.code,
                    strategy_tag=row.strategy_tag,
                    **update_data,
                )
                updated += 1

            except Exception as exc:
                logger.warning("[Screener] 更新追踪失败 %s: %s", row.code, exc)

        return {"updated": updated, "closed": closed}

    def apply_backtest_feedback(self, strategy_tag: Optional[str] = None) -> Dict[str, Any]:
        """Cross-reference screener results with backtest outcomes.

        Marks screener results as backtest_verified and records the outcome.
        """
        watch_rows = self.repo.get_watch_list(
            status='watch', days=60, strategy_tag=strategy_tag,
        )
        closed_rows = self._get_closed_results(strategy_tag=strategy_tag)
        all_rows = watch_rows + closed_rows

        verified = 0
        for row in all_rows:
            if row.backtest_verified:
                continue

            backtest_outcome = self._lookup_backtest_outcome(row.code, row.screen_date)
            if backtest_outcome:
                self.repo.update_tracking(
                    screen_date=row.screen_date,
                    code=row.code,
                    strategy_tag=row.strategy_tag,
                    backtest_verified=True,
                    backtest_outcome=backtest_outcome,
                )
                verified += 1

        return {"verified": verified, "total_checked": len(all_rows)}

    def get_performance_summary(
        self,
        strategy_tag: Optional[str] = None,
        days: int = 90,
    ) -> Dict[str, Any]:
        """Get aggregated performance stats for the screener."""
        return self.repo.get_performance_summary(strategy_tag=strategy_tag, days=days)

    def get_screening_history(
        self,
        strategy_tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get all screening dates and counts."""
        dates = self.repo.get_date_range(strategy_tag=strategy_tag)
        return {
            "total_dates": len(dates),
            "dates": [d.isoformat() for d in dates],
        }

    def _get_closed_results(
        self,
        strategy_tag: Optional[str] = None,
    ) -> List[ScreenerResult]:
        """Get closed screener results."""
        cutoff = date.today() - timedelta(days=60)
        with self.db.get_session() as session:
            from sqlalchemy import and_, select
            conditions = [
                ScreenerResult.status == 'closed',
                ScreenerResult.screen_date >= cutoff,
            ]
            if strategy_tag:
                conditions.append(ScreenerResult.strategy_tag == strategy_tag)
            rows = session.execute(
                select(ScreenerResult).where(
                    and_(*conditions)
                ).order_by(ScreenerResult.screen_date.desc())
            ).scalars().all()
            return list(rows)

    def _fetch_current_price(self, code: str) -> Optional[float]:
        """Fetch current price for a stock using the data provider layer."""
        try:
            from data_provider.factory import DataProviderFactory
            factory = DataProviderFactory()
            quote = factory.get_realtime_quote(code)
            if quote and quote.price:
                return float(quote.price)
        except Exception as exc:
            logger.debug("[Screener] 获取 %s 当前价格失败: %s", code, exc)
        return None

    def _lookup_backtest_outcome(self, code: str, screen_date: date) -> Optional[str]:
        """Look up backtest outcome for a stock from the backtest_results table."""
        try:
            from src.storage import BacktestResult
            from sqlalchemy import and_, select
            with self.db.get_session() as session:
                row = session.execute(
                    select(BacktestResult).where(
                        and_(
                            BacktestResult.code == code,
                            BacktestResult.analysis_date >= screen_date - timedelta(days=3),
                            BacktestResult.analysis_date <= screen_date + timedelta(days=3),
                            BacktestResult.eval_status == 'completed',
                        )
                    ).order_by(BacktestResult.analysis_date.desc())
                ).scalar_one_or_none()

                if row:
                    return row.outcome
        except Exception as exc:
            logger.debug("[Screener] 查询回测结果失败 %s: %s", code, exc)
        return None

    @staticmethod
    def _compute_adaptive_stops(code: str, entry_price: float) -> tuple:
        """Compute volatility-adjusted stop loss and take profit percentages.

        Uses 20-day ATR approximation from recent daily history.
        Falls back to -8%/+15% if data unavailable.
        Stop loss = 2 * ATR%, Take profit = 3 * ATR% (1.5:1 reward/risk).
        """
        default_stop = -8.0
        default_tp = 15.0

        try:
            from data_provider.factory import DataProviderFactory
            factory = DataProviderFactory()
            end = date.today()
            start = end - timedelta(days=60)
            df = factory.get_daily_history(code, start_date=start, end_date=end)
            if df is None or len(df) < 15:
                return default_stop, default_tp

            import numpy as np
            close = df["close"].values if "close" in df.columns else None
            high = df["high"].values if "high" in df.columns else None
            low = df["low"].values if "low" in df.columns else None

            if close is None or high is None or low is None or len(close) < 15:
                return default_stop, default_tp

            tr_list = []
            for i in range(1, len(close)):
                tr = max(
                    float(high[i]) - float(low[i]),
                    abs(float(high[i]) - float(close[i - 1])),
                    abs(float(low[i]) - float(close[i - 1])),
                )
                tr_list.append(tr)

            if not tr_list:
                return default_stop, default_tp

            atr = float(np.mean(tr_list[-14:]))
            atr_pct = atr / entry_price * 100 if entry_price > 0 else 2.0

            atr_pct = max(atr_pct, 1.5)
            atr_pct = min(atr_pct, 8.0)

            stop_loss = round(-2.0 * atr_pct, 1)
            take_profit = round(3.0 * atr_pct, 1)

            stop_loss = max(stop_loss, -15.0)
            take_profit = min(take_profit, 30.0)

            return stop_loss, take_profit
        except Exception:
            return default_stop, default_tp

    @staticmethod
    def _result_to_dict(r: ScreenerResult) -> Dict[str, Any]:
        """Convert a ScreenerResult to a plain dict."""
        signals = None
        if r.signals_json:
            try:
                signals = json.loads(r.signals_json)
            except (TypeError, ValueError):
                signals = None

        strategy_scores = None
        market_regime = None
        market_regime_label = None
        quality_tier = None
        quality_tier_label = None
        data_fetch_failed = None
        data_fetch_reason = None

        if signals and isinstance(signals, dict):
            strategy_scores = signals.get("strategy_scores")
            market_regime = signals.get("market_regime")
            market_regime_label = signals.get("market_regime_label")
            quality_tier = signals.get("quality_tier")
            quality_tier_label = signals.get("quality_tier_label")
            data_fetch_failed = signals.get("data_fetch_failed")
            data_fetch_reason = signals.get("data_fetch_reason")

        return {
            "id": r.id,
            "screen_date": r.screen_date.isoformat() if r.screen_date else None,
            "code": r.code,
            "name": r.name,
            "score": r.score,
            "rank": r.rank,
            "strategy_tag": r.strategy_tag,
            "price_at_screen": r.price_at_screen,
            "market_cap": r.market_cap,
            "turnover_rate": r.turnover_rate,
            "pe_ratio": r.pe_ratio,
            "pb_ratio": r.pb_ratio,
            "signals": signals,
            "strategy_scores": strategy_scores,
            "market_regime": market_regime,
            "market_regime_label": market_regime_label,
            "quality_tier": quality_tier,
            "quality_tier_label": quality_tier_label,
            "data_fetch_failed": data_fetch_failed,
            "data_fetch_reason": data_fetch_reason,
            "status": r.status,
            "days_held": r.days_held,
            "return_pct": r.return_pct,
            "max_return_pct": r.max_return_pct,
            "max_drawdown_pct": r.max_drawdown_pct,
            "exit_price": r.exit_price,
            "exit_date": r.exit_date.isoformat() if r.exit_date else None,
            "exit_reason": r.exit_reason,
            "backtest_verified": r.backtest_verified,
            "backtest_outcome": r.backtest_outcome,
        }
