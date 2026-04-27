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
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.storage import DatabaseManager, StockPoolEntry, StockPoolMeta

logger = logging.getLogger(__name__)

from src.core.screener_progress import ScreenerStep

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

    def _emit_progress(self, **kwargs: Any) -> None:
        from src.core.screener_progress import get_screener_broadcaster
        broadcaster = get_screener_broadcaster()
        broadcaster.update_pool_progress(**kwargs)

    def _run_init(self, version: str, expire_days: int) -> None:
        """Background worker: full-market scan → filter → tag → persist."""
        try:
            self._emit_progress(
                status="running",
                progress_pct=0,
                message="正在获取全市场行情数据...",
                stage="fetching_quotes",
                steps=[
                    ScreenerStep(label="获取行情数据", status="running", detail=""),
                    ScreenerStep(label="基础过滤", status="pending", detail=""),
                    ScreenerStep(label="分类打标签", status="pending", detail=""),
                    ScreenerStep(label="持久化存储", status="pending", detail=""),
                ],
            )
            self._update_progress(status="fetching_quotes")
            raw_df = self._fetch_full_market_quotes()
            if raw_df is None or raw_df.empty:
                detail = "; ".join(self._last_fetch_errors) if self._last_fetch_errors else "未知原因"
                self._finish_with_error(version, f"无法获取全市场行情数据: {detail}")
                self._emit_progress(
                    status="failed",
                    progress_pct=0,
                    message=f"获取行情数据失败: {detail}",
                    stage="fetching_quotes",
                )
                return

            total = len(raw_df)
            self._update_progress(total=total)
            self._emit_progress(
                status="running",
                progress_pct=10,
                message=f"获取到 {total} 只股票行情数据",
                stage="fetching_quotes",
                steps=[
                    ScreenerStep(label="获取行情数据", status="completed", detail=f"获取 {total} 只"),
                    ScreenerStep(label="基础过滤", status="running", detail=""),
                    ScreenerStep(label="分类打标签", status="pending", detail=""),
                    ScreenerStep(label="持久化存储", status="pending", detail=""),
                ],
                extra={"total": total},
            )

            self._update_progress(status="filtering")
            filtered = self._apply_basic_filters(raw_df)
            excluded_count = total - len(filtered)
            self._update_progress(filtered=len(filtered), excluded=excluded_count)

            if filtered.empty:
                self._finish_with_error(version, "过滤后无可用股票")
                self._emit_progress(
                    status="failed",
                    progress_pct=20,
                    message="过滤后无可用股票",
                    stage="filtering",
                )
                return

            self._emit_progress(
                status="running",
                progress_pct=25,
                message=f"过滤完成: {len(filtered)} 只通过, {excluded_count} 只排除",
                stage="filtering",
                steps=[
                    ScreenerStep(label="获取行情数据", status="completed", detail=f"获取 {total} 只"),
                    ScreenerStep(label="基础过滤", status="completed", detail=f"通过 {len(filtered)} 只, 排除 {excluded_count} 只"),
                    ScreenerStep(label="分类打标签", status="running", detail=""),
                    ScreenerStep(label="持久化存储", status="pending", detail=""),
                ],
                extra={"total": total, "filtered": len(filtered), "excluded": excluded_count},
            )

            self._update_progress(status="tagging")
            entries = self._classify_and_tag(filtered, version)

            tagged_count = len([e for e in entries if not e.get("is_excluded")])
            excluded_tag_count = len([e for e in entries if e.get("is_excluded")])
            self._emit_progress(
                status="running",
                progress_pct=75,
                message=f"分类打标完成: {tagged_count} 只活跃, {excluded_tag_count} 只排除",
                stage="tagging",
                steps=[
                    ScreenerStep(label="获取行情数据", status="completed", detail=f"获取 {total} 只"),
                    ScreenerStep(label="基础过滤", status="completed", detail=f"通过 {len(filtered)} 只"),
                    ScreenerStep(label="分类打标签", status="completed", detail=f"活跃 {tagged_count} 只, 排除 {excluded_tag_count} 只"),
                    ScreenerStep(label="持久化存储", status="running", detail=""),
                ],
                extra={"total": total, "filtered": len(filtered), "tagged": tagged_count, "excluded": excluded_tag_count},
            )

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

            self._emit_progress(
                status="completed",
                progress_pct=100,
                message=f"初始化完成: {p.tagged} 只活跃股票",
                stage="completed",
                steps=[
                    ScreenerStep(label="获取行情数据", status="completed", detail=f"获取 {total} 只"),
                    ScreenerStep(label="基础过滤", status="completed", detail=f"通过 {len(filtered)} 只"),
                    ScreenerStep(label="分类打标签", status="completed", detail=f"活跃 {p.tagged} 只"),
                    ScreenerStep(label="持久化存储", status="completed", detail=f"已保存 {len(entries)} 条"),
                ],
                extra={"total": p.total, "filtered": p.filtered, "tagged": p.tagged, "excluded": p.excluded},
            )

            logger.info(
                "[PoolInit] 初始化完成: version=%s, total=%d, filtered=%d, tagged=%d, excluded=%d",
                version, p.total, p.filtered, p.tagged, p.excluded,
            )

        except Exception as exc:
            logger.error("[PoolInit] 初始化失败: %s", exc, exc_info=True)
            self._finish_with_error(version, str(exc))
            self._emit_progress(
                status="failed",
                progress_pct=0,
                message=f"初始化失败: {str(exc)}",
                stage="failed",
            )

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

        for key in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY'):
            os.environ.pop(key, None)
        os.environ['NO_PROXY'] = '*'
        os.environ['no_proxy'] = '*'

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
                self._save_market_cache(df)
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
                self._save_market_cache(df)
                return df
        except Exception as e:
            err_msg = f"efinance: {e}"
            source_errors.append(err_msg)
            logger.warning("[PoolInit] efinance 也获取失败: %s, 尝试腾讯/新浪...", e)

        tencent_df = self._fetch_tencent_full_market_quotes()
        if tencent_df is not None:
            logger.info("[PoolInit] 腾讯行情获取成功: %d 只股票", len(tencent_df))
            self._save_market_cache(tencent_df)
            self._last_fetch_errors = []
            return tencent_df

        source_errors.append("tencent/sina: 获取失败")

        tushare_df = self._fetch_last_trading_day_quotes()
        if tushare_df is not None:
            logger.info("[PoolInit] tushare 获取成功: %d 只股票", len(tushare_df))
            self._save_market_cache(tushare_df)
            self._last_fetch_errors = []
            return tushare_df

        source_errors.append("tushare: 获取失败或不可用")

        cached_df = self._load_market_cache()
        if cached_df is not None and not cached_df.empty:
            logger.warning("[PoolInit] 所有数据源失败，使用缓存数据: %d 只股票", len(cached_df))
            self._last_fetch_errors = source_errors
            return cached_df

        self._last_fetch_errors = source_errors
        return None

    def _market_cache_path(self) -> str:
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, 'market_quotes.csv')

    def _save_market_cache(self, df: pd.DataFrame) -> None:
        try:
            path = self._market_cache_path()
            df.to_csv(path, index=False, encoding='utf-8-sig')
            logger.info("[PoolInit] 市场行情缓存已保存: %s", path)
        except Exception as e:
            logger.warning("[PoolInit] 保存市场行情缓存失败: %s", e)

    def _load_market_cache(self) -> Optional[pd.DataFrame]:
        try:
            path = self._market_cache_path()
            if not os.path.exists(path):
                return None
            mtime = os.path.getmtime(path)
            age_days = (datetime.now().timestamp() - mtime) / 86400
            if age_days > 7:
                logger.warning("[PoolInit] 市场行情缓存超过 7 天，已过期")
                return None
            df = pd.read_csv(path, encoding='utf-8-sig')
            logger.info("[PoolInit] 加载市场行情缓存: %d 只股票 (缓存时间 %.1f 天前)", len(df), age_days)
            return df
        except Exception as e:
            logger.warning("[PoolInit] 加载市场行情缓存失败: %s", e)
            return None

    def _fetch_tencent_full_market_quotes(self) -> Optional[pd.DataFrame]:
        try:
            import requests as _req

            stock_codes = self._get_all_a_stock_codes()
            if not stock_codes:
                return None

            symbols: List[str] = []
            for c in stock_codes:
                if c.startswith(('6', '9')):
                    symbols.append(f'sh{c}')
                elif c.startswith('8') or c.startswith('4'):
                    symbols.append(f'bj{c}')
                else:
                    symbols.append(f'sz{c}')

            session = _req.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'http://finance.qq.com',
            })
            session.trust_env = False

            batch_size = 800
            all_rows: List[Dict[str, Any]] = []

            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i + batch_size]
                query = ','.join(batch)
                url = f'https://qt.gtimg.cn/q={query}'
                try:
                    resp = session.get(url, timeout=20)
                    resp.encoding = 'gbk'
                    lines = resp.text.strip().split(';')
                    for line in lines:
                        line = line.strip()
                        if not line or '=' not in line:
                            continue
                        val_part = line.split('=', 1)[1].strip('"')
                        if not val_part:
                            continue
                        fields = val_part.split('~')
                        if len(fields) < 35:
                            continue
                        code = fields[2]
                        name = fields[1]
                        price = self._safe_float(fields[3])
                        pre_close = self._safe_float(fields[4])
                        if price is None or price <= 0:
                            continue
                        change_pct = self._safe_float(fields[32])
                        volume = self._safe_int(fields[36]) if len(fields) > 36 else 0
                        amount = self._safe_float(fields[37]) if len(fields) > 37 else 0
                        turnover_rate = self._safe_float(fields[38]) if len(fields) > 38 else 0
                        high = self._safe_float(fields[33]) if len(fields) > 33 else None
                        low = self._safe_float(fields[34]) if len(fields) > 34 else None
                        total_mv_yi = self._safe_float(fields[44]) if len(fields) > 44 else None
                        pe_ratio = self._safe_float(fields[39]) if len(fields) > 39 else None
                        pb_ratio = self._safe_float(fields[46]) if len(fields) > 46 else None

                        all_rows.append({
                            'code': code,
                            '名称': name,
                            '收盘价': price,
                            '涨跌幅': change_pct if change_pct is not None else 0,
                            '换手率': turnover_rate if turnover_rate is not None else 0,
                            '市盈率-动态': pe_ratio if pe_ratio is not None else 0,
                            '市净率': pb_ratio if pb_ratio is not None else 0,
                            '总市值': total_mv_yi * 1e8 if total_mv_yi else 0,
                        })
                except Exception as batch_e:
                    logger.warning("[PoolInit] 腾讯行情批次 %d 获取失败: %s", i // batch_size, batch_e)

            if not all_rows:
                return None

            df = pd.DataFrame(all_rows)
            df = df.dropna(subset=['收盘价'])
            df = df[df['code'].str.match(r'^[03689]\d{5}$')]
            logger.info("[PoolInit] 腾讯行情解析完成: %d 只股票", len(df))
            return df
        except Exception as e:
            logger.warning("[PoolInit] 腾讯全市场行情获取失败: %s", e)
            return None

    def _get_all_a_stock_codes(self) -> List[str]:
        try:
            from data_provider.tushare_fetcher import TushareFetcher
            fetcher = TushareFetcher()
            if not fetcher.is_available():
                return []
            stock_list = fetcher.get_stock_list()
            if stock_list is not None and not stock_list.empty:
                return stock_list['code'].tolist()
        except Exception:
            pass
        return []

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        try:
            v = float(val)
            return v if v != 0 or str(val) == '0' else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(val) -> int:
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return 0

    def _fetch_last_trading_day_quotes(self) -> Optional[pd.DataFrame]:
        try:
            from data_provider.tushare_fetcher import TushareFetcher
            fetcher = TushareFetcher()
            if not fetcher.is_available():
                return None

            trade_dates = fetcher._get_trade_dates()
            if not trade_dates:
                return None

            df = None
            tried_dates: List[str] = []
            for last_date in trade_dates[:5]:
                tried_dates.append(last_date)
                logger.info("[PoolInit] 使用 tushare daily 获取交易日(%s)...", last_date)
                df = fetcher._call_api_with_rate_limit("daily", start_date=last_date, end_date=last_date)
                if df is not None and not df.empty:
                    break
                logger.warning("[PoolInit] tushare daily %s 无数据，尝试前一交易日", last_date)

            if df is None or df.empty:
                logger.warning("[PoolInit] tushare daily 尝试 %s 均无数据", tried_dates)
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
        pct_chg_col = self._detect_column(result, ['涨跌幅', 'change_pct'])

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
            result = result[(result['_price'] >= 1.0)]

        if market_cap_col:
            result['_market_cap'] = pd.to_numeric(result[market_cap_col], errors='coerce')
            result = result[(result['_market_cap'] >= 10e8)]

        if turnover_col:
            result['_turnover_rate'] = pd.to_numeric(result[turnover_col], errors='coerce')
            result = result[(result['_turnover_rate'] >= 0.3)]

        if pe_col:
            result['_pe_ratio'] = pd.to_numeric(result[pe_col], errors='coerce')
        else:
            result['_pe_ratio'] = 0.0

        if pb_col:
            result['_pb_ratio'] = pd.to_numeric(result[pb_col], errors='coerce')
        else:
            result['_pb_ratio'] = 0.0

        if pct_chg_col:
            result['_pct_chg'] = pd.to_numeric(result[pct_chg_col], errors='coerce').fillna(0)
        else:
            result['_pct_chg'] = 0.0

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
        elif market_cap >= 2000e8:
            score += 1

        if pe > 0:
            if 5 <= pe <= 40:
                score += 2
            elif 40 < pe <= 80:
                score += 1
        elif pe <= 0:
            score += 1

        if pb > 0:
            if 0.5 <= pb <= 5:
                score += 2
            elif 5 < pb <= 10:
                score += 1
        elif pb <= 0:
            score += 0

        if turnover >= 2:
            score += 1

        if score >= 5:
            return "premium"
        if score >= 3:
            return "standard"
        return "speculative"

    def _compute_valuation_score(self, pe: float, pb: float, market_cap: float) -> float:
        score = 0.0
        if pe > 0:
            if 5 <= pe <= 20:
                score += 25
            elif 20 < pe <= 40:
                score += 18
            elif 40 < pe <= 80:
                score += 10
            elif 80 < pe <= 150:
                score += 5
        else:
            if market_cap >= 100e8:
                score += 8
            elif market_cap >= 30e8:
                score += 5
            else:
                score += 2

        if pb > 0:
            if 0.5 <= pb <= 2:
                score += 20
            elif 2 < pb <= 5:
                score += 14
            elif 5 < pb <= 10:
                score += 8
            elif 10 < pb <= 20:
                score += 4

        if 100e8 <= market_cap <= 2000e8:
            score += 15
        elif 50e8 <= market_cap < 100e8:
            score += 10
        elif market_cap >= 2000e8:
            score += 8
        elif 30e8 <= market_cap < 50e8:
            score += 6

        return min(score, 60.0)

    def _compute_momentum_score(self, turnover: float, pct_chg: float) -> float:
        score = 0.0
        if turnover >= 5:
            score += 18
        elif turnover >= 3:
            score += 12
        elif turnover >= 1.5:
            score += 8
        elif turnover >= 0.5:
            score += 4

        if -2 <= pct_chg <= 3:
            score += 12
        elif 3 < pct_chg <= 7:
            score += 8
        elif -5 <= pct_chg < -2:
            score += 6
        elif pct_chg > 7:
            score += 5
        elif pct_chg < -5:
            score += 3

        return min(score, 30.0)

    def _compute_base_score(self, turnover: float, pct_chg: float, pe: float, pb: float, market_cap: float) -> float:
        val_score = self._compute_valuation_score(pe, pb, market_cap)
        mom_score = self._compute_momentum_score(turnover, pct_chg)
        return min(val_score + mom_score, 100.0)

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

            if pe <= 0:
                tags_list.append("亏损/未盈利")
            elif pe > 100:
                tags_list.append("高估值")
            elif pe <= 30:
                tags_list.append("低估值")

            if pb <= 0:
                tags_list.append("负净资产")
            elif pb > 10:
                tags_list.append("高市净率")

            if board == "科创板" and pe <= 0:
                tags_list.append("科创成长")

            if market_cap >= 2000e8:
                tags_list.append("超大盘")
            elif market_cap >= 500e8:
                tags_list.append("大盘蓝筹")
            elif 100e8 <= market_cap < 500e8:
                tags_list.append("中盘成长")
            elif market_cap < 30e8:
                tags_list.append("微盘股")

            if turnover >= 5:
                tags_list.append("活跃换手")
            elif turnover < 0.5:
                tags_list.append("低流动性")

            if abs(pct_chg) >= 9.5:
                tags_list.append("涨跌停")

            if base_score >= 60:
                tags_list.append("高分基线")

            if turnover < 0.3 and market_cap < 20e8:
                is_excluded = True
                exclude_reason = "极低流动性微盘"

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
                pct = 25 + (processed / total) * 50
                self._emit_progress(
                    status="running",
                    progress_pct=pct,
                    message=f"分类打标中: {processed}/{total}",
                    stage="tagging",
                    steps=[
                        ScreenerStep(label="获取行情数据", status="completed", detail=""),
                        ScreenerStep(label="基础过滤", status="completed", detail=""),
                        ScreenerStep(label="分类打标签", status="running", detail=f"{processed}/{total}"),
                        ScreenerStep(label="持久化存储", status="pending", detail=""),
                    ],
                )

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
