# -*- coding: utf-8 -*-
"""Stock pool initializer — build, tag, and maintain the candidate pool.

Workflow:
1. Fetch full-market quotes (akshare / efinance / tushare fallback)
2. Apply basic filters (market cap, PE, PB, ST exclusion, etc.)
3. Classify each stock: board type, industry, quality tier
4. Tag stocks with labels for quick daily scanning
5. Persist to stock_pool_entries table
6. Track progress with ETA for the UI progress bar
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.storage import DatabaseManager, StockPoolEntry, StockPoolMeta

logger = logging.getLogger(__name__)

POOL_EXPIRE_DAYS = 45

BOARD_MAP = {
    "6": "主板",
    "0": "主板",
    "3": "创业板",
    "68": "科创板",
    "8": "北交所",
    "4": "北交所",
}

INDUSTRY_KEYWORDS: Dict[str, List[str]] = {
    "半导体": ["半导体", "芯片", "集成电路", "封测", "光刻"],
    "新能源": ["锂电", "光伏", "风电", "储能", "新能源", "充电桩", "氢能"],
    "人工智能": ["AI", "人工智能", "大模型", "算力", "GPU", "智能驾驶", "机器人"],
    "医药生物": ["医药", "生物", "创新药", "CRO", "医疗器械", "中药", "疫苗"],
    "消费": ["白酒", "食品", "饮料", "家电", "零售", "化妆品", "旅游"],
    "金融": ["银行", "证券", "保险", "信托", "期货"],
    "房地产": ["房地产", "物业", "建材", "装饰"],
    "军工": ["军工", "航天", "航空", "兵器", "船舶", "国防"],
    "汽车": ["汽车", "整车", "零部件", "新能源车", "智能驾驶"],
    "TMT": ["软件", "互联网", "通信", "传媒", "游戏", "云计算", "大数据"],
    "周期": ["钢铁", "煤炭", "有色", "化工", "水泥", "石油"],
    "公用事业": ["电力", "水务", "燃气", "环保"],
}


@dataclass
class PoolInitProgress:
    total: int = 0
    processed: int = 0
    filtered: int = 0
    tagged: int = 0
    excluded: int = 0
    progress_pct: float = 0.0
    eta_seconds: float = 0.0
    status: str = "pending"
    error_message: str = ""
    pool_version: str = ""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    expires_at: Optional[date] = None


class StockPoolInitializer:
    """Build and maintain the stock candidate pool with tagging."""

    _instance: Optional["StockPoolInitializer"] = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(cls, db_manager: Optional[DatabaseManager] = None) -> "StockPoolInitializer":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(db_manager=db_manager)
            return cls._instance

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()
        self._data_factory = None
        self._progress = PoolInitProgress()
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._active_version: Optional[str] = None
        self._last_fetch_errors: List[str] = []

    def get_progress(self) -> PoolInitProgress:
        with self._lock:
            return PoolInitProgress(**self._progress.__dict__)

    def cancel(self) -> bool:
        self._cancel_event.set()
        return True

    def start_init(self, expire_days: int = POOL_EXPIRE_DAYS) -> str:
        """Start pool initialization in a background thread.

        Returns the pool_version immediately so the caller can poll progress.
        """
        with self._lock:
            if self._progress.status == "running":
                return self._active_version or ""

        self._cancel_event.clear()
        version = datetime.now().strftime("v%Y%m%d_%H%M%S")

        with self._lock:
            self._active_version = version
            self._progress = PoolInitProgress(
                pool_version=version,
                status="running",
                started_at=datetime.now(),
                expires_at=date.today() + timedelta(days=expire_days),
            )

        meta = StockPoolMeta(
            pool_version=version,
            status="running",
            expires_at=date.today() + timedelta(days=expire_days),
            started_at=datetime.now(),
        )
        with self.db.session_scope() as session:
            session.add(meta)
            session.commit()

        def _safe_run_init(ver: str, exp_days: int) -> None:
            try:
                self._run_init(ver, exp_days)
            except Exception as e:
                logger.error("[PoolInit] 后台线程未捕获异常: %s", e, exc_info=True)
                try:
                    self._finish_with_error(ver, f"线程异常: {e}")
                except Exception:
                    logger.error("[PoolInit] 状态更新也失败，线程静默退出", exc_info=True)

        t = threading.Thread(target=_safe_run_init, args=(version, expire_days), daemon=True)
        t.start()

        return version

    def _run_init(self, version: str, expire_days: int) -> None:
        """Background worker: full-market scan → filter → tag → persist."""
        try:
            self._update_progress(status="fetching_quotes")
            raw_df = self._fetch_full_market_quotes()
            if raw_df is None or raw_df.empty:
                detail = "; ".join(self._last_fetch_errors) if self._last_fetch_errors else "未知原因"
                self._finish_with_error(version, f"无法获取全市场行情数据: {detail}")
                return

            total = len(raw_df)
            self._update_progress(total=total)

            self._update_progress(status="filtering")
            filtered = self._apply_basic_filters(raw_df)
            excluded_count = total - len(filtered)
            self._update_progress(filtered=len(filtered), excluded=excluded_count)

            if filtered.empty:
                self._finish_with_error(version, "过滤后无可用股票")
                return

            self._update_progress(status="tagging")
            entries = self._classify_and_tag(filtered, version)

            self._update_progress(status="persisting")
            self._persist_entries(version, entries)

            with self._lock:
                p = self._progress
                p.status = "completed"
                p.finished_at = datetime.now()
                p.progress_pct = 100.0
                p.eta_seconds = 0.0
                p.tagged = len([e for e in entries if not e.get("is_excluded")])
                p.excluded = len([e for e in entries if e.get("is_excluded")])

            with self.db.session_scope() as session:
                meta = session.query(StockPoolMeta).filter_by(pool_version=version).first()
                if meta:
                    meta.status = "completed"
                    meta.total_stocks = p.total
                    meta.filtered_stocks = p.filtered
                    meta.tagged_stocks = p.tagged
                    meta.excluded_stocks = p.excluded
                    meta.progress_pct = 100.0
                    meta.eta_seconds = 0.0
                    meta.finished_at = datetime.now()
                    session.commit()

            logger.info(
                "[PoolInit] 初始化完成: version=%s, total=%d, filtered=%d, tagged=%d, excluded=%d",
                version, p.total, p.filtered, p.tagged, p.excluded,
            )

        except Exception as exc:
            logger.error("[PoolInit] 初始化失败: %s", exc, exc_info=True)
            self._finish_with_error(version, str(exc))

    def _finish_with_error(self, version: str, message: str) -> None:
        with self._lock:
            self._progress.status = "failed"
            self._progress.error_message = message
            self._progress.finished_at = datetime.now()

        with self.db.session_scope() as session:
            meta = session.query(StockPoolMeta).filter_by(pool_version=version).first()
            if meta:
                meta.status = "failed"
                meta.error_message = message
                meta.finished_at = datetime.now()
                session.commit()

    def _update_progress(self, **kwargs: Any) -> None:
        with self._lock:
            for k, v in kwargs.items():
                setattr(self._progress, k, v)
            p = self._progress
            if p.total > 0:
                p.progress_pct = round(p.processed / p.total * 100, 1)
                if p.processed > 0 and p.started_at:
                    elapsed = (datetime.now() - p.started_at).total_seconds()
                    rate = p.processed / elapsed
                    remaining = (p.total - p.processed) / rate if rate > 0 else 0
                    p.eta_seconds = round(remaining, 0)

    def _fetch_full_market_quotes(self) -> Optional[pd.DataFrame]:
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

        source_errors: List[str] = []

        try:
            import akshare as ak
            logger.info("[PoolInit] 调用 ak.stock_zh_a_spot_em() 获取全市场行情...")
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(ak.stock_zh_a_spot_em)
                try:
                    df = future.result(timeout=60)
                except FuturesTimeout:
                    raise TimeoutError("akshare 调用超时(60s)")
            if df is not None and not df.empty:
                logger.info("[PoolInit] akshare 获取成功: %d 只股票", len(df))
                return df
        except Exception as e:
            err_msg = f"akshare: {e}"
            source_errors.append(err_msg)
            logger.warning("[PoolInit] akshare 获取失败: %s, 尝试 efinance...", e)

        try:
            import efinance as ef
            logger.info("[PoolInit] 调用 ef.stock.get_realtime_quotes()...")
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(ef.stock.get_realtime_quotes)
                try:
                    df = future.result(timeout=60)
                except FuturesTimeout:
                    raise TimeoutError("efinance 调用超时(60s)")
            if df is not None and not df.empty:
                logger.info("[PoolInit] efinance 获取成功: %d 只股票", len(df))
                return df
        except Exception as e:
            err_msg = f"efinance: {e}"
            source_errors.append(err_msg)
            logger.warning("[PoolInit] efinance 也获取失败: %s, 尝试 tushare...", e)

        tushare_df = self._fetch_last_trading_day_quotes()
        if tushare_df is None:
            source_errors.append("tushare: 获取失败或不可用")
            self._last_fetch_errors = source_errors
        else:
            self._last_fetch_errors = []
        return tushare_df

    def _fetch_last_trading_day_quotes(self) -> Optional[pd.DataFrame]:
        try:
            from data_provider.tushare_fetcher import TushareFetcher
            fetcher = TushareFetcher()
            if not fetcher.is_available():
                return None

            trade_dates = fetcher._get_trade_dates()
            if not trade_dates:
                return None

            last_date = trade_dates[0]
            logger.info("[PoolInit] 使用 tushare daily 获取最近交易日(%s)...", last_date)

            df = fetcher._call_api_with_rate_limit("daily", start_date=last_date, end_date=last_date)
            if df is None or df.empty:
                return None

            stock_list = fetcher.get_stock_list()
            name_map: Dict[str, str] = {}
            if stock_list is not None and not stock_list.empty:
                for _, row in stock_list.iterrows():
                    name_map[str(row['code'])] = str(row['name'])

            df = df.copy()
            df['code'] = df['ts_code'].astype(str).str.split('.').str[0]
            df['名称'] = df['code'].map(name_map).fillna('')
            df['收盘价'] = pd.to_numeric(df['close'], errors='coerce')
            df['涨跌幅'] = pd.to_numeric(df['pct_chg'], errors='coerce')
            df['总市值'] = pd.to_numeric(df.get('amount', 0), errors='coerce')
            df['换手率'] = 0.0
            df['市盈率-动态'] = 0.0
            df['市净率'] = 0.0

            try:
                df_daily_basic = fetcher._call_api_with_rate_limit(
                    "daily_basic",
                    trade_date=last_date,
                    fields='ts_code,turnover_rate,pe,pb,total_mv,circ_mv',
                )
                if df_daily_basic is not None and not df_daily_basic.empty:
                    df_daily_basic = df_daily_basic.copy()
                    df_daily_basic['code'] = df_daily_basic['ts_code'].astype(str).str.split('.').str[0]
                    basic_map = df_daily_basic.set_index('code')
                    df['换手率'] = df['code'].map(basic_map['turnover_rate']).fillna(0)
                    df['市盈率-动态'] = df['code'].map(basic_map['pe']).fillna(0)
                    df['市净率'] = df['code'].map(basic_map['pb']).fillna(0)
                    df['总市值'] = df['code'].map(basic_map['total_mv']).fillna(0) * 1e4
            except Exception as e:
                logger.warning("[PoolInit] tushare daily_basic 获取失败(降级为零值): %s", e)

            keep_cols = ['code', '名称', '收盘价', '涨跌幅', '换手率', '市盈率-动态', '市净率', '总市值']
            existing = [c for c in keep_cols if c in df.columns]
            result = df[existing].copy()
            result = result.dropna(subset=['收盘价'])
            result = result[result['code'].str.match(r'^[03689]\d{5}$')]
            return result

        except Exception as e:
            logger.error("[PoolInit] tushare 获取失败: %s", e)
            return None

    def _detect_column(self, df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        for c in candidates:
            if c in df.columns:
                return c
        return None

    def _apply_basic_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        code_col = self._detect_column(result, ['代码', '股票代码', 'code'])
        name_col = self._detect_column(result, ['名称', '股票名称', 'name'])
        price_col = self._detect_column(result, ['最新价', '收盘价', 'price', 'close'])
        market_cap_col = self._detect_column(result, ['总市值', 'market_cap'])
        turnover_col = self._detect_column(result, ['换手率', 'turnover_rate'])
        pe_col = self._detect_column(result, ['市盈率-动态', 'pe_ratio', '市盈率'])
        pb_col = self._detect_column(result, ['市净率', 'pb_ratio'])

        if code_col is None:
            return pd.DataFrame()

        result['_code'] = result[code_col].astype(str).str.strip()
        result['_name'] = result[name_col].astype(str).str.strip() if name_col else ''
        result = result[result['_code'].str.match(r'^[03689]\d{5}$')]

        if name_col:
            st_kw = ("ST", "*ST", "S*ST", "SST")
            mask = ~result['_name'].apply(lambda n: any(k in n for k in st_kw))
            result = result[mask]

        if price_col:
            result['_price'] = pd.to_numeric(result[price_col], errors='coerce')
            result = result[(result['_price'] >= 2.0) & (result['_price'] <= 200.0)]

        if market_cap_col:
            result['_market_cap'] = pd.to_numeric(result[market_cap_col], errors='coerce')
            result = result[(result['_market_cap'] >= 20e8) & (result['_market_cap'] <= 8000e8)]

        if turnover_col:
            result['_turnover_rate'] = pd.to_numeric(result[turnover_col], errors='coerce')
            result = result[(result['_turnover_rate'] >= 0.5)]

        if pe_col:
            result['_pe_ratio'] = pd.to_numeric(result[pe_col], errors='coerce')
            result = result[(result['_pe_ratio'] >= 0) & (result['_pe_ratio'] <= 300)]

        if pb_col:
            result['_pb_ratio'] = pd.to_numeric(result[pb_col], errors='coerce')
            result = result[(result['_pb_ratio'] >= 0) & (result['_pb_ratio'] <= 30)]

        result = result.dropna(subset=['_price'] if '_price' in result.columns else ['_code'])
        return result

    def _classify_board(self, code: str) -> str:
        if code.startswith("68"):
            return "科创板"
        if code.startswith("8") or code.startswith("4"):
            return "北交所"
        if code.startswith("3"):
            return "创业板"
        if code.startswith("6") or code.startswith("0"):
            return "主板"
        return "其他"

    def _classify_industry(self, name: str) -> str:
        for industry, keywords in INDUSTRY_KEYWORDS.items():
            for kw in keywords:
                if kw in name:
                    return industry
        return "其他"

    def _classify_quality(self, pe: float, pb: float, market_cap: float, turnover: float) -> str:
        score = 0
        if 50e8 <= market_cap <= 2000e8:
            score += 2
        elif 20e8 <= market_cap < 50e8:
            score += 1

        if 5 <= pe <= 40:
            score += 2
        elif 40 < pe <= 80:
            score += 1

        if 0.5 <= pb <= 5:
            score += 2
        elif 5 < pb <= 10:
            score += 1

        if turnover >= 2:
            score += 1

        if score >= 5:
            return "premium"
        if score >= 3:
            return "standard"
        return "marginal"

    def _compute_base_score(self, turnover: float, pct_chg: float, pe: float, pb: float, market_cap: float) -> float:
        score = 0.0
        if turnover >= 3:
            score += 20
        elif turnover >= 1.5:
            score += 10

        if -3 <= pct_chg <= 5:
            score += 15
        elif pct_chg > 5:
            score += 5

        if 5 <= pe <= 30:
            score += 20
        elif 30 < pe <= 60:
            score += 10

        if 0.5 <= pb <= 3:
            score += 15
        elif 3 < pb <= 6:
            score += 8

        if 100e8 <= market_cap <= 1000e8:
            score += 15
        elif 50e8 <= market_cap < 100e8:
            score += 8

        return min(score, 100.0)

    def _classify_and_tag(self, df: pd.DataFrame, version: str) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        total = len(df)

        for idx, (_, row) in enumerate(df.iterrows()):
            if self._cancel_event.is_set():
                logger.info("[PoolInit] 收到取消信号，停止分类")
                break

            code = str(row.get('_code', ''))
            name = str(row.get('_name', ''))
            price = float(row.get('_price', 0) or 0)
            market_cap = float(row.get('_market_cap', 0) or 0)
            turnover = float(row.get('_turnover_rate', 0) or 0)
            pe = float(row.get('_pe_ratio', 0) or 0)
            pb = float(row.get('_pb_ratio', 0) or 0)
            pct_chg = float(row.get('_pct_chg', 0) or 0)

            board = self._classify_board(code)
            industry = self._classify_industry(name)
            quality = self._classify_quality(pe, pb, market_cap, turnover)
            base_score = self._compute_base_score(turnover, pct_chg, pe, pb, market_cap)

            is_excluded = False
            exclude_reason = ""
            tags_list: List[str] = [board, industry, quality]

            if quality == "marginal" and market_cap < 30e8:
                is_excluded = True
                exclude_reason = "小盘低质"
            elif pe <= 0 and pb <= 0:
                is_excluded = True
                exclude_reason = "财务异常"
            elif turnover < 0.5:
                is_excluded = True
                exclude_reason = "流动性不足"

            if base_score >= 60:
                tags_list.append("高分基线")
            if turnover >= 5:
                tags_list.append("活跃换手")
            if 100e8 <= market_cap <= 500e8:
                tags_list.append("中盘成长")
            elif market_cap >= 500e8:
                tags_list.append("大盘蓝筹")

            entries.append({
                "pool_version": version,
                "code": code,
                "name": name,
                "board": board,
                "industry": industry,
                "quality_tier": quality,
                "base_score": round(base_score, 2),
                "tags": json.dumps(tags_list, ensure_ascii=False),
                "is_excluded": is_excluded,
                "exclude_reason": exclude_reason,
                "market_cap": market_cap,
                "pe_ratio": pe,
                "pb_ratio": pb,
                "price": price,
                "turnover_rate": turnover,
            })

            processed = idx + 1
            if processed % 100 == 0 or processed == total:
                self._update_progress(processed=processed)

        return entries

    def _persist_entries(self, version: str, entries: List[Dict[str, Any]]) -> None:
        batch_size = 200
        with self.db.session_scope() as session:
            for i in range(0, len(entries), batch_size):
                batch = entries[i:i + batch_size]
                for e in batch:
                    existing = session.query(StockPoolEntry).filter_by(
                        pool_version=version, code=e["code"],
                    ).first()
                    if existing:
                        for k, v in e.items():
                            setattr(existing, k, v)
                    else:
                        session.add(StockPoolEntry(**e))
                session.commit()

    def get_pool_status(self) -> Dict[str, Any]:
        """Return the latest pool status for the UI."""
        with self.db.session_scope() as session:
            meta = session.query(StockPoolMeta).order_by(
                StockPoolMeta.created_at.desc(),
            ).first()

            if meta is None:
                return {
                    "has_pool": False,
                    "status": "none",
                    "pool_version": None,
                    "expires_at": None,
                    "days_remaining": None,
                    "total_stocks": 0,
                    "filtered_stocks": 0,
                    "tagged_stocks": 0,
                    "excluded_stocks": 0,
                    "progress_pct": 0.0,
                    "eta_seconds": 0.0,
                    "error_message": None,
                }

            days_remaining = None
            if meta.expires_at:
                days_remaining = (meta.expires_at - date.today()).days

            return {
                "has_pool": True,
                "status": meta.status,
                "pool_version": meta.pool_version,
                "expires_at": meta.expires_at.isoformat() if meta.expires_at else None,
                "days_remaining": days_remaining,
                "total_stocks": meta.total_stocks or 0,
                "filtered_stocks": meta.filtered_stocks or 0,
                "tagged_stocks": meta.tagged_stocks or 0,
                "excluded_stocks": meta.excluded_stocks or 0,
                "progress_pct": meta.progress_pct or 0.0,
                "eta_seconds": meta.eta_seconds or 0.0,
                "error_message": meta.error_message,
            }

    def get_pool_summary(self, version: Optional[str] = None) -> Dict[str, Any]:
        """Return pool composition summary: board/industry/quality distributions."""
        with self.db.session_scope() as session:
            if version is None:
                meta = session.query(StockPoolMeta).order_by(
                    StockPoolMeta.created_at.desc(),
                ).first()
                if meta is None:
                    return {"boards": {}, "industries": {}, "qualities": {}, "total_active": 0}
                version = meta.pool_version

            active_entries = session.query(StockPoolEntry).filter_by(
                pool_version=version, is_excluded=False,
            ).all()

            boards: Dict[str, int] = {}
            industries: Dict[str, int] = {}
            qualities: Dict[str, int] = {}

            for e in active_entries:
                boards[e.board] = boards.get(e.board, 0) + 1
                industries[e.industry] = industries.get(e.industry, 0) + 1
                qualities[e.quality_tier] = qualities.get(e.quality_tier, 0) + 1

            sorted_industries = dict(sorted(industries.items(), key=lambda x: -x[1])[:15])

            return {
                "boards": boards,
                "industries": sorted_industries,
                "qualities": qualities,
                "total_active": len(active_entries),
            }

    def get_pool_codes(
        self,
        version: Optional[str] = None,
        boards: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
        qualities: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        min_base_score: float = 0.0,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Query pool entries by tags for quick daily scanning."""
        with self.db.session_scope() as session:
            if version is None:
                meta = session.query(StockPoolMeta).order_by(
                    StockPoolMeta.created_at.desc(),
                ).first()
                if meta is None:
                    return []
                version = meta.pool_version

            q = session.query(StockPoolEntry).filter_by(
                pool_version=version, is_excluded=False,
            )

            if boards:
                q = q.filter(StockPoolEntry.board.in_(boards))
            if industries:
                q = q.filter(StockPoolEntry.industry.in_(industries))
            if qualities:
                q = q.filter(StockPoolEntry.quality_tier.in_(qualities))
            if min_base_score > 0:
                q = q.filter(StockPoolEntry.base_score >= min_base_score)

            q = q.order_by(StockPoolEntry.base_score.desc())
            entries = q.limit(limit).all()

            results = []
            for e in entries:
                entry_tags = json.loads(e.tags) if e.tags else []
                if tags:
                    if not any(t in entry_tags for t in tags):
                        continue

                results.append({
                    "code": e.code,
                    "name": e.name,
                    "board": e.board,
                    "industry": e.industry,
                    "quality_tier": e.quality_tier,
                    "base_score": e.base_score,
                    "tags": entry_tags,
                    "market_cap": e.market_cap,
                    "pe_ratio": e.pe_ratio,
                    "pb_ratio": e.pb_ratio,
                    "price": e.price,
                    "turnover_rate": e.turnover_rate,
                })

            return results
