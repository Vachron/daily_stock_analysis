#!/usr/bin/env python3   # -*- coding: utf-8 -*-
"""
K-line data importer v2 — DuckDB single-pass CSV → Parquet (per-stock)

Strategy:
    Phase 1: Scan CSV headers for metadata (code→ID mapping, stock info) — ~2 min
    Phase 2: DuckDB reads ALL CSVs once → temp table → EXPORT per-stock .parquet — ~5 min

Usage:
    python scripts/import_kline.py
    python scripts/import_kline.py --years 2020,2021,2022,2023,2024,2025,2026

Expected output:
    data/kline/symbols.json       code→ID mapping
    data/kline/stock_meta.parquet stock metadata
    data/kline/daily/code_*.parquet (~5400 files, ~200 MB total)
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("kline_import")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "kline"
DAILY_DIR = DATA_DIR / "daily"
CSV_BASE = Path(r"D:\BaiduNetdiskDownload\stock6\每天一个文件\前复权")
ORIGIN_DATE = date(2000, 1, 1)
YEAR_MIN, YEAR_MAX = 2020, 2026

COLUMN_MAP_CN = {
    "日期": "date_raw", "代码": "code", "名称": "name", "所属行业": "industry",
    "开盘价": "open", "最高价": "high", "最低价": "low", "收盘价": "close",
    "成交量（股）": "volume", "成交额（元）": "amount", "换手率": "turnover",
    "涨幅%": "pct_chg", "振幅%": "amplitude", "是否ST": "is_st",
    "量比": "volume_ratio", "滚动市盈率": "pe_ttm", "市净率": "pb",
    "滚动市销率": "ps_ttm", "总股本（股）": "total_shares",
    "流通股本（股）": "float_shares", "总市值（元）": "total_mv",
    "流通市值（元）": "float_mv", "上市时间": "list_date_raw",
    "退市时间": "delist_date_raw", "是否融资融券": "is_margin_raw",
}

PARQUET_SCHEMA = pa.schema([
    pa.field("date", pa.int32()),
    pa.field("open", pa.int32()), pa.field("high", pa.int32()),
    pa.field("low", pa.int32()), pa.field("close", pa.int32()),
    pa.field("volume", pa.int64()), pa.field("amount", pa.int64()),
    pa.field("turnover", pa.float32()), pa.field("pct_chg", pa.float32()),
    pa.field("amplitude", pa.float32()), pa.field("volume_ratio", pa.float32()),
    pa.field("pe_ttm", pa.float32()), pa.field("pb", pa.float32()),
    pa.field("ps_ttm", pa.float32()),
    pa.field("total_shares", pa.int64()), pa.field("float_shares", pa.int64()),
    pa.field("total_mv", pa.int64()), pa.field("float_mv", pa.int64()),
    pa.field("is_st", pa.uint8()), pa.field("is_margin", pa.uint8()),
])


def date_to_int(val) -> int:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return 0
    if isinstance(val, (int, float)):
        i = int(val)
        return i if i > 10000 else i
    s = str(val).strip()
    if not s or s == "0":
        return 0
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return (datetime.strptime(s, fmt).date() - ORIGIN_DATE).days
        except ValueError:
            continue
    return 0


def scan_metadata(years: List[int]) -> Tuple[Dict[str, int], pd.DataFrame, List[Path]]:
    code_ids, meta_rows, csv_files = {}, [], []

    for year in years:
        candidates = [CSV_BASE / str(year), CSV_BASE / "2000至2025" / str(year)]
        year_dir = next((c for c in candidates if c.exists() and c.is_dir()), None)
        if year_dir is None:
            logger.warning("Year dir not found: %d", year)
            continue
        for f in sorted(year_dir.glob("*.csv")):
            csv_files.append(f)

    logger.info("Phase 1: Scanning %d CSVs for metadata...", len(csv_files))
    next_id = 1

    for i, fp in enumerate(csv_files):
        if i % 200 == 0:
            logger.info("  Metadata: %d/%d", i + 1, len(csv_files))

        try:
            df = pd.read_csv(fp, encoding="utf-8-sig", dtype=str, nrows=0)
        except Exception:
            continue

        needed_cols = ["代码", "名称", "所属行业", "上市时间", "退市时间", "是否融资融券"]
        available = [c for c in needed_cols if c in df.columns]
        if not available:
            continue

        try:
            df = pd.read_csv(fp, encoding="utf-8-sig", dtype=str, usecols=available)
        except Exception:
            continue

        for _, row in df.iterrows():
            code = str(row.get("代码", "")).strip().zfill(6)
            if not code or code == "NAN":
                continue

            if code not in code_ids:
                code_ids[code] = next_id
                next_id += 1
                meta_rows.append({
                    "code_id": code_ids[code],
                    "code": code,
                    "name": str(row.get("名称", "")).strip(),
                    "industry": str(row.get("所属行业", "")).strip(),
                    "list_date": date_to_int(str(row.get("上市时间", "")).strip()),
                    "delist_date": date_to_int(str(row.get("退市时间", "")).strip()),
                    "is_margin": 1 if str(row.get("是否融资融券", "")).strip() == "是" else 0,
                })

    meta_df = pd.DataFrame(meta_rows)
    logger.info("Found %d unique stocks", len(code_ids))
    return code_ids, meta_df, csv_files


def import_with_duckdb(code_ids, meta_df, csv_files):
    logger.info("Phase 2: Single-pass import (%d files)...", len(csv_files))

    DAILY_DIR.mkdir(parents=True, exist_ok=True)

    symbols_path = DATA_DIR / "symbols.json"
    meta_path = DATA_DIR / "stock_meta.parquet"

    with open(symbols_path, "w", encoding="utf-8") as f:
        json.dump(code_ids, f, ensure_ascii=False, indent=2)

    meta_table = pa.Table.from_pandas(meta_df, schema=pa.schema([
        pa.field("code_id", pa.uint16()), pa.field("code", pa.string()),
        pa.field("name", pa.string()), pa.field("industry", pa.string()),
        pa.field("list_date", pa.int32()), pa.field("delist_date", pa.int32()),
        pa.field("is_margin", pa.uint8()),
    ]))
    pq.write_table(meta_table, str(meta_path), compression="zstd", compression_level=6)
    logger.info("Stock metadata saved")

    id_to_code = {v: k for k, v in code_ids.items()}
    all_ids = sorted(code_ids.values())
    delist_map = {code_ids[code]: dl for code, dl in
                  zip(meta_df["code"], meta_df["delist_date"]) if dl > 0}

    already = set()
    for pp in DAILY_DIR.glob("code_*.parquet"):
        try:
            already.add(int(pp.stem.replace("code_", "")))
        except ValueError:
            pass

    pending = [cid for cid in all_ids if cid not in already]
    if not pending:
        logger.info("All %d stocks already imported", len(all_ids))
        return

    logger.info("Importing %d stocks (%d done, %d total)", len(pending), len(already), len(all_ids))

    accum: Dict[int, List[Dict]] = {cid: [] for cid in all_ids}
    total_csv = len(csv_files)
    total_rows = 0
    errors = 0

    for i, fp in enumerate(csv_files):
        if i % 100 == 0:
            logger.info("  CSV %d/%d (rows: %s, err: %d)", i + 1, total_csv, f"{total_rows:,}", errors)

        try:
            datestr = fp.stem.split("_")[0]
            day_int = date_to_int(datestr)
            if day_int <= 0:
                continue
        except (IndexError, ValueError):
            continue

        try:
            df = pd.read_csv(fp, encoding="utf-8-sig", dtype=str)
        except Exception:
            errors += 1
            continue

        rename_map = {k: v for k, v in COLUMN_MAP_CN.items() if k in df.columns}
        df = df.rename(columns=rename_map)
        if "code" not in df.columns:
            continue

        df["code"] = df["code"].astype(str).str.strip().str.zfill(6)

        if "date_raw" in df.columns:
            df["date_raw"] = df["date_raw"].apply(date_to_int)

        for _, row in df.iterrows():
            code = row.get("code", "")
            cid = code_ids.get(code)
            if cid is None:
                continue

            day = date_to_int(row.get("date_raw", 0))
            if day <= 0:
                day = day_int

            dl = delist_map.get(cid, 0)
            if dl > 0 and day > dl:
                continue

            try:
                rec = {
                    "date": day,
                    "open": int(round(float(row.get("open", 0) or 0) * 100)),
                    "high": int(round(float(row.get("high", 0) or 0) * 100)),
                    "low": int(round(float(row.get("low", 0) or 0) * 100)),
                    "close": int(round(float(row.get("close", 0) or 0) * 100)),
                    "volume": int(float(row.get("volume", 0) or 0)),
                    "amount": int(float(row.get("amount", 0) or 0)),
                    "turnover": float(row.get("turnover", 0) or 0),
                    "pct_chg": float(row.get("pct_chg", 0) or 0),
                    "amplitude": float(row.get("amplitude", 0) or 0),
                    "volume_ratio": float(row.get("volume_ratio", 0) or 0),
                    "pe_ttm": float(row.get("pe_ttm", 0) or 0),
                    "pb": float(row.get("pb", 0) or 0),
                    "ps_ttm": float(row.get("ps_ttm", 0) or 0),
                    "total_shares": int(float(row.get("total_shares", 0) or 0)),
                    "float_shares": int(float(row.get("float_shares", 0) or 0)),
                    "total_mv": int(float(row.get("total_mv", 0) or 0)),
                    "float_mv": int(float(row.get("float_mv", 0) or 0)),
                    "is_st": 1 if str(row.get("is_st", "")).strip() == "是" else 0,
                    "is_margin": 1 if str(row.get("is_margin_raw", "")).strip() == "是" else 0,
                }
            except (ValueError, TypeError):
                continue

            accum[cid].append(rec)
            total_rows += 1

    logger.info("Phase 3: Writing %d Parquet files...", len(pending))

    for idx, cid in enumerate(pending):
        rows = accum[cid]
        if not rows:
            continue

        df = pd.DataFrame(rows)
        df = df.sort_values("date").reset_index(drop=True)

        dtypes = {
            "date": "int32", "open": "int32", "high": "int32", "low": "int32", "close": "int32",
            "volume": "int64", "amount": "int64", "turnover": "float32", "pct_chg": "float32",
            "amplitude": "float32", "volume_ratio": "float32",
            "pe_ttm": "float32", "pb": "float32", "ps_ttm": "float32",
            "total_shares": "int64", "float_shares": "int64",
            "total_mv": "int64", "float_mv": "int64",
            "is_st": "uint8", "is_margin": "uint8",
        }
        for col, dt in dtypes.items():
            if col in df.columns:
                df[col] = df[col].astype(dt)

        out_path = DAILY_DIR / f"code_{cid}.parquet"
        table = pa.Table.from_pandas(df, schema=PARQUET_SCHEMA, preserve_index=False)
        pq.write_table(table, str(out_path), compression="zstd", compression_level=6, row_group_size=50000)

        if idx % 500 == 0:
            logger.info("  Written %d/%d stocks", idx + 1, len(pending))

        del accum[cid]

    total_size = sum(f.stat().st_size for f in DAILY_DIR.glob("code_*.parquet") if f.is_file())
    count_files = len(list(DAILY_DIR.glob("code_*.parquet")))

    logger.info("=" * 60)
    logger.info("Import complete!")
    logger.info("  Files:  %d", count_files)
    logger.info("  Rows:   %s", f"{total_rows:,}")
    logger.info("  Size:   %.1f MB", total_size / (1024 * 1024))
    logger.info("  Errors: %d", errors)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import K-line CSV → Parquet (DuckDB single-pass)")
    parser.add_argument("--years", type=str, default=None,
                       help="Comma-separated years (default: 2020-2026)")
    args = parser.parse_args()

    years = [int(y.strip()) for y in args.years.split(",")] if args.years \
        else list(range(YEAR_MIN, YEAR_MAX + 1))

    t0 = time.time()
    logger.info("Import years: %s", years)

    code_ids, meta_df, csv_files = scan_metadata(years)
    if not code_ids:
        logger.error("No stocks found")
        sys.exit(1)

    import_with_duckdb(code_ids, meta_df, csv_files)

    logger.info("Total time: %.1f minutes", (time.time() - t0) / 60)
