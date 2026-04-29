# 需求分析：K线数据导入（Parquet + DuckDB）

## 1. 需求概述

将本地云盘中的每日CSV全量A股K线数据（2020-2026，1529个文件）导入为按股票分区的Parquet文件，供Alpha系统和回测引擎使用。

## 2. 消歧义记录

| 歧义点 | 决策 |
|--------|------|
| 数据源路径 | `F:\Stock_project\daily_stock_analysis\data\sources\{year}\` |
| 处理年份 | 2020-2026（7年） |
| 存储格式 | Parquet（按股票分区）+ ZSTD压缩 |

## 3. 功能需求

- FR-01: CSV元数据扫描 → code→ID映射 + stock_meta.parquet
- FR-02: 逐股票聚合数据 → 去可计算列（均线/动量）→ 类型窄化 → 整数编码
- FR-03: Parquet写出 → ZSTD level=6 → row_group_size=50000

## 4. 验收标准

- 5724支股票×7年数据 ≈ 7.5M行 → ~200-500MB Parquet
- 无错误行
- symbols.json + stock_meta.parquet 完整
