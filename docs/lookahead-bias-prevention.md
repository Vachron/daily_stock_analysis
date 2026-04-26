# 未来函数防范规范（Look-ahead Bias Prevention）

> 最后更新：2026-04-26
> 适用范围：`src/core/`、`data_provider/`、`src/services/backtest_service.py`、所有因子计算与回测代码

## 问题描述

未来函数（look-ahead bias）是量化交易中最隐蔽也最致命的陷阱。它指的是在策略计算或回测中，使用了**当时不可能知道的信息**，导致回测结果虚高、实盘必然失效。

本项目中已发现多处未来函数风险，涉及复权方式、入场价格、分形确认、IC 计算等多个环节。本文档列出所有已知风险、防范规则和检测方法。

## 风险清单

| # | 风险项 | 严重度 | 触发条件 | 现有代码位置 |
|---|--------|--------|----------|-------------|
| 1 | 前复权数据未来函数 | 🔴 高危 | 回测使用前复权价格 | `data_provider/akshare_fetcher.py:417`、`efinance_fetcher.py:403`、`yfinance_fetcher.py:184` |
| 2 | 当日收盘价用于信号计算 | 🔴 高危 | 盘中运行选股，close[-1] 为未确定价格 | `src/core/strategy_signal_extractor.py:147`（`_bull_trend` 等所有策略） |
| 3 | 回测入场价使用当日收盘 | 🟡 中危 | 回测假设以分析日收盘价成交 | `src/services/backtest_service.py:133` |
| 4 | 缠论分形使用未来K线确认 | 🟡 中危 | 分形识别遍历到 len(close)-2 | `src/core/strategy_signal_extractor.py:645`（`_chan_theory`） |
| 5 | IC 计算中因子值与收益率起点重叠 | 🟡 中危 | 因子分数和收益率都基于当日收盘 | IC 引擎（待实现） |
| 6 | 波浪理论使用未来K线区间 | 🟢 低危 | recent_high 使用近5日最高价 | `src/core/strategy_signal_extractor.py:730`（`_wave_theory`） |

---

## 防范规则

### 规则1：回测必须使用不复权数据

- **要求**：回测引擎计算历史收益时，必须使用不复权（raw）价格。策略信号计算使用后复权（hfq）价格。
- **原因**：
  - 前复权（qfq）以最新价格为基准向前调整，每次除权后所有历史价格都会改变
  - 后复权（hfq）只调整历史价格，不影响最新价格，且调整是增量的
  - 不复权（raw）反映真实交易价格，是回测的唯一正确选择
- **检测方法**：回测运行时检查数据源参数，`adjust` 不允许为 `qfq` 或 `fqt=1`
- **例外**：策略信号计算（非回测）可使用后复权，因为后复权不会因未来事件改变历史值

**实施要点**：

```python
# 回测场景
backtest_data = data_provider.get_daily_history(code, adjust="none")  # 不复权

# 策略信号计算场景
signal_data = data_provider.get_daily_history(code, adjust="hfq")  # 后复权

# 前复权仅用于展示（当前价格与历史价格在同一基准上）
display_data = data_provider.get_daily_history(code, adjust="qfq")  # 前复权
```

**现有代码影响**：

| 文件 | 当前行为 | 需要改动 |
|------|---------|---------|
| `akshare_fetcher.py` | 默认 `adjust="qfq"` | 增加 `adjust` 参数，回测时传 `"none"` |
| `efinance_fetcher.py` | 默认 `fqt=1` | 增加 `fqt` 参数，回测时传 `0` |
| `yfinance_fetcher.py` | `auto_adjust=True` | 回测时传 `auto_adjust=False` |
| `baostock_fetcher.py` | 已支持 `adjustflag` 参数 | 无需改动 |
| `backtest_service.py` | 使用 `start_daily.close` | 改为使用不复权数据的收盘价 |

### 规则2：策略信号必须基于 T-1 日数据

- **要求**：策略信号计算时，所有技术指标（MA、RSI、布林带等）必须基于 `close[:-1]`（截至昨日）计算，`close[-1]`（今日）仅用于确认是否触发。
- **原因**：盘中运行时，当日收盘价尚未确定；即使收盘后运行，也应明确区分"信号生成时刻"和"信号确认时刻"
- **检测方法**：代码审查时检查策略函数是否直接用 `close[-1]` 参与指标计算
- **例外**：如果系统明确标注"仅限收盘后运行"且运行时间固定在 15:30 之后，可放宽为 `close[-1]` 参与计算，但必须在代码中添加运行时间断言

**实施要点**：

```python
# 当前写法（有未来函数风险）
ma5 = self._calc_sma(close, 5)  # close[-1] 包含今日
cur = close[-1]
if cur > ma5[-1]:  # 今日价格与今日均线比较

# 正确写法
ma5 = self._calc_sma(close[:-1], 5)  # 基于昨日及之前
cur = close[-1]  # 今日仅用于确认
if cur > ma5[-1]:  # 今日价格与昨日均线比较
```

**注意**：此改动影响所有 21 个策略函数，属于大规模改造。建议在因子优化实施阶段统一处理，而非逐个修补。

### 规则3：回测入场价必须使用次日开盘价

- **要求**：回测的入场价格应为分析日次日的开盘价，而非分析日收盘价
- **原因**：分析报告在收盘后生成，投资者最早只能在次日开盘买入。用当天收盘价回测等于假设你能以收盘价成交
- **检测方法**：回测引擎检查 `start_price` 是否等于 `analysis_date` 次日的开盘价
- **例外**：如果策略明确标注为"收盘前5分钟执行"，可使用当日收盘价，但需加滑点（默认 0.1%）

**实施要点**：

```python
# 当前写法（有未来函数）
start_price = float(start_daily.close)  # 当日收盘价

# 正确写法
next_day = stock_repo.get_next_trading_day(analysis_date)
next_daily = stock_repo.get_daily(code, next_day)
start_price = float(next_daily.open)  # 次日开盘价
```

**滑点处理**：

```python
# 保守估计：次日开盘价 + 0.1% 滑点
slippage = 0.001
start_price = float(next_daily.open) * (1 + slippage)
```

### 规则4：分形识别必须排除未确认区间

- **要求**：缠论分形、波浪理论等需要"未来N根K线确认"的形态识别，必须排除最近 N 根 K 线
- **原因**：分形需要后续K线确认，最近 2 根 K 线的分形可能被错误识别
- **检测方法**：代码审查时检查分形遍历范围是否排除了 `close[-N:]`
- **例外**：无

**实施要点**：

```python
# 当前写法（有未来函数风险）
for i in range(2, len(close) - 2):  # 遍历到倒数第3根
    if high[i] > high[i+1] and high[i] > high[i+2]:
        pivot_highs.append((i, high[i]))

# 正确写法
CONFIRM_BARS = 2  # 需要后续2根K线确认
for i in range(2, len(close) - CONFIRM_BARS):  # 排除未确认区间
    if high[i] > high[i+1] and high[i] > high[i+2]:
        pivot_highs.append((i, high[i]))
```

### 规则5：IC 计算必须错开因子值与收益率的时间窗口

- **要求**：因子值基于 T-1 日数据计算，收益率从 T 日开盘到 T+N 日收盘
- **原因**：如果因子值和收益率都基于当日收盘价，IC 会被高估——因为收盘价既影响了因子值又影响了收益率的起点
- **检测方法**：IC 引擎单元测试验证因子值和收益率的时间窗口不重叠
- **例外**：无

**实施要点**：

```python
# 错误写法
factor_scores = compute_factor_scores(close[:T])  # 包含 T 日收盘
future_returns = (close[T+N] - close[T]) / close[T]  # 从 T 日收盘开始

# 正确写法
factor_scores = compute_factor_scores(close[:T-1])  # 截至 T-1 日
future_returns = (open[T+N] - open[T]) / open[T]  # 从 T 日开盘到 T+N 日收盘
```

### 规则6：幸存者偏差标注

- **要求**：回测数据必须标注是否包含退市股票。如果缺失退市股票数据，必须在回测结果中标注"可能存在幸存者偏差"
- **原因**：退市股票通常表现极差，缺失它们的数据会使回测结果偏乐观
- **检测方法**：回测运行时检查股票池是否包含已退市股票
- **例外**：A 股退市股票数据较难获取，可标注"退市数据不完整"而非强制补全

---

## 自动检测方法

### 未来函数扫描器

计划在 `src/core/data_quality_gate.py` 中实现自动扫描：

```python
class LookAheadBiasScanner:
    """扫描因子计算代码中的未来函数风险"""

    RULES = [
        "close[-1]参与指标计算而非仅用于确认",
        "回测入场价使用当日收盘而非次日开盘",
        "分形识别遍历到未确认区间",
        "IC计算因子值与收益率时间窗口重叠",
        "前复权数据用于回测",
    ]

    def scan_strategy_function(self, func_source: str) -> List[str]:
        """扫描策略函数源码，返回命中的规则列表"""
        violations = []
        # 检测 close[-1] 是否参与 _calc_sma 等指标计算
        # 检测分形遍历范围
        # ...
        return violations
```

### 运行时断言

在选股引擎和回测引擎中添加运行时检查：

```python
# 选股引擎：确保收盘后运行
import datetime
now = datetime.datetime.now()
if now.hour < 15 or (now.hour == 15 and now.minute < 30):
    logger.warning("[Screener] 当前时间 %s 未到收盘后，策略信号可能包含未确定价格", now.strftime("%H:%M"))

# 回测引擎：确保入场价不是当日收盘
if start_price == analysis_day_close:
    logger.warning("[Backtest] 入场价等于分析日收盘价，可能存在未来函数")
```

---

## 检查清单

每次修改因子计算或回测代码时，必须逐项确认：

- [ ] 回测是否使用不复权数据？
- [ ] 策略信号是否基于 T-1 日数据计算？
- [ ] 回测入场价是否为次日开盘价（含滑点）？
- [ ] 分形识别是否排除了未确认区间？
- [ ] IC 计算的因子值与收益率时间窗口是否错开？
- [ ] 回测结果是否标注了幸存者偏差？
- [ ] 新增因子是否通过了未来函数扫描器检查？
- [ ] 盘中运行时是否有运行时间警告？
