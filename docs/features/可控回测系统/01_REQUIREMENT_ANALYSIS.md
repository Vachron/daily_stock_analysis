# 用户可控回测系统

> 状态：草案 → 已增强（极致压缩存储方案）
> 最后更新：2026-04-28
> 关联代码：`src/core/backtest_engine.py`, `apps/dsa-web/src/pages/BacktestPage.tsx`, `src/alpha/portfolio_simulator.py`
> 参考对标：QuantConnect, Backtrader, TradingView PineScript

## 背景

当前回测系统的局限性：

1. **只验证历史分析记录**：当前回测只能对比"AI分析时的预测 vs N天后的实际走势"，无法让用户**自己设定策略并模拟**从头到尾的买卖
2. **用户无法调整任何参数**：资金量、策略因子、买卖触发条件全部黑盒
3. **缺少完整交易模拟**：没有仓位管理、没有分步调仓、没有每日资产变化
4. **结果维度单一**：只返回胜率/夏普等全局指标，缺少逐笔交易明细和资金曲线
5. **与选股系统割裂**：选出的股票无法直接导入回测系统进行策略验证

## 数据可行性分析

### 现有数据资产

| 数据源 | 路径 | 格式 | 时间跨度 | 字段数 | 每日规模 |
|--------|------|------|---------|--------|---------|
| 本地CSV (前复权) | `D:\BaiduNetdiskDownload\stock6\每天一个文件\前复权\` | 每日一个CSV | 2000-2026 | **38列** | ~5,458股 × 1.6 MB |

### CSV 关键字段

```
OHLC: 开盘价, 最高价, 最低价, 收盘价, 前收盘价
量价: 成交量(股), 成交额(元), 换手率, 量比
涨跌: 涨幅%, 振幅%, 是否ST, 是否涨停
动量: 3日涨幅%, 6日涨幅%, 10日涨幅%, 25日涨幅%
估值: 滚动市盈率, 市净率, 滚动市销率
市值: 总股本, 流通股本, 总市值(元), 流通市值(元)
均线: 5日线, 10日线, 20日线, 30日线, 60日线, 120日线, 250日线
元信息: 代码, 名称, 所属行业, 上市时间, 退市时间, 是否融资融券
```

### 数据体量

| 指标 | 数值 |
|------|------|
| 压缩包 | `前复权.rar` = **1.80 GB** (2000-2025年) |
| 2026年已解压 | 74 文件, **118 MB** |
| 预估6年解压后 | ~1,500 文件, **~2.5 GB** (CSV 格式) |
| 6年总行数 | ~1,500日 × 5,458股 = **~8,200,000 条记录** |

---

## 存储架构优化：从 SQLite 到 Parquet + DuckDB

### 业界调研结论

| 方案 | 压缩比 | 查询速度 | 生态成熟度 | 适合场景 |
|------|--------|---------|-----------|---------|
| CSV (基准) | 1x | 慢 | ★★★★★ | 交换格式 |
| SQLite (行式) | ~2x | 中 (OLTP) | ★★★★★ | 小数据量 CRUD |
| **Parquet + DuckDB** | **5-15x** | **快 (OLAP)** | ★★★★ | **金融时序分析** |
| Qlib .bin 格式 | ~3x | 极快 | ★★★ (Python only) | ML 训练 |
| ClickHouse | 10-20x | 极快 | ★★★ (需Server) | TB级生产环境 |

**结论**：Parquet + DuckDB 是个人量化回测的黄金方案。理由：
- 业界验证：`quantmini` 项目实现 70%+ 压缩率，1亿条 K 线仅 2-5 GB
- DuckDB 零配置：`pip install duckdb`，嵌入式运行，无需数据库服务
- 直接查询 Parquet 文件，无需"导入"步骤
- 列式存储天然适合"只查 OHLCV 中的某几列"的场景

### 五层压缩优化策略

```
┌────────────────────────────────────────────────────────────────────┐
│                    5 层压缩漏斗                                     │
│                                                                    │
│  原始 CSV 6年数据:  ~2.5 GB (5,458 股 × 1,500日 × 38 列)           │
│                                                                    │
│  Layer 1: 列裁剪 — 删除可计算列                                     │
│  ├─ 删除: ma5/10/20/30/60/120/250 (DuckDB 窗口函数可计算)          │
│  ├─ 删除: pct_3d/6d/10d/25d (可用 close 计算)                     │
│  └─ 删除: 前收盘价 (可用 LAG 函数), 涨幅% (可计算)                   │
│  → 38列 → 25列, 节省 ~30%                                          │
│  → ~1.75 GB                                                       │
│                                                                    │
│  Layer 2: 类型窄化 (float64→float32, int64→int32)                  │
│  ├─ open/high/low/close → float32 (4B → 4B, 不变)                  │
│  ├─ volume/amount → int32 (8B → 4B)                                │
│  ├─ 市盈率/市净率/市销率 → float32 (8B → 4B)                       │
│  ├─ 总市值/流通市值 → int64 (值太大, 保持)                           │
│  └─ 换手率/量比 → float32 (8B → 4B)                                │
│  → 每行 ~400B → ~200B, 节省 ~50%                                   │
│  → ~0.9 GB                                                        │
│                                                                    │
│  Layer 3: 整数编码 (价格 × 100 → int32, 代码 → category)            │
│  ├─ open/high/low/close → int32 (以厘为单位: ¥18.50 → 1850)        │
│  ├─ 日期 → int32 (距 2000-01-01 的天数)                             │
│  ├─ 代码 → uint16 (映射表: 600519 → 1, 000001 → 2, ...)           │
│  └─ 布尔列：is_st, is_limit_up, is_margin → uint8 (1B)             │
│  → Parquet DELTA_BINARY_PACKED 编码对有序整数压缩率可达 80%+        │
│  → ~0.5 GB                                                        │
│                                                                    │
│  Layer 4: Parquet 列式 + ZSTD 压缩 (compression_level=6)            │
│  ├─ 相同类型数据聚在一起，重复模式极多                               │
│  ├─ ZSTD 字典压缩对金融数据效率极高                                  │
│  └─ 业界实测：1亿条 K 线从 10-20GB (CSV) → 2-5GB (Parquet+ZSTD)    │
│  → 3-5x 压缩比                                                    │
│  → ~150-170 MB / 6年                                              │
│                                                                    │
│  Layer 5: 按股票代码分区 (每天一个 Parquet 文件 vs 每只股票一个文件)  │
│  ├─ 按股票分：不需要的股票直接跳过，零 I/O                           │
│  ├─ 增量更新：新一天的数据只需新建当天文件                            │
│  └─ 并行查询：多只股票可多线程同时读取                               │
│  → metadata 开销约 5%，可忽略                                       │
│  → ~160-180 MB / 6年                                               │
│                                                                    │
│  ──────────────────────────────────────────────                    │
│  最终预估: 180 - 250 MB (6年，5,458只A股全量日线)                   │
│  压缩比:  CSV 2.5GB → 0.18GB = 14x                                 │
│  对比方案: SQLite 原方案 1.7GB → 现在 0.2GB = 8.5x 更小             │
└────────────────────────────────────────────────────────────────────┘
```

### 为什么按股票分区？

```
每天一个 Parquet 文件 (按日期分区):
  优点：导入简单，逐日 append
  缺点：查茅台6年行情 → 扫描 1,500 个文件 → 慢
       全市场某日打分 → 必须读整个1.6MB文件 → 即使只要500只股票

按股票一个 Parquet 文件 (推荐):
  优点：查茅台6年行情 → 读 1 个文件 → <1ms
       全市场打分 → DuckDB predicate pushdown 只读需要的列
       增量更新 → 只需 append 到对应股票的文件
  缺点：首次导入需要预排序 (一次性成本)
```

### 最终目录结构

```
data/kline/
├── symbols.json                    # 代码→ID 映射: {"000001": 1, "600519": 2, ...}
├── stock_meta.parquet              # 元数据: 代码, 名称, 行业, 上市日, 退市日
├── daily/                          # 前复权日线数据
│   ├── code_1.parquet              # 000001 平安银行 (映射ID=1)
│   ├── code_2.parquet              # 600519 贵州茅台 (映射ID=2)
│   ├── ...
│   └── code_5458.parquet
└── benchmark/                      # 指数数据 (沪深300等)
    ├── 000300.parquet
    └── 000905.parquet
```

### Parquet 文件 Schema

```python
# 单只股票的 Parquet 文件 schema (优化后: 25列 → 核心列)
SCHEMA = {
    'date':        'int32',     # days since 2000-01-01 (e.g., 8831 = 2024-03-15)
    'open':        'int32',     # price × 100 (cents)
    'high':        'int32',
    'low':         'int32',
    'close':       'int32',
    'volume':      'int32',     # 成交量（股），大多数股票日成交<2^31
    'amount':      'int64',     # 成交额（分），大盘股日成交超2^31
    'turnover':    'float32',   # 换手率%
    'pct_chg':     'float32',   # 涨跌幅%
    'amplitude':   'float32',   # 振幅%
    'volume_ratio': 'float32',  # 量比
    'pe_ttm':      'float32',   # 滚动市盈率
    'pb':          'float32',   # 市净率
    'ps_ttm':      'float32',   # 滚动市销率
    'total_mv':    'int64',     # 总市值（元）
    'float_mv':    'int64',     # 流通市值（元）
    'total_shares': 'int64',    # 总股本
    'float_shares': 'int64',    # 流通股本
    'is_st':       'uint8',     # 0/1
    'is_limit_up': 'uint8',     # 0/1
}

# 元数据表 (stock_meta.parquet)
META_SCHEMA = {
    'code':        'str',
    'code_id':     'uint16',    # 映射ID
    'name':        'str',
    'industry':    'str',       # 所属行业
    'list_date':   'int32',     # 上市日期
    'delist_date': 'int32',     # 退市日期 (0 = 未退市)
    'is_margin':   'uint8',     # 是否融资融券
}
```

### 被删除的可计算列 (DuckDB SQL 实时计算)

```sql
-- 这些列不需要存储，查询时用 DuckDB SQL 动态计算
-- 示例：查询某只股票的完整回测所需数据

SELECT
    date,
    open / 100.0 AS open,           -- 还原价格（自动）
    high / 100.0 AS high,
    low / 100.0 AS low,
    close / 100.0 AS close,
    LAG(close) OVER w / 100.0 AS pre_close,
    volume,
    amount / 100.0 AS amount_yuan,
    turnover,
    pct_chg,
    
    -- 动态计算均线（无需存储！）
    AVG(close) OVER (ORDER BY date ROWS 4 PRECEDING) / 100.0 AS ma5,
    AVG(close) OVER (ORDER BY date ROWS 9 PRECEDING) / 100.0 AS ma10,
    AVG(close) OVER (ORDER BY date ROWS 19 PRECEDING) / 100.0 AS ma20,
    AVG(close) OVER (ORDER BY date ROWS 29 PRECEDING) / 100.0 AS ma30,
    AVG(close) OVER (ORDER BY date ROWS 59 PRECEDING) / 100.0 AS ma60,
    AVG(close) OVER (ORDER BY date ROWS 119 PRECEDING) / 100.0 AS ma120,
    AVG(close) OVER (ORDER BY date ROWS 249 PRECEDING) / 100.0 AS ma250,
    
    -- 动态计算多周期动量
    (close - LAG(close, 3) OVER w) * 100.0 / NULLIF(LAG(close, 3) OVER w, 0) AS pct_3d,
    (close - LAG(close, 6) OVER w) * 100.0 / NULLIF(LAG(close, 6) OVER w, 0) AS pct_6d,
    (close - LAG(close, 10) OVER w) * 100.0 / NULLIF(LAG(close, 10) OVER w, 0) AS pct_10d,
    (close - LAG(close, 25) OVER w) * 100.0 / NULLIF(LAG(close, 25) OVER w, 0) AS pct_25d

FROM read_parquet('data/kline/daily/code_2.parquet')
WINDOW w AS (ORDER BY date)
ORDER BY date
```

### 压缩效果逐层预估

```
                                                   累计大小   压缩比(vs CSV)
─────────────────────────────────────────────────────────────────────
原始 CSV (38列 × float64 × 8.2M行)                  2.50 GB     1.0x
Layer 1: 删除11列可计算字段                          1.75 GB     1.4x
Layer 2: 类型窄化 (float32, int32)                   0.90 GB     2.8x
Layer 3: 整数编码 (价格×100, 日期→int32, code→uint16) 0.50 GB     5.0x
Layer 4: Parquet 列式 + ZSTD level=6                 0.18 GB    13.9x
Layer 5: 按股票分区 (metadata开销)                    0.20 GB    12.5x
─────────────────────────────────────────────────────────────────────
```

### 与原始 SQLite 方案对比

| 维度 | SQLite 方案 | Parquet + DuckDB 方案 |
|------|------------|----------------------|
| 6年数据大小 | ~1.7 GB | **~200 MB** (8.5x 小) |
| 查询模式 | 逐行扫描 | **列式向量化** |
| 依赖 | 无额外依赖 | `pip install duckdb pyarrow` |
| 全市场单日打分 | ~3 秒 | **<1 秒** |
| 单股6年K线 | <5ms | **<1ms** (读单个文件) |
| 计算均线/动量 | 需要存储或Python算 | **SQL窗口函数实时计算** |
| 可迁移性 | 不错 | 极好 (5000个独立文件) |
| 分析能力 | 基础SQL | **完整OLAP** (窗口/CTE/协方差) |

### 导入脚本设计

```python
# scripts/import_kline.py — 一次性导入，极致压缩

class KlineImporter:
    """
    从 D:\BaiduNetdiskDownload\stock6\每天一个文件\前复权\
    导入到 data/kline/daily/*.parquet (按股票分区)

    输出:
      data/kline/symbols.json       代码→ID映射
      data/kline/stock_meta.parquet 股票元数据
      data/kline/daily/code_*.parquet 每只股票一个文件

    用法：
      python scripts/import_kline.py --years 2020,2021,2022,2023,2024,2025,2026

    压缩策略:
      - open/high/low/close → int32 (×100)
      - date → int32 (days since 2000)
      - volume → int32, amount → int64
      - 删除可计算列 (均线、动量、前收盘价、涨幅)
      - Parquet writer: compression='zstd', compression_level=6
      - 启用 DELTA_BINARY_PACKED encoding (Parquet v2)

    特性：
      - 断点续传 (按股票代码跳过已导入)
      - 自动解压 rar → 年份子目录
      - 内存安全 (10只股票一批，避免OOM)
      - DuckDB 写入效率: ~100万行/分钟
    """
```

**导入执行流程：**

```
Phase 1: 解压前复权.rar (如未解压)          ~5分钟 (手动)
Phase 2: 扫描所有CSV → 建立 code→ID 映射     ~1分钟
Phase 3: 逐股票聚合数据 + 写入 Parquet        ~15分钟 (8.2M行)
Phase 4: 创建 stock_meta.parquet              ~10秒
Phase 5: 验证统计 (输出压缩报告)              ~30秒
────────────────────────────────────────
总计: ~20分钟 (首次)
```

### 查询示例 (DuckDB)

```python
import duckdb

conn = duckdb.connect()

# 查询茅台2024年全部数据
df = conn.execute("""
    SELECT date, open/100.0 AS open, high/100.0 AS high,
           low/100.0 AS low, close/100.0 AS close, volume
    FROM read_parquet('data/kline/daily/code_2.parquet')
    WHERE date BETWEEN 8767 AND 9131  -- 2024-01-01 ~ 2024-12-31
    ORDER BY date
""").df()

# 全市场某日的 close + pct_chg (打分用)
df = conn.execute("""
    SELECT c.code_id, k.close / 100.0 AS close, k.pct_chg, k.turnover,
           k.pe_ttm, k.pb, k.total_mv
    FROM read_parquet('data/kline/daily/*.parquet') k
    JOIN read_parquet('data/kline/stock_meta.parquet') c
      ON k.code_id = c.code_id
    WHERE k.date = 8831  -- 2024-03-15
      AND k.close > 0
""").df()
```

## 业界对标分析 (保留)

(与之前版本相同，略)

## 实施计划

| 阶段 | 内容 | 依赖 |
|------|------|------|
| **0** | **pip install duckdb pyarrow** | 无 |
| **0a** | 解压 `前复权.rar` → 提取2020-2026年CSV | 手动 |
| **0b** | 编写 + 运行 `scripts/import_kline.py` (~20分钟) | 阶段0a |
| **0c** | 验证压缩效果: ~200MB for 6年 | 阶段0b |
| 1 | 后端: KlineRepo (DuckDB 接入层) | 阶段0c |
| 2 | 后端: 参数模型 + 组合回测引擎 | 阶段1 |
| 3 | 后端: 交易记录生成 + API | 阶段2 |
| 4 | 前端: 回测参数面板 | 阶段3 |
| 5 | 前端: 绩效报告 + 资金曲线 | 阶段3 |
| 6 | 后端: 参数扫描引擎 | 阶段2 |
| 7 | 前端: 参数热力图 | 阶段6 |

## 参考链接

- [QuantConnect 平台](https://www.quantconnect.com/)
- [Backtrader 文档](https://www.backtrader.com/)
- [DuckDB + Parquet 优化指南](https://duckdb.org/docs/stable/data/parquet/tips.html)
- [Parquet DELTA_BINARY_PACKED encoding](https://github.com/apache/parquet-format/blob/master/Encodings.md)
- [quantmini 项目 (70%+ 压缩率)](https://github.com/nittygritty-zzy/quantmini)
- [现有回测引擎](file:///d:/Stock_Analysis/daily_stock_analysis/src/core/backtest_engine.py)
- [组合模拟器](file:///d:/Stock_Analysis/daily_stock_analysis/src/alpha/portfolio_simulator.py)
- [本地K线数据](file:///D:/BaiduNetdiskDownload/stock6)
