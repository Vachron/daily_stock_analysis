# -*- coding: utf-8 -*-
"""Screener repository — database access for screener results."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, delete, desc, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.storage import DatabaseManager, ScreenerResult

logger = logging.getLogger(__name__)


class ScreenerRepository:
    """DB access layer for screener results."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def save_results_batch(self, results: List[ScreenerResult]) -> int:
        """Save a batch of screener results, upserting on conflict.

        Uses SQLite INSERT ... ON CONFLICT DO UPDATE to avoid N+1 queries.
        The unique constraint is (screen_date, code, strategy_tag).
        Before inserting, deletes stale watch-status records for the same
        date+strategy_tag that are no longer in the new result set.
        Inserts are batched to stay under SQLite's variable limit (~999).
        """
        _BATCH_SIZE = 50

        if not results:
            return 0

        mappings = []
        new_codes = set()
        screen_date = results[0].screen_date
        strategy_tag = results[0].strategy_tag
        for r in results:
            new_codes.add(r.code)
            mappings.append({
                'screen_date': r.screen_date,
                'code': r.code,
                'name': r.name,
                'score': r.score,
                'rank': r.rank,
                'strategy_tag': r.strategy_tag,
                'price_at_screen': r.price_at_screen,
                'market_cap': r.market_cap,
                'turnover_rate': r.turnover_rate,
                'pe_ratio': r.pe_ratio,
                'pb_ratio': r.pb_ratio,
                'signals_json': r.signals_json,
                'status': r.status or 'watch',
            })

        with self.db.get_session() as session:
            try:
                if new_codes and screen_date and strategy_tag:
                    existing = session.execute(
                        select(ScreenerResult.code).where(
                            and_(
                                ScreenerResult.screen_date == screen_date,
                                ScreenerResult.strategy_tag == strategy_tag,
                                ScreenerResult.status == 'watch',
                            )
                        )
                    ).scalars().all()
                    stale_codes = sorted(set(existing) - new_codes)
                    all_stale = 0
                    for i in range(0, len(stale_codes), _BATCH_SIZE):
                        chunk = stale_codes[i:i + _BATCH_SIZE]
                        result = session.execute(
                            delete(ScreenerResult).where(
                                and_(
                                    ScreenerResult.screen_date == screen_date,
                                    ScreenerResult.strategy_tag == strategy_tag,
                                    ScreenerResult.status == 'watch',
                                    ScreenerResult.code.in_(chunk),
                                )
                            )
                        )
                        all_stale += result.rowcount
                    if all_stale > 0:
                        logger.debug("Removed %d stale watch records for %s/%s", all_stale, screen_date, strategy_tag)

                for i in range(0, len(mappings), _BATCH_SIZE):
                    batch = mappings[i:i + _BATCH_SIZE]
                    stmt = sqlite_insert(ScreenerResult).values(batch)
                    excluded = stmt.excluded
                    session.execute(
                        stmt.on_conflict_do_update(
                            index_elements=['screen_date', 'code', 'strategy_tag'],
                            set_={
                                'score': excluded.score,
                                'rank': excluded.rank,
                                'name': func.coalesce(excluded.name, ScreenerResult.name),
                                'price_at_screen': excluded.price_at_screen,
                                'market_cap': excluded.market_cap,
                                'turnover_rate': excluded.turnover_rate,
                                'pe_ratio': excluded.pe_ratio,
                                'pb_ratio': excluded.pb_ratio,
                                'signals_json': excluded.signals_json,
                                'updated_at': datetime.now(),
                            },
                        )
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise

        return len(results)

    def get_results_by_date(
        self,
        screen_date: date,
        strategy_tag: Optional[str] = None,
    ) -> List[ScreenerResult]:
        """Get screener results for a specific date."""
        with self.db.get_session() as session:
            conditions = [ScreenerResult.screen_date == screen_date]
            if strategy_tag:
                conditions.append(ScreenerResult.strategy_tag == strategy_tag)
            rows = session.execute(
                select(ScreenerResult)
                .where(and_(*conditions))
                .order_by(ScreenerResult.rank)
            ).scalars().all()
            return list(rows)

    def get_latest_date(self, strategy_tag: Optional[str] = None) -> Optional[date]:
        """Get the most recent screening date."""
        with self.db.get_session() as session:
            conditions = []
            if strategy_tag:
                conditions.append(ScreenerResult.strategy_tag == strategy_tag)
            query = select(func.max(ScreenerResult.screen_date))
            if conditions:
                query = query.where(and_(*conditions))
            result = session.execute(query).scalar()
            return result

    def get_watch_list(
        self,
        status: str = 'watch',
        days: int = 30,
        strategy_tag: Optional[str] = None,
    ) -> List[ScreenerResult]:
        """Get stocks currently in watch status within recent N days."""
        cutoff = date.today() - timedelta(days=days)
        with self.db.get_session() as session:
            conditions = [
                ScreenerResult.status == status,
                ScreenerResult.screen_date >= cutoff,
            ]
            if strategy_tag:
                conditions.append(ScreenerResult.strategy_tag == strategy_tag)
            rows = session.execute(
                select(ScreenerResult)
                .where(and_(*conditions))
                .order_by(desc(ScreenerResult.screen_date), ScreenerResult.rank)
            ).scalars().all()
            return list(rows)

    def update_tracking(
        self,
        screen_date: date,
        code: str,
        strategy_tag: str,
        **kwargs: Any,
    ) -> bool:
        """Update tracking fields for a screener result."""
        with self.db.get_session() as session:
            row = session.execute(
                select(ScreenerResult).where(
                    and_(
                        ScreenerResult.screen_date == screen_date,
                        ScreenerResult.code == code,
                        ScreenerResult.strategy_tag == strategy_tag,
                    )
                )
            ).scalar_one_or_none()

            if not row:
                return False

            for key, value in kwargs.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            row.updated_at = datetime.now()
            session.commit()
            return True

    def batch_update_tracking(self, updates: List[Dict[str, Any]]) -> int:
        """Batch update tracking fields. Each dict must contain screen_date, code, strategy_tag."""
        updated = 0
        for u in updates:
            keys = {'screen_date', 'code', 'strategy_tag'}
            if not keys.issubset(u.keys()):
                continue
            screen_date = u.pop('screen_date')
            code = u.pop('code')
            strategy_tag = u.pop('strategy_tag')
            if self.update_tracking(screen_date, code, strategy_tag, **u):
                updated += 1
        return updated

    def get_performance_summary(
        self,
        strategy_tag: Optional[str] = None,
        days: int = 90,
    ) -> Dict[str, Any]:
        """Aggregate performance stats across all tracked picks."""
        cutoff = date.today() - timedelta(days=days)
        with self.db.get_session() as session:
            conditions = [
                ScreenerResult.screen_date >= cutoff,
                ScreenerResult.return_pct.isnot(None),
            ]
            if strategy_tag:
                conditions.append(ScreenerResult.strategy_tag == strategy_tag)

            rows = session.execute(
                select(ScreenerResult).where(and_(*conditions))
            ).scalars().all()

            if not rows:
                return {"total": 0}

            returns = [r.return_pct for r in rows if r.return_pct is not None]
            wins = [r for r in returns if r > 0]
            total_count = len(returns)

            return {
                "total": total_count,
                "win_count": len(wins),
                "loss_count": total_count - len(wins),
                "win_rate": round(len(wins) / total_count * 100, 2) if total_count else 0,
                "avg_return": round(sum(returns) / total_count, 2) if total_count else 0,
                "max_return": round(max(returns), 2) if returns else 0,
                "min_return": round(min(returns), 2) if returns else 0,
            }

    def get_date_range(self, strategy_tag: Optional[str] = None) -> List[date]:
        """Get all distinct screening dates."""
        with self.db.get_session() as session:
            conditions = []
            if strategy_tag:
                conditions.append(ScreenerResult.strategy_tag == strategy_tag)
            query = select(ScreenerResult.screen_date).distinct()
            if conditions:
                query = query.where(and_(*conditions))
            return sorted(session.execute(query).scalars().all(), reverse=True)

    def delete_by_date(self, screen_date: date, strategy_tag: Optional[str] = None) -> int:
        """Delete screener results for a specific date."""
        with self.db.get_session() as session:
            conditions = [ScreenerResult.screen_date == screen_date]
            if strategy_tag:
                conditions.append(ScreenerResult.strategy_tag == strategy_tag)
            result = session.execute(
                delete(ScreenerResult).where(and_(*conditions))
            )
            session.commit()
            return result.rowcount
