#!/usr/bin/env python3
"""
Package K-line source data for cloud drive sharing.

Copies 2020-2026 前复权 CSV files from BaiduNetdisk directory
into data/sources/, then zips them for upload.

Output:
    data/sources/kline_2020_2026.zip  (~450 MB, containing 2020-2026)
    data/sources/README.md            (download + usage instructions)
"""

import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = PROJECT_ROOT / "data" / "sources"
TARGET_DIR = SOURCE_DIR / "kline_source"
CSV_BASE = Path(r"D:\BaiduNetdiskDownload\stock6\每天一个文件\前复权")

YEARS = ["2020", "2021", "2022", "2023", "2024", "2025", "2026"]

def main():
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    total_files = 0
    total_size = 0

    print("Copying source files...")
    for year in YEARS:
        candidates = [
            CSV_BASE / year,
            CSV_BASE / "2000至2025" / year,
        ]
        year_dir = next((c for c in candidates if c.exists() and c.is_dir()), None)
        if year_dir is None:
            print(f"  {year}: NOT FOUND, skipping")
            continue

        dest = TARGET_DIR / year
        dest.mkdir(exist_ok=True)

        for f in sorted(year_dir.glob("*.csv")):
            shutil.copy2(f, dest / f.name)
            total_files += 1
            total_size += os.path.getsize(f)

        print(f"  {year}: {len(list(year_dir.glob('*.csv')))} files")

    print(f"\nTotal: {total_files} files, {total_size / (1024*1024):.0f} MB")

    zip_path = SOURCE_DIR / "kline_2020_2026.zip"
    print(f"\nCreating archive: {zip_path.name} ...")
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(str(TARGET_DIR)):
            for f in files:
                file_path = Path(root) / f
                arcname = file_path.relative_to(TARGET_DIR)
                zf.write(str(file_path), str(arcname))

    zip_size = os.path.getsize(str(zip_path)) / (1024 * 1024)
    print(f"Archive size: {zip_size:.0f} MB")

    shutil.rmtree(str(TARGET_DIR))
    print(f"Cleaned up temporary files at {TARGET_DIR}")

    readme = SOURCE_DIR / "README.md"
    readme.write_text(
        f"""# K-line 数据源

## 文件

| 文件 | 大小 | 内容 |
|------|------|------|
| `kline_2020_2026.zip` | ~{zip_size:.0f} MB | 2020-2026 年 A 股前复权日线数据 |

## 使用方式

1. 从云盘下载 `kline_2020_2026.zip`
2. 解压到 `data/sources/kline_source/`（即本目录下的 `kline_source/`）
3. 运行导入脚本：

```bash
python scripts/import_kline.py
```

导入脚本会自动检测 `data/sources/kline_source/` 路径。

## 数据来源

- 金玥数据
- 前复权价格（适配回测—自动处理分红除权）
- 每日约 5,500 只 A 股 × 38 列（OHLCV + 均线 + 估值 + 动量 + 行业）

## 生成日期

{datetime.now().strftime("%Y-%m-%d")}

## 注意

- Parquet 生成文件 (`data/kline/daily/`) 已 gitignored
- 元数据文件 (`symbols.json`, `stock_meta.parquet`) 已提交到仓库
""",
        encoding="utf-8",
    )

    print(f"\nDone! Archive: {zip_path}")
    print(f"Upload this file to your cloud drive and share the link.")
    print(f"README written to: {readme}")


if __name__ == "__main__":
    main()
