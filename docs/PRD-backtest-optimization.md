# PRD: daily_stock_analysis 回测系统优化

> **项目**: daily_stock_analysis  
> **版本**: v1.0  
> **日期**: 2026-04-29  
> **作者**: 高级开发者 Agent  
> **框架**: Harness 开发框架  
> **状态**: Draft

---

## 目录

1. [背景与动机](#1-背景与动机)
2. [现状分析](#2-现状分析)
3. [竞品深度调研](#3-竞品深度调研)
4. [核心发现与对比矩阵](#4-核心发现与对比矩阵)
5. [产品目标与成功指标](#5-产品目标与成功指标)
6. [功能需求详述](#6-功能需求详述)
7. [技术架构设计](#7-技术架构设计)
8. [数据模型设计](#8-数据模型设计)
9. [API 接口设计](#9-api-接口设计)
10. [实施路线图](#10-实施路线图)
11. [风险评估与缓解](#11-风险评估与缓解)
12. [测试策略](#12-测试策略)
13. [附录](#13-附录)
14. [前端功能布局与实现细节](#14-前端功能布局与实现细节)
15. [后端功能布局与实现细节](#15-后端功能布局与实现细节)
16. [Agent 开发规则（Harness 框架扩展）](#16-agent-开发规则harness-框架扩展)
17. [验收检查清单](#17-验收检查清单)
18. [透明度与用户可理解性体系](#18-透明度与用户可理解性体系)

---

## 1. 背景与动机

### 1.1 问题描述

daily_stock_analysis 当前的回测系统存在严重的功能缺陷和架构问题：

1. **回测逻辑过于简单**：仅对历史 AI 分析记录做"方向准确率"事后验证，缺乏真实的策略回测能力
2. **模块边界模糊**：回测逻辑分散在 `src/alpha/portfolio_simulator.py`、API 层和前端，职责不清
3. **策略执行引擎缺失**：YAML 定义的策略由 AI Agent 自然语言解读执行，无法精确量化回测
4. **指标体系薄弱**：仅支持方向准确率、胜率、平均收益率、止盈止损触发率，缺少专业风险指标
5. **无可视化**：没有权益曲线、回撤图、交易标记等回测可视化
6. **无参数优化**：策略因子虽定义了范围和步长，但没有优化器来搜索最优参数

### 1.2 商业价值

优化回测系统将带来：

- **策略可信度提升**：从"AI 说看多"的模糊判断，变为"回测夏普 1.2、最大回撤 8%"的量化证明
- **用户决策质量**：用历史数据量化每个策略的真实表现，避免"感觉好"的主观偏见
- **产品差异化**：从"AI 分析推送工具"升级为"AI + 量化回测一体化平台"
- **生态扩展基础**：回测引擎是策略市场、实盘模拟等高级功能的基础设施

---

## 2. 现状分析

### 2.1 当前回测架构

```
当前架构（问题标注）：

┌──────────────────────────────────────────┐
│  AI 分析流程                               │
│  main.py → analyzer_service.py → LLM      │
│    ↓ 生成 AnalysisHistory                  │
├──────────────────────────────────────────┤
│  回测触发（API/自动）                       │
│  /api/v1/backtest/run                      │
│    ↓ ⚠️ 仅验证历史记录                      │
├──────────────────────────────────────────┤
│  回测评估逻辑                               │
│  ⚠️ 硬编码在 API 层                        │
│  ⚠️ 方向推断规则写死                        │
│  ⚠️ 无策略执行引擎                         │
├──────────────────────────────────────────┤
│  输出                                      │
│  direction_accuracy_pct / win_rate_pct     │
│  avg_simulated_return_pct                  │
│  ⚠️ 无权益曲线/回撤图/交易明细              │
└──────────────────────────────────────────┘
```

### 2.2 当前能力 vs 应有能力

| 能力维度 | 当前状态 | 行业标准（3个竞品共识） | 差距 |
|----------|---------|----------------------|------|
| 策略定义 | YAML 自然语言 + AI 解读 | 编程式策略基类 (init/next) | 🔴 严重 |
| 订单类型 | 无 | 市价/限价/止损/止盈/追踪止损 | 🔴 严重 |
| 交易成本 | 无 | 可配置佣金/滑点/保证金 | 🔴 严重 |
| 绩效指标 | 6个基础指标 | 25+ 专业指标 | 🔴 严重 |
| 可视化 | 无 | 交互式 HTML 报告 + 权益曲线 | 🔴 严重 |
| 参数优化 | 无 | 网格搜索 + 贝叶斯优化 | 🟡 缺失 |
| 多标的 | 单股验证 | 多标的组合回测 | 🟡 缺失 |
| 风险管理 | 无 | 止损/追踪止损/仓位管理/风险模型 | 🔴 严重 |
| 蒙特卡洛 | 无 | 随机数据鲁棒性测试 | 🟡 缺失 |
| 回测报告 | API JSON | HTML 交互报告 + Tearsheet | 🔴 严重 |

### 2.3 当前策略 YAML 格式分析

当前 YAML 格式有 `factors` 字段定义了可参数化的因子，这是非常好的设计基础：

```yaml
# strategies/ma_golden_cross.yaml 中的 factors 段
factors:
  - id: short_window
    type: int
    default: 5
    range: [3, 10]
    step: 1
  - id: mid_window
    type: int
    default: 20
    range: [10, 30]
    step: 5
  # ...
```

**关键洞察**：YAML 策略的 `factors` 段天然具备参数优化所需的定义（类型、范围、步长），只需补全执行引擎和优化器即可。

---

## 3. 竞品深度调研

### 3.1 backtesting.py — 事件驱动回测引擎

#### 3.1.1 核心架构

```
┌─────────────────────────────────────────────┐
│              Backtest 主类                     │
│  __init__(data, strategy, cash, commission,   │
│           margin, trade_on_close, hedging,    │
│           exclusive_orders, finalize_trades)  │
├─────────────────────────────────────────────┤
│              Strategy 抽象基类                 │
│  init()  → 指标声明 (self.I)                  │
│  next()  → 每根 K 线的交易逻辑                 │
│  buy(size, limit, stop, sl, tp, tag)         │
│  sell(size, limit, stop, sl, tp, tag)        │
├─────────────────────────────────────────────┤
│              _Broker 模拟经纪商                │
│  _process_orders()  → 订单撮合引擎             │
│  保证金计算 / 破产检测 / FIFO 平仓              │
├─────────────────────────────────────────────┤
│              _Stats 统计模块                   │
│  compute_stats() → 25+ 绩效指标               │
│  Sharpe / Sortino / Calmar / Alpha / Beta    │
│  Max DD / CAGR / Kelly / SQN / Profit Factor │
├─────────────────────────────────────────────┤
│              _Plotting 可视化                  │
│  交互式 HTML 报告 (Bokeh)                      │
│  权益曲线 / 回撤图 / 交易标记 / 指标叠加        │
└─────────────────────────────────────────────┘
```

#### 3.1.2 核心特色功能

**① Strategy 基类 + `self.I()` 指标注册**

```python
class SmaCross(Strategy):
    def init(self):
        self.ma1 = self.I(SMA, self.data.Close, 10)  # 自动管理+绘图
        self.ma2 = self.I(SMA, self.data.Close, 20)
    
    def next(self):
        if crossover(self.ma1, self.ma2):
            self.buy()
```

- `self.I()` 包装器自动注册指标，框架管理指标计算和绘图
- `self.data` 提供统一的 OHLCV 数据访问接口
- 策略逻辑完全由用户控制，框架只提供基础设施

**② 完整的订单体系**

```python
# 市价单
self.buy(size=1.0)

# 限价单
self.buy(limit=100.5, size=1.0)

# 带止损止盈
self.buy(sl=95.0, tp=110.0)

# 带关联止损止盈的限价挂单
self.buy(limit=100.5, sl=95.0, tp=110.0, tag="突破入场")

# 带止损触发价的挂单
self.buy(stop=101.0, sl=95.0, tp=110.0)
```

- `Order` 对象支持 `size`、`limit`、`stop`、`sl`、`tp`、`tag` 完整参数
- 关联订单（contingent orders）：主单成交后自动挂 SL/TP 单
- `exclusive_orders=True` 保证新订单自动平旧仓

**③ 内置优化器**

```python
stats = bt.optimize(
    fast=range(5, 30, 5),
    slow=range(10, 60, 5),
    maximize='Sharpe Ratio',      # 优化目标
    method='grid',                # 网格搜索 or 'sambo'(贝叶斯)
    max_tries=200,
    constraint=lambda p: p.fast < p.slow,  # 约束条件
    return_heatmap=True,          # 返回热力图数据
    return_optimization=True,     # 返回优化过程
)
```

- 支持网格搜索和 `sambo`（贝叶斯优化）
- 多进程并行
- 热力图可视化（`plot_heatmaps()`）
- 自定义约束条件

**④ 专业级统计指标（25+）**

| 维度 | 指标 |
|------|------|
| 收益 | Return, Return(Ann.), CAGR, Buy & Hold Return |
| 风险 | Volatility(Ann.), Max Drawdown, Avg Drawdown, Drawdown Duration |
| 风险调整 | Sharpe Ratio, Sortino Ratio, Calmar Ratio |
| CAPM | Alpha, Beta |
| 交易 | # Trades, Win Rate, Best/Worst Trade, Avg Trade, Profit Factor, SQN, Kelly Criterion |
| 暴露 | Exposure Time |

**⑤ lib.py 可组合策略**

```python
class SignalStrategy(Strategy):   # 向量化信号策略
    def set_signal(self, entry_size, exit_portion)

class TrailingStrategy(Strategy):  # ATR 追踪止损策略
    def set_trailing_sl(self, n_atr=6)
    def set_trailing_pct(self, pct=0.05)

class FractionalBacktest(Backtest): # 小数份额交易
class MultiBacktest:                # 多品种并行回测
```

**⑥ 蒙特卡洛模拟**

```python
random_data = random_ohlc_data(example_data, frac=1.0)
for data in random_data:
    stats = Backtest(data, MyStrategy).run()
```

**⑦ 多时间框架支持**

```python
self.sma = resample_apply('D', SMA, self.data.Close, 10)
```

#### 3.1.3 不足

- 单标的回测（`MultiBacktest` 只是简单并行包装）
- 不支持组合级别回测（无投资组合构建、权重分配）
- 无风险管理模块
- 无信号与组合的解耦架构
- AGPL-3.0 许可证限制

---

### 3.2 mizar-alpha — 向量相似性回测框架

#### 3.2.1 核心架构

```
┌─────────────────────────────────────────────┐
│          预测信号生成管线                       │
│  52个技术指标 → PCA降维 → ChromaDB向量检索     │
│  → Top-K相似状态 → 收益分布统计 → 预测信号      │
├─────────────────────────────────────────────┤
│          Strategy (v0.2 基础版)               │
│  should_open() → 多维信号开仓                  │
│  step() → 核心执行逻辑                        │
│  should_close_by_signal_or_days()            │
│  should_stop_out() → 止损止盈                 │
├─────────────────────────────────────────────┤
│          Strategy Pro (v0.2 增强版)            │
│  _check_open_conditions() → 信号过滤+仓位      │
│  _check_exit_conditions() → 多规则平仓优先级    │
│  ExitRule → 平仓规则数据类                     │
│  force_close() → 回测结束强制平仓              │
├─────────────────────────────────────────────┤
│          ParamPresets 参数预设                  │
│  ActivityLevel × CapSize → 16种预设组合        │
│  蓝筹/成长/科技小盘/量化活跃                     │
├─────────────────────────────────────────────┤
│          metrics 绩效计算                      │
│  calculate_metrics() → 基础指标+绘图           │
│  plot_net_value_with_price() → 双轴可视化      │
└─────────────────────────────────────────────┘
```

#### 3.2.2 核心特色功能

**① 多维信号开仓过滤**

```python
def _check_open_conditions(self, prediction):
    prob = prediction.get('up_probability', 0)
    if prob < self.threshold:       # 概率阈值
        return False, 0.0
    if prediction.get('confidence', 0) < self.min_confidence:  # 置信度过滤
        return False, 0.0
    if prediction.get('avg_ret_5d', 0) < self.min_ret_5d:     # 5日预期收益过滤
        return False, 0.0
    return True, pct
```

- 三层过滤：概率阈值 → 置信度 → 预期收益
- 仓位管理：`full`（满仓）vs `signal`（按信号强度比例）
- 与 daily_stock_analysis 的 AI 预测场景天然契合

**② 多规则平仓优先级系统**

```python
# 平仓优先级（从高到低）：
1. trailing_stop_pct  → 移动止损（从最高点回撤）
2. take_profit_pct    → 目标止盈（可部分止盈 50%）
3. signal_lost/fixed_days → 信号消失或固定天数
4. max_hold_days      → 最大持仓天数强制平仓
```

- `exit_reason` 记录每笔交易的平仓原因（trailing_stop / take_profit / fixed_days / signal_lost / max_hold_days / force_close）
- 部分止盈支持：`partial_exit_enabled=True` 时止盈只平 50%

**③ 参数预设系统 (ParamPresets)**

```python
# 活跃度 × 市值 → 参数组合
ActivityLevel  CapSize      threshold  trailing_stop  take_profit
LOW × LARGE    (蓝筹)       0.45       0.03           0.04
MEDIUM × MID   (成长中盘)   0.55       0.05           0.08
HIGH × SMALL   (科技小盘)   0.62       0.08           0.18
EXTREME × SMALL(量化活跃)   0.65       0.10           0.20
```

- 核心设计理念：**活跃度越高、市值越小，参数越保守**
- 16 种预设组合覆盖 A 股主要品种
- 便捷别名：`blue_chip()` / `growth_mid()` / `tech_small()` / `quant_active()`

**④ 基于 backtesting.py 的封装**

- 底层使用 `backtesting.py` 作为回测执行引擎
- 自定义信号生成器接入向量相似性预测
- 输出交互式 HTML 报告

**⑤ 净值与价格双轴可视化**

- 左轴：策略净值曲线
- 右轴：归一化价格曲线
- 开仓点标记（红色散点）

#### 3.2.3 不足

- 单标的回测
- 统计指标较少（仅 8 个核心指标，缺少 Sortino/Calmar/Alpha/Beta 等）
- 无参数优化器
- 无多时间框架支持
- 无投资组合级别的回测
- 数据加载器极其简陋（单函数，无异常处理）

---

### 3.3 QSTrader — 计划驱动组合回测引擎

#### 3.3.1 核心架构

```
┌─────────────────────────────────────────────┐
│          TradingSession (系统编排层)           │
│  协调所有组件的生命周期和交互                   │
├─────────────────────────────────────────────┤
│          Simulation Engine (模拟引擎)          │
│  sim_engine.py → 事件驱动主循环               │
│  daily_bday.py → 工作日调度器                 │
│  event.py → 事件类型定义                      │
├─────────────────────────────────────────────┤
│          Alpha Model (信号生成层)              │
│  产生交易信号，与组合构建完全解耦                │
├─────────────────────────────────────────────┤
│          Risk Model (风险模型层)               │
│  风险约束、仓位限制、波动率控制                  │
├─────────────────────────────────────────────┤
│          Portfolio Construction (组合构建层)   │
│  PCM (组合构建管理器)                          │
│    ├── Optimiser → 资产权重优化                │
│    └── Order Sizer → 实际下单规模              │
├─────────────────────────────────────────────┤
│          Execution (执行层)                    │
│  订单执行逻辑                                 │
├─────────────────────────────────────────────┤
│          Broker (模拟经纪层)                   │
│  simulated_broker.py → 模拟券商               │
│    ├── Fee Model → 手续费模型                  │
│    ├── Portfolio → 投资组合管理                │
│    └── Transaction → 交易记录                  │
├─────────────────────────────────────────────┤
│          Statistics (统计层)                   │
│  statistics.py → 统计基类                     │
│  performance.py → 绩效指标计算                 │
│  json_statistics.py → JSON 输出               │
│  tearsheet.py → Tearsheet 报告                │
├─────────────────────────────────────────────┤
│          Data (数据层)                         │
│  行情数据加载与处理                             │
└─────────────────────────────────────────────┘
```

#### 3.3.2 核心特色功能

**① 五层解耦架构**

QSTrader 最独特的设计是信号生成→风险管理→组合构建→执行→经纪的**完全解耦**：

```
Alpha Model (信号) → Risk Model (风控) → PCM (组合) → Execution (执行) → Broker (经纪)
```

- 每层可独立替换、继承或完全自定义
- 信号生成不知道组合如何构建，组合构建不知道信号如何生成
- 这种解耦使得回测各环节可独立测试和迭代

**② 计划驱动 (Schedule-Driven) 组合构建**

```python
# 不同于传统的逐 bar 策略，QSTrader 支持基于时间表的再平衡
# 例如：每月末再平衡到 60/40 比例
```

- 定时再平衡（月末/季末/自定义周期）
- 目标权重驱动的组合构建
- 适合资产配置和系统性策略

**③ 完整的经纪商模拟**

- `broker.py` → 基类接口
- `simulated_broker.py` → 模拟实现
- `fee_model/` → 手续费模型（佣金/滑点/融资利率）
- `portfolio/` → 投资组合（持仓/现金/净值/盈亏）
- `transaction/` → 交易记录追踪

**④ Tearsheet 报告**

- 类似 Quantopian 风格的完整策略分析报告
- JSON 格式输出，便于集成
- 绩效指标 + 可视化图表

**⑤ 工作日调度器**

- 基于工作日频率生成仿真事件
- 跳过周末和节假日
- 确保只在交易日运行模拟

#### 3.3.3 不足

- 架构过于重型，学习曲线陡峭
- 不适合简单的单标的策略回测
- 文档较少，社区活跃度低
- 无内置参数优化
- 可视化不如 backtesting.py 丰富
- 安装配置较复杂

---

## 4. 核心发现与对比矩阵

### 4.1 共性核心功能（三个项目均已实现）

| 功能 | backtesting.py | mizar-alpha | qstrader | 重要性 |
|------|:-:|:-:|:-:|:-:|
| K 线数据驱动 | ✅ | ✅ | ✅ | 🔴 关键 |
| 策略抽象基类 | ✅ Strategy.init/next | ✅ Strategy.step | ✅ AlphaModel | 🔴 关键 |
| 模拟经纪商/订单执行 | ✅ _Broker | ✅ (简化版) | ✅ SimulatedBroker | 🔴 关键 |
| 手续费模拟 | ✅ commission | ✅ fee_rate | ✅ FeeModel | 🔴 关键 |
| 止损/止盈 | ✅ sl/tp | ✅ stop_loss/take_profit | ✅ (via RiskModel) | 🔴 关键 |
| 追踪止损 | ✅ TrailingStrategy | ✅ trailing_stop_pct | ❌ | 🟡 重要 |
| 绩效指标计算 | ✅ 25+ 指标 | ✅ 8 指标 | ✅ Performance | 🔴 关键 |
| 权益曲线 | ✅ _equity_curve | ✅ net_values | ✅ Portfolio | 🔴 关键 |
| 回撤计算 | ✅ compute_drawdown | ✅ max_drawdown | ✅ | 🔴 关键 |
| 交易记录 | ✅ _trades DataFrame | ✅ trades list | ✅ Transaction | 🔴 关键 |
| 回测结果可视化 | ✅ HTML(Bokeh) | ✅ Matplotlib | ✅ Tearsheet | 🔴 关键 |

### 4.2 特色功能（仅个别项目实现）

| 特色功能 | 来源项目 | 价值评估 | 适配难度 |
|----------|----------|----------|----------|
| 参数优化器（网格+贝叶斯） | backtesting.py | ⭐⭐⭐⭐⭐ 极高 | 🟡 中 |
| 热力图可视化 | backtesting.py | ⭐⭐⭐⭐ 高 | 🟡 中 |
| 多时间框架 (resample_apply) | backtesting.py | ⭐⭐⭐ 中 | 🟢 低 |
| 蒙特卡洛模拟 | backtesting.py | ⭐⭐⭐⭐ 高 | 🟢 低 |
| 可组合策略 (SignalStrategy/TrailingStrategy) | backtesting.py | ⭐⭐⭐⭐ 高 | 🟢 低 |
| 多品种并行 (MultiBacktest) | backtesting.py | ⭐⭐⭐ 中 | 🟡 中 |
| 小数份额交易 (FractionalBacktest) | backtesting.py | ⭐⭐ 低 | 🟢 低 |
| 多维信号过滤（概率+置信度+预期收益） | mizar-alpha | ⭐⭐⭐⭐⭐ 极高 | 🟢 低 |
| 仓位管理（full/signal） | mizar-alpha | ⭐⭐⭐⭐ 高 | 🟢 低 |
| 多规则平仓优先级 | mizar-alpha | ⭐⭐⭐⭐⭐ 极高 | 🟢 低 |
| 部分止盈 | mizar-alpha | ⭐⭐⭐ 中 | 🟢 低 |
| 参数预设系统（活跃度×市值） | mizar-alpha | ⭐⭐⭐⭐⭐ 极高 | 🟢 低 |
| 平仓原因记录 | mizar-alpha | ⭐⭐⭐⭐ 高 | 🟢 低 |
| 五层解耦架构 | qstrader | ⭐⭐⭐⭐ 高 | 🔴 高 |
| 计划驱动组合构建 | qstrader | ⭐⭐⭐ 中 | 🔴 高 |
| 投资组合优化器 | qstrader | ⭐⭐⭐ 中 | 🔴 高 |
| 风险模型层 | qstrader | ⭐⭐⭐⭐ 高 | 🟡 中 |
| Tearsheet 报告 | qstrader | ⭐⭐⭐⭐ 高 | 🟡 中 |
| 工作日调度器 | qstrader | ⭐⭐ 低 | 🟢 低 |

### 4.3 适配 daily_stock_analysis 的优先级判断

基于 daily_stock_analysis 项目的特点（AI 驱动、A股为主、YAML 策略框架已有），适配优先级：

```
P0（必须实现）：
  ├── 策略执行引擎（将 YAML 策略转为可回测的 Strategy 类）
  ├── 模拟经纪商（订单管理、撮合、手续费）
  ├── 多规则平仓系统（移动止损/止盈/信号消失/固定天数/最大持仓）
  ├── 多维信号开仓过滤（概率/置信度/预期收益 三层过滤）
  ├── 专业绩效指标（25+ 指标体系）
  ├── 回测可视化（HTML 交互报告 + 权益曲线 + 回撤图）
  └── 参数预设系统（活跃度×市值 → 参数组合）

P1（应该实现）：
  ├── 参数优化器（网格搜索 + 热力图）
  ├── 追踪止损（ATR/百分比）
  ├── 仓位管理（full/signal/kelly）
  ├── 蒙特卡洛模拟
  └── 平仓原因记录与统计

P2（可以延后）：
  ├── 多时间框架
  ├── 多标的组合回测
  ├── 投资组合优化器
  ├── 风险模型层
  └── 计划驱动再平衡
```

---

## 5. 产品目标与成功指标

### 5.1 产品目标

**将 daily_stock_analysis 的回测系统从"事后验证工具"升级为"专业量化回测引擎"，同时保留 AI 驱动和 YAML 策略框架的核心优势。**

### 5.2 成功指标

| 指标 | 当前值 | 目标值 | 衡量方式 |
|------|--------|--------|----------|
| 可回测的策略数量 | 0（仅方向验证） | 11+（所有 YAML 策略） | 策略可执行回测 |
| 绩效指标数量 | 6 | 25+ | 指标清单 |
| 回测报告格式 | API JSON | HTML 交互报告 | 输出格式 |
| 参数优化能力 | 无 | 网格+贝叶斯 | 优化器可用 |
| 回测执行速度 | N/A | 1年日线 < 5s | 基准测试 |
| 策略参数预设 | 无 | 16 种（4活跃度×4市值） | 预设库 |
| 平仓规则类型 | 1（止盈止损） | 5+（移动止损/目标止盈/信号消失/固定天数/最大持仓） | 规则类型 |

---

## 6. 功能需求详述

### 6.1 P0：策略执行引擎

#### FR-001: Strategy 基类定义

**描述**：定义回测策略的抽象基类，统一策略接口。

**详细规格**：

```python
class BacktestStrategy(ABC):
    """回测策略抽象基类"""
    
    # ---- 必须实现 ----
    @abstractmethod
    def init(self):
        """初始化策略，声明指标和参数"""
        pass
    
    @abstractmethod
    def next(self):
        """每根 K 线调用一次，实现交易逻辑"""
        pass
    
    # ---- 数据访问 ----
    @property
    def data(self) -> OHLCVData:
        """当前回测数据的访问接口"""
        pass
    
    # ---- 指标注册 ----
    def I(self, func, *args, name=None, plot=True, overlay=True, color=None, **kwargs):
        """注册指标函数，框架自动管理计算和绘图"""
        pass
    
    # ---- 订单接口 ----
    def buy(self, size=None, limit=None, stop=None, sl=None, tp=None, tag=None) -> Order:
        """下多单"""
        pass
    
    def sell(self, size=None, limit=None, stop=None, sl=None, tp=None, tag=None) -> Order:
        """下空单"""
        pass
    
    # ---- 持仓信息 ----
    @property
    def position(self) -> Position:
        """当前持仓"""
        pass
    
    @property
    def equity(self) -> float:
        """当前权益（现金+持仓市值）"""
        pass
    
    @property
    def trades(self) -> Tuple[Trade, ...]:
        """活跃交易"""
        pass
    
    @property
    def closed_trades(self) -> Tuple[Trade, ...]:
        """已结算交易"""
        pass
    
    @property
    def orders(self) -> Tuple[Order, ...]:
        """等待执行的订单"""
        pass
```

**验收标准**：
- [ ] 用户可通过继承 `BacktestStrategy` 实现自定义策略
- [ ] `init()` 和 `next()` 方法在回测中被正确调用
- [ ] `self.I()` 注册的指标自动计算并可在可视化中绘制
- [ ] `buy()`/`sell()` 创建的订单在下一根 K 线被处理

#### FR-002: YAML 策略到 Strategy 的桥接

**描述**：将现有的 YAML 策略自动转换为可执行的 Strategy 子类。

**详细规格**：

```python
class YAMLStrategy(BacktestStrategy):
    """YAML 策略的 Strategy 适配器"""
    
    def __init__(self, yaml_path: str, factors: dict = None):
        """
        参数:
            yaml_path: YAML 策略文件路径
            factors: 因子覆盖值，如 {'short_window': 10, 'mid_window': 30}
        """
        pass
    
    def init(self):
        """解析 YAML，注册因子为指标"""
        # 1. 加载 YAML 定义
        # 2. 根据 factors 段注册 self.I() 指标
        # 3. 设置默认参数
        pass
    
    def next(self):
        """根据 YAML instructions 和因子值执行交易逻辑"""
        # 1. 读取已注册指标值
        # 2. 应用 scoring rules（来自 instructions）
        # 3. 根据 score 执行 buy/sell
        pass
```

**桥接策略**：

```python
# 自动桥接：YAML → Strategy
strategy_cls = yaml_to_strategy("strategies/ma_golden_cross.yaml")
bt = Backtest(data, strategy_cls, cash=100000)
stats = bt.run(short_window=10, mid_window=30)
```

**验收标准**：
- [ ] 所有 21 个 YAML 策略可自动转换为 Strategy 子类
- [ ] YAML 中的 `factors` 段正确映射为 Strategy 的可调参数
- [ ] YAML 中的 `instructions` 段的评分规则被正确执行
- [ ] 因子覆盖（factors 参数）正确替换默认值

#### FR-003: AI 预测信号策略

**描述**：支持 AI 分析结果作为回测信号输入（类 mizar-alpha 的多维信号）。

**详细规格**：

```python
class AIPredictionStrategy(BacktestStrategy):
    """AI 预测信号驱动策略"""
    
    def __init__(self, 
                 threshold: float = 0.55,
                 min_confidence: float = None,
                 min_ret_5d: float = None,
                 position_sizing: str = 'full'):
        pass
    
    def init(self):
        """加载 AI 预测历史数据"""
        pass
    
    def next(self):
        """根据当日 AI 预测信号执行交易"""
        # 获取当日 AI 预测（up_probability, confidence, avg_ret_5d）
        # 三层过滤：概率阈值 → 置信度 → 预期收益
        # 仓位计算：full(1.0) 或 signal(概率×置信度)
        pass
```

**验收标准**：
- [ ] 支持 AI 预测信号作为回测输入
- [ ] 三层过滤条件（概率/置信度/预期收益）独立可配
- [ ] `full` 和 `signal` 两种仓位模式正确工作
- [ ] 与现有 `AnalysisHistory` 数据兼容

---

### 6.2 P0：模拟经纪商

#### FR-004: 订单管理

**描述**：完整的订单生命周期管理。

**数据结构**：

```python
@dataclass
class Order:
    size: float           # 正数=多单，负数=空单
    limit: float = None   # 限价
    stop: float = None    # 触发价
    sl: float = None      # 止损价（关联订单）
    tp: float = None      # 止盈价（关联订单）
    tag: str = None       # 自定义标签
    
    # 只读属性
    is_long: bool         # 是否多单
    is_short: bool        # 是否空单
    is_contingent: bool   # 是否关联订单
    
    def cancel(self):
        """取消订单"""
        pass

@dataclass
class Trade:
    size: float
    entry_price: float
    exit_price: float = None
    entry_bar: int = 0
    exit_bar: int = 0
    entry_time: datetime = None
    exit_time: datetime = None
    sl: float = None      # 可动态修改
    tp: float = None      # 可动态修改
    tag: str = None
    
    @property
    def pl(self) -> float:
        """盈亏金额"""
        pass
    
    @property
    def pl_pct(self) -> float:
        """盈亏百分比"""
        pass
    
    def close(self, portion: float = 1.0):
        """平仓（支持部分平仓）"""
        pass

@dataclass
class Position:
    size: float            # 正数=多头，负数=空头
    entry_price: float
    
    @property
    def pl(self) -> float: pass
    
    @property
    def pl_pct(self) -> float: pass
    
    @property
    def is_long(self) -> bool: pass
    
    @property
    def is_short(self) -> bool: pass
    
    def close(self, portion: float = 1.0): pass
```

**验收标准**：
- [ ] 市价单、限价单、止损触发单正确执行
- [ ] 关联订单（SL/TP）在主单成交后自动挂出
- [ ] 部分平仓功能正确
- [ ] 订单取消功能正确
- [ ] `exclusive_orders` 模式正确（新订单自动平旧仓）

#### FR-005: 交易成本模型

**描述**：可配置的交易成本模拟。

**规格**：

```python
class Backtest:
    def __init__(self,
                 data,
                 strategy,
                 cash: float = 100000,
                 commission: float = 0.0003,    # 佣金率（双边万三）
                 slippage: float = 0.001,        # 滑点率
                 stamp_duty: float = 0.001,      # 印花税（A股卖出千一）
                 min_commission: float = 5.0,    # 最低佣金（元）
                 margin: float = 1.0,            # 保证金率
                 ):
        pass
```

**A股特殊规则**：
- 印花税：卖出时收取 0.1%
- 佣金：双向收取，最低 5 元
- 滑点：按比例模拟，开仓滑高、平仓滑低

**验收标准**：
- [ ] 佣金双向正确扣除
- [ ] 印花税卖出时正确扣除
- [ ] 最低佣金限制生效
- [ ] 滑点模拟正确影响成交价
- [ ] 交易成本在绩效统计中正确反映

#### FR-006: 订单撮合引擎

**描述**：模拟真实交易的订单撮合逻辑。

**撮合规则**：

| 订单类型 | 触发条件 | 成交价格 |
|----------|---------|---------|
| 市价买 | 当前 bar | 开盘价（默认）或收盘价（trade_on_close） |
| 市价卖 | 当前 bar | 开盘价（默认）或收盘价（trade_on_close） |
| 限价买 | 价格 ≤ limit | limit 价格 |
| 限价卖 | 价格 ≥ limit | limit 价格 |
| 止损触发买 | 价格 ≥ stop | stop 价格 |
| 止损触发卖 | 价格 ≤ stop | stop 价格 |
| 止损单(SL) | 价格 ≤ sl | sl 价格 |
| 止盈单(TP) | 价格 ≥ tp | tp 价格 |

**特殊处理**：
- 一根 K 线内 SL/TP 同时触发时，SL 优先
- 跳空缺口时，以实际可成交价格执行
- 破产检测：权益 ≤ 0 时停止回测

**验收标准**：
- [ ] 所有订单类型正确撮合
- [ ] SL/TP 优先级正确
- [ ] 跳空缺口场景正确处理
- [ ] 破产场景正确处理
- [ ] 非对冲模式下 FIFO 平仓正确

---

### 6.3 P0：多规则平仓系统

#### FR-007: 平仓规则引擎

**描述**：支持多种平仓规则的灵活组合，按优先级依次检查。

**平仓规则定义**：

```python
@dataclass
class ExitRule:
    """平仓规则配置"""
    signal_threshold: float           # 信号消失阈值
    fixed_days: int = None            # 固定持仓天数
    trailing_stop_pct: float = None   # 移动止损回撤百分比
    trailing_stop_atr: float = None   # 移动止损 ATR 倍数
    take_profit_pct: float = None     # 目标止盈百分比
    stop_loss_pct: float = None       # 固定止损百分比
    max_hold_days: int = None         # 最大持仓天数
    partial_exit_pct: float = 1.0     # 部分平仓比例（0~1）
```

**优先级顺序**：

```
1. 固定止损 (stop_loss_pct)        → 全平
2. 移动止损 (trailing_stop_pct/atr) → 全平
3. 目标止盈 (take_profit_pct)      → 可部分平仓
4. 信号消失 (signal_threshold)     → 全平
5. 固定天数 (fixed_days)           → 全平
6. 最大持仓天数 (max_hold_days)    → 全平
```

**平仓原因枚举**：

```python
class ExitReason(Enum):
    STOP_LOSS = 'stop_loss'
    TRAILING_STOP = 'trailing_stop'
    TAKE_PROFIT = 'take_profit'
    PARTIAL_TAKE_PROFIT = 'partial_take_profit'
    SIGNAL_LOST = 'signal_lost'
    FIXED_DAYS = 'fixed_days'
    MAX_HOLD_DAYS = 'max_hold_days'
    FORCE_CLOSE = 'force_close'
```

**验收标准**：
- [ ] 所有 8 种平仓规则独立可配
- [ ] 优先级顺序严格执行
- [ ] 移动止损从持仓最高点计算回撤
- [ ] 部分止盈正确减少持仓比例
- [ ] 每笔交易记录平仓原因
- [ ] 回测结束时未平仓位自动强制平仓

---

### 6.4 P0：多维信号开仓过滤

#### FR-008: AI 信号过滤系统

**描述**：支持基于 AI 预测信号的多维开仓过滤。

**过滤维度**：

| 维度 | 参数 | 默认值 | 说明 |
|------|------|--------|------|
| 上涨概率 | threshold | 0.55 | 低于阈值不开仓 |
| 置信度 | min_confidence | None | 低于阈值不开仓 |
| 5日预期收益 | min_ret_5d | None | 低于阈值不开仓 |
| 评分 | min_score | None | 低于阈值不开仓 |
| 风险等级 | max_risk_level | None | 高于阈值不开仓 |

**仓位管理**：

```python
class PositionSizing(Enum):
    FULL = 'full'          # 满仓
    SIGNAL = 'signal'      # 按信号强度（概率×置信度）
    KELLY = 'kelly'        # 凯利公式
    FIXED = 'fixed'        # 固定比例
    EQUAL_RISK = 'equal'   # 等风险（ATR反算）
```

**验收标准**：
- [ ] 5 个过滤维度独立可配
- [ ] 4 种仓位管理模式正确计算
- [ ] 仓位比例在交易记录中正确记录
- [ ] 过滤条件可组合使用

---

### 6.5 P0：专业绩效指标

#### FR-009: 指标计算引擎

**描述**：实现 25+ 专业级回测绩效指标。

**指标体系**：

| 维度 | 指标 | 公式/说明 |
|------|------|-----------|
| **基础** | Start / End | 回测起止时间 |
| | Duration | 回测持续时间 |
| | Exposure Time [%] | 有持仓时间占比 |
| **收益** | Return [%] | 总收益率 |
| | Return (Ann.) [%] | 年化收益率 |
| | CAGR [%] | 复合年化增长率 |
| | Buy & Hold Return [%] | 买入持有收益率 |
| **风险** | Volatility (Ann.) [%] | 年化波动率 |
| | Max Drawdown [%] | 最大回撤 |
| | Avg Drawdown [%] | 平均回撤 |
| | Max DD Duration | 最大回撤持续时间 |
| | Avg DD Duration | 平均回撤持续时间 |
| **风险调整** | Sharpe Ratio | (年化收益-无风险利率) / 年化波动率 |
| | Sortino Ratio | (年化收益-无风险利率) / 下行标准差 |
| | Calmar Ratio | 年化收益 / 最大回撤 |
| **CAPM** | Alpha [%] | 超额收益（扣除市场风险后） |
| | Beta | 与市场的系统性风险暴露 |
| **交易** | # Trades | 交易次数 |
| | Win Rate [%] | 胜率 |
| | Best Trade [%] | 最佳单笔收益 |
| | Worst Trade [%] | 最差单笔收益 |
| | Avg Trade [%] | 平均单笔收益（几何平均） |
| | Max Trade Duration | 最长持仓时间 |
| | Avg Trade Duration | 平均持仓时间 |
| | Profit Factor | 盈利交易总利润 / 亏损交易总亏损 |
| | Expectancy [%] | 期望收益 |
| | SQN | System Quality Number |
| | Kelly Criterion | 凯利最优仓位比例 |
| **成本** | Commissions [$] | 总手续费 |
| **A股扩展** | 换手率 | 总交易量 / 平均持仓市值 |
| | 日胜率 | 日度盈利天数占比 |
| | 盈亏比 | 平均盈利 / 平均亏损 |

**验收标准**：
- [ ] 所有 25+ 指标计算正确
- [ ] 指标与 backtesting.py 的 `compute_stats()` 结果一致（同一数据集）
- [ ] 无风险利率可配置
- [ ] A 股扩展指标正确实现

---

### 6.6 P0：回测可视化

#### FR-010: HTML 交互式报告

**描述**：生成包含图表的交互式 HTML 回测报告。

**报告结构**：

```
┌─────────────────────────────────────┐
│  回测概览                            │
│  策略名 / 回测区间 / 初始资金        │
│  核心指标卡片（收益/夏普/回撤/胜率）  │
├─────────────────────────────────────┤
│  权益曲线图                          │
│  策略权益 vs 买入持有基准            │
│  回撤区域阴影                        │
├─────────────────────────────────────┤
│  K 线 + 交易标记图                   │
│  OHLC K线 + 指标叠加                 │
│  买入/卖出标记 + 止损/止盈标记       │
├─────────────────────────────────────┤
│  指标详情表格                        │
│  25+ 指标的完整列表                  │
├─────────────────────────────────────┤
│  交易明细表                          │
│  每笔交易的进出/盈亏/原因            │
├─────────────────────────────────────┤
│  平仓原因分布饼图                    │
│  止损/止盈/信号消失/固定天数/强制     │
├─────────────────────────────────────┤
│  月度收益热力图                      │
│  年×月 的收益矩阵                    │
└─────────────────────────────────────┘
```

**技术方案**：
- 基于 Plotly 生成交互式 HTML（兼容 Bokeh 方案）
- 支持缩放、悬浮、下载为 PNG
- 单文件 HTML，无外部依赖

**验收标准**：
- [ ] 报告在浏览器中正确渲染
- [ ] 权益曲线、回撤图、K 线图交互正常
- [ ] 交易标记在正确位置显示
- [ ] 月度收益热力图正确
- [ ] 单文件 HTML 可独立打开

---

### 6.7 P0：参数预设系统

#### FR-011: 股票分类参数预设

**描述**：基于股票活跃度和市值规模提供回测参数预设。

**预设矩阵**：

```python
class ActivityLevel(Enum):
    LOW = 'low'       # 低波动（银行、公用事业）
    MEDIUM = 'medium' # 中等波动（沪深300）
    HIGH = 'high'     # 高波动（题材股、科创板）
    EXTREME = 'extreme' # 极端波动（妖股）

class CapSize(Enum):
    LARGE = 'large'   # 大盘 >500亿
    MID = 'mid'       # 中盘 100-500亿
    SMALL = 'small'   # 小盘 <100亿
    MICRO = 'micro'   # 微盘 <30亿

class BacktestPreset:
    threshold: float
    trailing_stop_pct: float
    take_profit_pct: float
    max_hold_days: int = None
    position_sizing: str = 'full'
    fee_rate: float = 0.0015
    min_confidence: float = None
    min_ret_5d: float = None
    partial_exit_enabled: bool = False
```

**预设组合（16 种）**：

| 活跃度 × 市值 | threshold | trailing_stop | take_profit | 特点 |
|---|---|---|---|---|
| LOW × LARGE | 0.45 | 0.03 | 0.04 | 低门槛、窄止损、快出场 |
| LOW × MID | 0.48 | 0.04 | 0.05 | 稍严格 |
| LOW × SMALL | 0.50 | 0.04 | 0.05 | 短持仓(max 3天) |
| LOW × MICRO | 0.52 | 0.05 | 0.06 | 更保守 |
| MEDIUM × LARGE | 0.50 | 0.04 | 0.06 | 中等参数 |
| MEDIUM × MID | 0.55 | 0.05 | 0.08 | 分批止盈 |
| MEDIUM × SMALL | 0.57 | 0.06 | 0.10 | 稍严格 |
| MEDIUM × MICRO | 0.58 | 0.06 | 0.10 | 更严格 |
| HIGH × LARGE | 0.55 | 0.06 | 0.10 | 高门槛 |
| HIGH × MID | 0.60 | 0.07 | 0.15 | 要求5日正收益 |
| HIGH × SMALL | 0.62 | 0.08 | 0.18 | 更高门槛 |
| HIGH × MICRO | 0.63 | 0.08 | 0.18 | 长持仓(max 12天) |
| EXTREME × LARGE | 0.58 | 0.07 | 0.12 | 极端保守 |
| EXTREME × MID | 0.62 | 0.08 | 0.16 | 高过滤 |
| EXTREME × SMALL | 0.65 | 0.10 | 0.20 | 最高门槛、容忍巨震 |
| EXTREME × MICRO | 0.68 | 0.12 | 0.22 | 极端保守 |

**便捷方法**：

```python
BacktestPresets.blue_chip()      # LOW × LARGE
BacktestPresets.growth_mid()     # MEDIUM × MID
BacktestPresets.tech_small()     # HIGH × SMALL
BacktestPresets.quant_active()   # EXTREME × SMALL
BacktestPresets.from_stock(code) # 根据股票代码自动分类
```

**验收标准**：
- [ ] 16 种预设组合全部定义
- [ ] `from_stock()` 根据股票属性自动匹配预设
- [ ] 预设参数可直接传递给回测引擎
- [ ] 预设可被用户参数覆盖

---

### 6.8 P1：参数优化器

#### FR-012: 网格搜索优化

**描述**：对策略参数进行网格搜索优化。

**详细规格**：

```python
class Backtest:
    def optimize(self,
                 maximize: str = 'Sharpe Ratio',  # 优化目标
                 method: str = 'grid',            # 'grid' 或 'bayesian'
                 max_tries: int = None,           # 最大尝试次数
                 constraint: Callable = None,      # 约束条件
                 return_heatmap: bool = False,     # 返回热力图数据
                 return_optimization: bool = False, # 返回优化过程
                 **kwargs) -> pd.Series:
        """
        参数优化。
        kwargs 中传入参数的搜索范围，如：
            optimize(short_window=range(3, 15), mid_window=range(10, 40, 5))
        """
        pass
```

**支持参数类型**：
- `range(start, stop, step)` — 整数参数
- 列表 `[5, 10, 20, 60]` — 离散参数
- `(low, high)` — 连续参数（贝叶斯优化）

**约束条件**：

```python
# 示例：短期均线必须小于长期均线
constraint=lambda p: p.short_window < p.mid_window
```

**验收标准**：
- [ ] 网格搜索正确遍历所有参数组合
- [ ] 约束条件正确过滤
- [ ] 优化结果返回最优参数和对应统计
- [ ] 热力图数据正确生成

#### FR-013: 热力图可视化

**描述**：参数优化结果的热力图可视化。

**验收标准**：
- [ ] 双参数热力图正确渲染
- [ ] 多参数时自动生成多张热力图
- [ ] 支持交互式缩放和悬浮
- [ ] 可导出为 HTML 或 PNG

#### FR-014: 贝叶斯优化

**描述**：使用贝叶斯方法进行高效参数优化。

**技术方案**：集成 `sambo` 或 `scikit-optimize` 库。

**验收标准**：
- [ ] 贝叶斯优化收敛到近优解
- [ ] 在相同预算下优于随机搜索
- [ ] 支持 `max_tries` 限制
- [ ] 返回优化轨迹数据

---

### 6.9 P1：追踪止损

#### FR-015: ATR 追踪止损

**描述**：基于 ATR 的追踪止损策略组件。

```python
class TrailingMixin:
    """追踪止损混入类"""
    
    def set_atr_periods(self, periods: int = 100):
        """设置 ATR 计算周期"""
        pass
    
    def set_trailing_sl(self, n_atr: float = 6.0):
        """设置 ATR 倍数追踪止损"""
        pass
    
    def set_trailing_pct(self, pct: float = 0.05):
        """设置百分比追踪止损"""
        pass
```

**验收标准**：
- [ ] ATR 追踪止损从持仓最高点计算
- [ ] 百分比追踪止损正确转换
- [ ] 止损价只往有利方向移动
- [ ] 部分平仓后追踪止损继续工作

---

### 6.10 P1：蒙特卡洛模拟

#### FR-016: 随机数据鲁棒性测试

**描述**：通过蒙特卡洛模拟测试策略鲁棒性。

```python
def random_ohlc_data(example_data: pd.DataFrame, 
                     frac: float = 1.0,
                     random_state: int = None) -> Generator[pd.DataFrame, None, None]:
    """
    生成具有相似统计特征的随机 OHLC 数据。
    frac > 1 时为过采样。
    """
    pass
```

**验收标准**：
- [ ] 随机数据保持原始数据的基本统计特征
- [ ] 支持多次独立模拟
- [ ] 模拟结果的分布统计正确
- [ ] 可输出策略鲁棒性评估报告

---

### 6.11 P1：可组合策略

#### FR-017: 信号策略 (SignalStrategy)

```python
class SignalStrategy(BacktestStrategy):
    """向量化信号策略"""
    def set_signal(self, entry_size, exit_portion=None, plot=True):
        """设置入场/出场信号向量"""
        pass
```

#### FR-018: 追踪止损策略 (TrailingStrategy)

```python
class TrailingStrategy(BacktestStrategy):
    """带追踪止损的策略"""
    def set_trailing_sl(self, n_atr=6): pass
    def set_trailing_pct(self, pct=0.05): pass
```

**验收标准**：
- [ ] `SignalStrategy` 正确执行向量化回测
- [ ] `TrailingStrategy` 正确管理追踪止损
- [ ] 可通过继承组合使用

---

### 6.12 P1：平仓原因统计

#### FR-019: 平仓原因分析

**描述**：统计各种平仓原因的分布和对应收益。

**输出**：

| 平仓原因 | 次数 | 占比 | 平均收益 | 胜率 |
|----------|------|------|----------|------|
| trailing_stop | 23 | 28% | -2.3% | 15% |
| take_profit | 18 | 22% | +8.5% | 100% |
| signal_lost | 15 | 18% | +1.2% | 53% |
| fixed_days | 12 | 15% | +3.1% | 67% |
| stop_loss | 10 | 12% | -3.8% | 0% |
| max_hold_days | 4 | 5% | -1.5% | 25% |

**验收标准**：
- [ ] 每种平仓原因的统计数据正确
- [ ] 在 HTML 报告中展示分布饼图
- [ ] 支持按平仓原因筛选交易

---

### 6.13 P2：多时间框架

#### FR-020: 多时间框架指标

```python
def resample_apply(rule: str, func, series, *args, agg=None, **kwargs):
    """将指标函数应用到重采样后的时间框架"""
    pass
```

**验收标准**：
- [ ] 支持任意 Pandas 频率字符串（'D', 'W', 'ME' 等）
- [ ] 指标正确计算和重采样回原时间框架
- [ ] 在 `init()` 中自动包装为 `self.I()`

---

### 6.14 P2：多标的组合回测

#### FR-021: 多标的并行回测

```python
class MultiBacktest:
    """多品种并行回测"""
    def __init__(self, df_list, strategy_cls, **kwargs): pass
    def run(self, **kwargs) -> pd.DataFrame: pass
    def optimize(self, **kwargs) -> pd.DataFrame: pass
```

**验收标准**：
- [ ] 多品种并行回测正确执行
- [ ] 结果按品种分组
- [ ] 共享内存优化大数据场景

---

## 7. 技术架构设计

### 7.1 整体架构

```
┌────────────────────────────────────────────────────────────┐
│                     Web UI / API 层                         │
│  Flask/FastAPI → /api/v1/backtest/*                        │
├────────────────────────────────────────────────────────────┤
│                     回测服务层                              │
│  BacktestService                                           │
│    ├── run_backtest()      → 执行单次回测                  │
│    ├── run_optimization()  → 执行参数优化                  │
│    ├── run_montecarlo()    → 执行蒙特卡洛                  │
│    └── generate_report()   → 生成 HTML 报告               │
├────────────────────────────────────────────────────────────┤
│                     回测引擎层                              │
│  Backtest                                                  │
│    ├── __init__(data, strategy, cash, commission, ...)     │
│    ├── run(**kwargs)      → 运行回测                       │
│    ├── optimize(...)      → 参数优化                       │
│    └── plot(...)          → 可视化                         │
├──────────┬──────────┬──────────┬───────────┬──────────────┤
│ Strategy │  Broker  │  Stats   │ Plotting  │ Optimizer    │
│ 基类     │ 模拟经纪 │ 统计引擎 │ 可视化    │ 优化器       │
├──────────┴──────────┴──────────┴───────────┴──────────────┤
│                     数据层                                  │
│  DataProvider → OHLCV DataFrame                            │
│    ├── AkShare / Tushare / Pytdx / Baostock               │
│    └── CSV / 数据库                                        │
├────────────────────────────────────────────────────────────┤
│                     策略适配层                              │
│  YAMLStrategy → AI 预测策略 → 自定义 Strategy              │
├────────────────────────────────────────────────────────────┤
│                     参数预设层                              │
│  BacktestPresets (16 种预设)                               │
└────────────────────────────────────────────────────────────┘
```

### 7.2 核心执行流程

```
Backtest.run()
│
├── 1. 数据预处理
│   ├── 验证 OHLCV 格式
│   ├── 排序和填充缺失值
│   └── 创建 _Data 访问对象
│
├── 2. 初始化组件
│   ├── _Broker(cash, commission, slippage, ...)
│   ├── Strategy(data, broker)
│   └── strategy.init()  → 用户注册指标
│
├── 3. 指标预热
│   └── 跳过前 N 根 K 线（指标计算所需）
│
├── 4. 主循环（逐 K 线）
│   for i in range(warmup, len(data)):
│   │
│   ├── broker.next()  → 处理挂单
│   │   ├── 检查 stop 条件
│   │   ├── 检查 limit 条件
│   │   ├── 处理 SL/TP 关联订单
│   │   ├── FIFO 平仓（非对冲模式）
│   │   └── 保证金检查
│   │
│   └── strategy.next()  → 用户交易逻辑
│       ├── 读取指标值
│       ├── 判断开仓/平仓条件
│       ├── 执行 buy/sell
│       └── 修改 SL/TP
│
├── 5. 收尾
│   ├── 强制平仓剩余仓位
│   └── 收集交易记录
│
└── 6. 计算统计
    ├── compute_stats(trades, equity, data, strategy)
    ├── 返回 pd.Series（25+ 指标）
    └── 包含 _equity_curve, _trades 详细数据
```

### 7.3 目录结构设计

```
src/
├── backtest/                        # 🔑 新增：回测引擎模块
│   ├── __init__.py                  # 公共 API 导出
│   ├── engine.py                    # Backtest 主类
│   ├── strategy.py                  # BacktestStrategy 基类
│   ├── order.py                     # Order / Trade / Position 数据类
│   ├── broker.py                    # _Broker 模拟经纪商
│   ├── stats.py                     # compute_stats() 统计引擎
│   ├── plotting.py                  # HTML 报告生成
│   ├── optimizer.py                 # 参数优化器（网格+贝叶斯）
│   ├── presets.py                   # BacktestPresets 参数预设
│   ├── exit_rules.py                # ExitRule / ExitReason 平仓规则
│   ├── position_sizing.py           # 仓位管理策略
│   ├── lib.py                       # 辅助函数（crossover, resample_apply, etc.）
│   ├── strategies/                  # 内置可组合策略
│   │   ├── __init__.py
│   │   ├── signal_strategy.py       # SignalStrategy
│   │   ├── trailing_strategy.py     # TrailingStrategy
│   │   └── ai_prediction_strategy.py # AI 预测策略
│   ├── adapters/                    # 策略适配器
│   │   ├── __init__.py
│   │   ├── yaml_strategy.py         # YAML → Strategy 桥接
│   │   └── ai_signal_adapter.py     # AI 信号适配器
│   └── tests/                       # 回测引擎测试
│       ├── test_engine.py
│       ├── test_strategy.py
│       ├── test_broker.py
│       ├── test_stats.py
│       ├── test_optimizer.py
│       ├── test_presets.py
│       └── test_exit_rules.py
├── alpha/                           # 现有：保留但重构
│   ├── portfolio_simulator.py       # 重构：调用 backtest 引擎
│   └── ...
└── ...
```

### 7.4 与现有系统的集成点

| 集成点 | 方向 | 说明 |
|--------|------|------|
| `strategies/*.yaml` | 回测引擎 ← 读取 | YAML 策略通过适配器转为 Strategy |
| `src/alpha/portfolio_simulator.py` | 回测引擎 → 替换 | 原模拟器重构为调用 Backtest 引擎 |
| `AnalysisHistory` | 回测引擎 ← 读取 | AI 预测策略读取历史分析记录 |
| `data_provider/` | 回测引擎 ← 读取 | 通过现有数据源获取 K 线数据 |
| `data/kline/` | 回测引擎 ← 读取 | 本地 K 线数据缓存 |
| `/api/v1/backtest/*` | 回测引擎 → 服务 | API 层调用 BacktestService |
| `apps/dsa-web/` | 回测引擎 → 展示 | 前端展示回测结果和报告 |

---

## 8. 数据模型设计

### 8.1 核心数据类

```python
# ---- OHLCV 数据 ----
# 输入格式：pd.DataFrame，必须包含 Open/High/Low/Close 列
# 可选列：Volume, Adj Close
# 索引：pd.DatetimeIndex

# ---- 回测结果 ----
@dataclass
class BacktestResult:
    # 基础信息
    strategy_name: str
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_cash: float
    
    # 配置参数
    commission: float
    slippage: float
    stamp_duty: float
    preset_name: str = None
    
    # 绩效指标（25+）
    stats: pd.Series
    
    # 详细数据
    equity_curve: pd.DataFrame       # columns: Equity, DrawdownPct, DrawdownDuration
    trades: pd.DataFrame             # 详细交易记录
    
    # 元数据
    engine_version: str = 'v2'
    created_at: datetime = None
    
    # 方法
    def to_html(self, filename: str = None) -> str:
        """生成 HTML 报告"""
        pass
    
    def to_json(self) -> dict:
        """序列化为 JSON"""
        pass
    
    def summary(self) -> dict:
        """返回核心摘要指标"""
        pass
```

### 8.2 交易记录格式

```python
# trades DataFrame 列定义
trades_columns = {
    'Size': float,              # 交易方向和数量（正=多，负=空）
    'EntryBar': int,            # 入场 K 线索引
    'ExitBar': int,             # 出场 K 线索引
    'EntryPrice': float,        # 入场价格
    'ExitPrice': float,         # 出场价格
    'SL': float,                # 止损价
    'TP': float,                # 止盈价
    'PnL': float,               # 盈亏金额
    'ReturnPct': float,         # 收益率
    'Commission': float,        # 手续费
    'EntryTime': datetime,      # 入场时间
    'ExitTime': datetime,       # 出场时间
    'Duration': timedelta,      # 持仓时间
    'Tag': str,                 # 自定义标签
    'ExitReason': str,          # 平仓原因（新增）
    'PositionPct': float,       # 仓位比例（新增）
}
```

### 8.3 数据库模型扩展

```sql
-- 新增：回测结果表
CREATE TABLE backtest_results (
    id INTEGER PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_cash REAL DEFAULT 100000,
    commission REAL DEFAULT 0.0003,
    slippage REAL DEFAULT 0.001,
    preset_name TEXT,
    
    -- 核心指标
    total_return_pct REAL,
    annual_return_pct REAL,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    max_drawdown_pct REAL,
    win_rate_pct REAL,
    profit_factor REAL,
    trade_count INTEGER,
    cagr_pct REAL,
    calmar_ratio REAL,
    alpha_pct REAL,
    beta REAL,
    sqn REAL,
    kelly_criterion REAL,
    
    -- 详细数据（JSON）
    equity_curve_json TEXT,
    trades_json TEXT,
    
    -- 元数据
    engine_version TEXT DEFAULT 'v2',
    config_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 新增：参数优化结果表
CREATE TABLE optimization_results (
    id INTEGER PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    optimize_target TEXT NOT NULL,
    method TEXT NOT NULL,
    best_params_json TEXT NOT NULL,
    best_value REAL NOT NULL,
    all_results_json TEXT,
    heatmap_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 9. API 接口设计

### 9.1 回测引擎 API

```python
# ===== 核心 API =====

# 1. 运行策略回测
POST /api/v1/backtest/run
Body: {
    "strategy": "ma_golden_cross",     # 策略名或 YAML 路径
    "symbol": "600519",                # 股票代码
    "start_date": "2024-01-01",        # 回测起始日
    "end_date": "2026-03-31",          # 回测结束日
    "cash": 100000,                    # 初始资金
    "commission": 0.0003,              # 佣金率
    "slippage": 0.001,                 # 滑点率
    "preset": "blue_chip",             # 参数预设（可选）
    "factors": {                       # 因子覆盖（可选）
        "short_window": 10,
        "mid_window": 30
    },
    "exit_rules": {                    # 平仓规则（可选）
        "trailing_stop_pct": 0.05,
        "take_profit_pct": 0.10,
        "max_hold_days": 10
    }
}
Response: BacktestResult

# 2. 运行 AI 预测策略回测
POST /api/v1/backtest/run-ai
Body: {
    "symbol": "600519",
    "start_date": "2024-01-01",
    "end_date": "2026-03-31",
    "threshold": 0.55,
    "min_confidence": 0.4,
    "position_sizing": "signal",
    "exit_rules": { ... }
}

# 3. 运行参数优化
POST /api/v1/backtest/optimize
Body: {
    "strategy": "ma_golden_cross",
    "symbol": "600519",
    "start_date": "2024-01-01",
    "end_date": "2026-03-31",
    "maximize": "Sharpe Ratio",
    "method": "grid",
    "factor_ranges": {
        "short_window": [3, 5, 8, 10, 13],
        "mid_window": [10, 15, 20, 30, 40]
    },
    "constraint": "short_window < mid_window"
}

# 4. 运行蒙特卡洛模拟
POST /api/v1/backtest/montecarlo
Body: {
    "strategy": "ma_golden_cross",
    "symbol": "600519",
    "n_simulations": 1000,
    "frac": 1.0
}

# 5. 生成 HTML 报告
GET /api/v1/backtest/report/{result_id}
Response: HTML file

# 6. 获取预设列表
GET /api/v1/backtest/presets
Response: List[BacktestPreset]

# 7. 获取策略列表（可回测）
GET /api/v1/backtest/strategies
Response: List[StrategyInfo]

# 8. 查询历史回测结果
GET /api/v1/backtest/results?page=1&limit=20&strategy=ma_golden_cross
Response: PaginatedResult[BacktestResult]

# 9. 获取回测绩效概览
GET /api/v1/backtest/performance?strategy=ma_golden_cross
Response: PerformanceSummary

# 10. 平仓原因分析
GET /api/v1/backtest/exit-analysis/{result_id}
Response: ExitAnalysis
```

---

## 10. 实施路线图

### Phase 1：核心引擎（3 周）

| 周次 | 任务 | 交付物 |
|------|------|--------|
| W1 | BacktestStrategy 基类 + _Broker 模拟经纪商 | `strategy.py` + `broker.py` + `order.py` |
| W1 | 订单撮合引擎 + 交易成本模型 | `broker.py` 完善 |
| W2 | compute_stats() 统计引擎 | `stats.py`（25+ 指标） |
| W2 | ExitRule 平仓规则引擎 | `exit_rules.py` |
| W3 | Backtest 主类 + run() 主循环 | `engine.py` |
| W3 | 单元测试 + 集成测试 | `tests/` |

**里程碑**：`Backtest(data, MyStrategy).run()` 可运行并返回完整统计

### Phase 2：策略适配 + 可视化（2 周）

| 周次 | 任务 | 交付物 |
|------|------|--------|
| W4 | YAML → Strategy 适配器 | `yaml_strategy.py` |
| W4 | AI 预测策略适配器 | `ai_prediction_strategy.py` |
| W4 | 参数预设系统 | `presets.py` |
| W5 | HTML 交互式报告 | `plotting.py` |
| W5 | Web API 集成 | `backtest_service.py` |
| W5 | 前端回测页面更新 | `apps/dsa-web/` |

**里程碑**：21 个 YAML 策略全部可回测，HTML 报告可生成

### Phase 3：优化器 + 高级功能（2 周）

| 周次 | 任务 | 交付物 |
|------|------|--------|
| W6 | 网格搜索优化器 + 热力图 | `optimizer.py` |
| W6 | TrailingStrategy + SignalStrategy | `strategies/` |
| W7 | 蒙特卡洛模拟 | `lib.py` |
| W7 | 多时间框架支持 | `lib.py` |
| W7 | 平仓原因分析 + 统计 | 集成到报告 |

**里程碑**：参数优化可用，完整报告可生成

### Phase 4：扩展 + 打磨（2 周）

| 周次 | 任务 | 交付物 |
|------|------|--------|
| W8 | 多标的并行回测 | `MultiBacktest` |
| W8 | 仓位管理策略 (Kelly/Equal Risk) | `position_sizing.py` |
| W9 | 性能优化 + 大数据测试 | 性能报告 |
| W9 | 文档 + 用户指南 | `docs/` |

**里程碑**：完整功能上线

---

## 11. 风险评估与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| YAML→Strategy 桥接的指令解析复杂 | 高 | 高 | 优先实现编程式 Strategy，YAML 适配作为第二优先 |
| A股 T+1 限制未正确模拟 | 中 | 高 | 在 Broker 中硬编码 T+1 规则：当日买入不可卖出 |
| 回测结果与实际偏差大 | 中 | 高 | 添加滑点模型和流动性假设，明确标注局限性 |
| 性能瓶颈（大量 K 线数据） | 中 | 中 | 使用 NumPy 向量化计算，避免逐行循环 |
| 与现有 API 不兼容 | 低 | 中 | 新增 API 端点，保留旧 API 向后兼容 |
| Plotly/Bokeh 渲染问题 | 低 | 低 | 支持降级为静态 Matplotlib 输出 |

---

## 12. 测试策略

### 12.1 单元测试

| 模块 | 测试重点 | 覆盖率目标 |
|------|---------|-----------|
| `engine.py` | run() 主循环、边界条件 | 90%+ |
| `strategy.py` | init/next 调用、I() 注册 | 85%+ |
| `broker.py` | 订单撮合、SL/TP、T+1 | 95%+ |
| `stats.py` | 每个指标与 backtesting.py 对照 | 95%+ |
| `exit_rules.py` | 每种平仓规则、优先级 | 90%+ |
| `optimizer.py` | 网格搜索完整性、约束过滤 | 85%+ |
| `presets.py` | 16 种预设参数正确性 | 100% |
| `yaml_strategy.py` | 每个策略 YAML 的解析和执行 | 80%+ |

### 12.2 集成测试

- 完整回测流程：数据加载 → 策略执行 → 统计计算 → 报告生成
- YAML 策略端到端：每个 YAML 文件 → 回测 → 结果
- API 集成：每个 API 端点的请求/响应
- 前端集成：Web UI 回测页面交互

### 12.3 基准测试

| 场景 | 数据量 | 目标时间 |
|------|--------|----------|
| 1年日线单标的 | ~250 bars | < 1s |
| 3年日线单标的 | ~750 bars | < 3s |
| 10年日线单标的 | ~2500 bars | < 10s |
| 参数优化（4参数，100组合） | ~250 bars × 100 | < 30s |
| 蒙特卡洛 1000 次 | ~250 bars × 1000 | < 5min |

### 12.4 回归测试

- 使用 backtesting.py 的标准测试数据集（GOOG/EURUSD）对照验证
- 统计指标与 backtesting.py 结果偏差 < 0.01%
- 每次发布前运行完整测试套件

---

## 13. 附录

### 附录 A：三个竞品的详细源码分析

详见调研过程中的原始记录：

1. **backtesting.py 核心源码**：`backtesting.py`（Backtest + Strategy + _Broker）、`_stats.py`（25+ 指标计算）、`lib.py`（可组合策略 + 辅助函数）
2. **mizar-alpha 核心源码**：`strategy.py`（基础版 Strategy）、`strategy_pro.py`（增强版 Strategy + ExitRule）、`metrics.py`（绩效计算 + 可视化）、`param_presets.py`（参数预设）、`data_loader.py`（数据加载）
3. **qstrader 核心源码**：`simulation/sim_engine.py`（事件驱动引擎）、`statistics/`（统计 + Tearsheet）、`broker/`（模拟经纪 + 手续费 + 组合）、`portcon/`（组合构建 + 优化器）、`risk_model/`（风险模型）

### 附录 B：与 backtesting.py 的兼容性策略

**核心原则**：参考 backtesting.py 的设计模式，但重新实现（不依赖其代码），因为：
1. AGPL-3.0 许可证限制
2. 需要适配 A 股特殊规则（T+1、印花税等）
3. 需要与现有 YAML 策略框架和 AI 预测系统集成

**兼容层**：提供 `from backtest import Backtest, Strategy` 的导入路径，确保熟悉 backtesting.py 的用户可以零学习成本迁移。

### 附录 C：A股特殊规则清单

| 规则 | 说明 | 实现位置 |
|------|------|----------|
| T+1 | 当日买入不可当日卖出 | `broker.py` |
| 印花税 | 卖出时收取 0.1% | `broker.py` fee_model |
| 最低佣金 | 每笔最低 5 元 | `broker.py` fee_model |
| 涨跌停 | ±10% / ±20%（ST/科创板） | `broker.py` 撮合 |
| 交易单位 | 100 股为 1 手 | `broker.py` order_sizer |
| 融资融券 | 保证金交易 | P2 阶段 |
| 集合竞价 | 开盘/收盘集合竞价 | P2 阶段 |

### 附录 D：参考资源

- [backtesting.py 官方文档](https://kernc.github.io/backtesting.py/)
- [backtesting.py GitHub](https://github.com/kernc/backtesting.py)
- [QSTrader GitHub](https://github.com/mhallsmoore/qstrader)
- [mizar-alpha GitHub](https://github.com/jiangtaovan/mizar-alpha)
- [QuantConnect Lean 引擎](https://github.com/QuantConnect/Lean)
- [Zipline (Quantopian)](https://github.com/quantopian/zipline)

---

> **免责声明**：本 PRD 中所有回测功能的设计和实现仅供参考和学习用途，不构成任何投资建议。回测结果不代表未来收益，直接用于实盘交易可能导致重大损失。

---

## 14. 前端功能布局与实现细节

> **前提**：基于现有 `apps/dsa-web/` 的技术栈（React 19 + TypeScript + Tailwind CSS v4 + Zustand + Recharts + Vite），在已有 UI 组件和页面框架上扩展。

### 14.1 现有前端资源盘点

#### 14.1.1 已有回测相关组件

```
components/backtest/
├── BacktestProgress.tsx    # ✅ 可复用：SSE 进度条
├── OverviewTab.tsx         # ⚠️ 需重构：仅展示组合回测概览
├── PerformanceTab.tsx      # ⚠️ 需重构：指标不完整
├── RiskTab.tsx             # ⚠️ 需重构：仅有基础风险数据
├── TradeDetailTable.tsx    # ✅ 可复用：交易明细表格
└── TradeTab.tsx            # ⚠️ 需重构：缺少平仓原因列
```

#### 14.1.2 已有通用组件（可复用）

| 组件 | 用途 | 回测场景复用 |
|------|------|-------------|
| `StatCard` | 数据统计卡片 | 展示核心指标（收益/夏普/回撤） |
| `SectionCard` | 分区卡片 | 各功能区块容器 |
| `Select` / `Input` | 表单控件 | 回测参数配置 |
| `Button` | 按钮 | 运行回测/导出报告 |
| `Badge` | 徽章 | 策略标签/状态标记 |
| `Pagination` | 分页 | 交易明细/结果列表分页 |
| `Drawer` | 抽屉 | 参数高级配置面板 |
| `ConfirmDialog` | 确认对话框 | 清空回测结果确认 |
| `EmptyState` | 空状态 | 无回测数据时展示 |
| `Loading` | 加载状态 | 回测执行中 |
| `ScrollArea` | 滚动区域 | 长结果列表 |
| `Tooltip` | 提示 | 指标含义解释 |
| `Collapsible` | 折叠 | 高级参数面板 |
| `StockAutocomplete` | 股票搜索 | 选择回测标的 |

#### 14.1.3 已有 Hooks（可复用/需扩展）

| Hook | 现有功能 | 回测扩展需求 |
|------|---------|-------------|
| `useBacktestProgress` | SSE 进度追踪 | 保留，扩展新引擎的进度事件 |
| `useBacktestStream` | SSE 数据流 | 保留，扩展新回测类型的事件 |
| `useAutocomplete` | 股票搜索 | 保留，用于标的搜索 |

#### 14.1.4 已有页面框架

现有 `BacktestPage.tsx` 采用 **三步向导** 模式：

```
Step 1: config   → 配置参数
Step 2: running  → 执行回测（SSE 进度）
Step 3: results  → 展示结果
```

**关键决策**：保留三步向导模式，但将 Step 1 和 Step 3 大幅扩展。

### 14.2 新增/重构页面布局

#### 14.2.1 BacktestPage 整体布局重构

```
┌─────────────────────────────────────────────────────────────────────┐
│  BacktestPage                                                        │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  顶部标签栏：[策略回测] [AI验证回测] [参数优化] [蒙特卡洛]    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  StepIndicator: config → running → results                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                                                              │   │
│  │  （根据当前 step 和 tab 动态渲染的内容区域）                    │   │
│  │                                                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**四种回测模式 Tab**：

| Tab | 对应 API | 功能 |
|-----|---------|------|
| 策略回测 | `POST /api/v1/backtest/strategy` | 选择 YAML 策略 + 标的 + 参数运行回测 |
| AI验证回测 | `POST /api/v1/backtest/run`（现有） | 保留现有 AI 历史验证功能 |
| 参数优化 | `POST /api/v1/backtest/optimize` | 策略参数网格/贝叶斯优化 |
| 蒙特卡洛 | `POST /api/v1/backtest/montecarlo` | 策略鲁棒性测试 |

#### 14.2.2 策略回测 Tab — Step 1: 配置面板

```
┌─────────────────────────────────────────────────────────────────────┐
│  配置面板                                                            │
│                                                                      │
│  ┌─────────────────────┐  ┌─────────────────────────────────────┐  │
│  │ 1. 标的选择          │  │ 2. 策略选择                          │  │
│  │ ┌─────────────────┐ │  │ ┌─────────────────────────────────┐ │  │
│  │ │ StockAutocomplete│ │  │ │ 策略分类筛选                    │ │  │
│  │ │ 搜索添加标的     │ │  │ │ [趋势] [形态] [反转] [框架]     │ │  │
│  │ └─────────────────┘ │  │ │                                 │ │  │
│  │ 已选:               │  │ │ ┌───────────────────────────┐   │ │  │
│  │ [600519 ×] [000001×]│  │ │ │ ● 均线金叉   ⭐推荐      │   │ │  │
│  │                     │  │ │ │ ○ MACD背离               │   │ │  │
│  │                     │  │ │ │ ○ 缠论                   │   │ │  │
│  │                     │  │ │ │ ○ 海龟交易法              │   │ │  │
│  │                     │  │ │ │ ○ 布林带回归              │   │ │  │
│  │                     │  │ │ │ ... (21个策略)            │   │ │  │
│  │                     │  │ │ └───────────────────────────┘   │ │  │
│  │                     │  │ │                                 │ │  │
│  │                     │  │ │ 策略说明 (展开/折叠):           │ │  │
│  │                     │  │ │ 检测均线金叉配合量能确认信号...  │ │  │
│  │                     │  │ └─────────────────────────────────┘ │  │
│  └─────────────────────┘  └─────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 3. 策略参数 (根据选中策略动态生成)                            │   │
│  │                                                              │   │
│  │ 短期均线窗口 [___5___] ← range [3, 10] step 1               │   │
│  │ 中期均线窗口 [__20___] ← range [10, 30] step 5               │   │
│  │ 长期均线窗口 [__60___] ← range [30, 120] step 10             │   │
│  │ 金叉得分     [_12.0__] ← range [5.0, 25.0] step 1.0         │   │
│  │ 死叉惩罚     [_-10.0_] ← range [-25.0, -3.0] step 1.0       │   │
│  │ 放量确认得分 [__5.0__] ← range [0.0, 12.0] step 1.0         │   │
│  │                                                              │   │
│  │ [使用预设参数 ▾]  → 蓝筹 / 成长中盘 / 科技小盘 / 量化活跃    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 4. 交易参数                                                   │   │
│  │                                                              │   │
│  │ 初始资金    [___100000___] 元                                 │   │
│  │ 佣金率      [___0.0003___] (万三)                            │   │
│  │ 滑点率      [___0.001____] (千一)                            │   │
│  │ 回测区间    [2024-01-01] ~ [2026-03-31]                      │   │
│  │                                                              │   │
│  │ 5. 平仓规则 (Collapsible 高级参数)                            │   │
│  │ ┌──────────────────────────────────────────────────────┐     │   │
│  │ │ 移动止损   [开启 ☑] 回撤比例 [___5___]%              │     │   │
│  │ │ 目标止盈   [开启 ☑] 止盈比例  [__10___]%             │     │   │
│  │ │ 固定止损   [开启 ☐] 止损比例  [___3___]%             │     │   │
│  │ │ 最大持仓   [开启 ☐] 天数      [__10___]天            │     │   │
│  │ │ 部分止盈   [开启 ☐] 平仓比例  [__50___]%             │     │   │
│  │ │ 信号消失平仓 [开启 ☐] 信号阈值 [__0.45__]           │     │   │
│  │ └──────────────────────────────────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  [StickyActionBar:  ← 上一步  |  开始回测 →  ]                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 14.2.3 策略回测 Tab — Step 3: 结果展示

```
┌─────────────────────────────────────────────────────────────────────┐
│  回测结果                                                            │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 核心指标卡片行 (4个 StatCard)                                │   │
│  │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │   │
│  │ │ 累计收益  │ │ 夏普比率  │ │ 最大回撤  │ │ 胜率      │        │   │
│  │ │ +58.9%   │ │  1.23    │ │ -12.3%   │ │ 62.5%    │        │   │
│  │ │ 🟢       │ │ 🟢       │ │ 🟡       │ │ 🟢       │        │   │
│  │ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 结果标签页: [概览] [绩效] [交易] [风险] [可视化]             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ---- 概览 Tab ----                                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 策略名称: 均线金叉  |  标的: 600519  |  回测区间: 3年         │   │
│  │ 初始资金: ¥100,000  |  最终权益: ¥158,900                    │   │
│  │ 买入持有收益: +42.3%  |  超额收益: +16.6%                    │   │
│  │                                                              │   │
│  │ 权益曲线图 (Recharts)                                        │   │
│  │ ┌──────────────────────────────────────────────────────────┐ │   │
│  │ │  策略权益 ────────  买入持有基准 - - - -                  │ │   │
│  │ │  ▲158.9%                    /──────                       │ │   │
│  │ │             /──────────────/                               │ │   │
│  │ │  ─------/                                                 │ │   │
│  │ │  回撤区域 (灰色阴影)      ▼-12.3%                         │ │   │
│  │ └──────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ---- 绩效 Tab ----                                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ ┌─────────────────────────┐ ┌─────────────────────────┐     │   │
│  │ │ 收益指标                │ │ 风险指标                │     │   │
│  │ │ 总收益率    +58.9%      │ │ 年化波动率  18.3%       │     │   │
│  │ │ 年化收益率  +22.4%      │ │ 最大回撤    -12.3%      │     │   │
│  │ │ CAGR        +18.7%      │ │ 平均回撤    -3.2%       │     │   │
│  │ │ 买入持有    +42.3%      │ │ 最大回撤持续 68天       │     │   │
│  │ │ 暴露时间    94.3%       │ │ 平均回撤持续 12天       │     │   │
│  │ └─────────────────────────┘ └─────────────────────────┘     │   │
│  │ ┌─────────────────────────┐ ┌─────────────────────────┐     │   │
│  │ │ 风险调整指标             │ │ CAPM 指标               │     │   │
│  │ │ 夏普比率    1.23        │ │ Alpha       +16.6%      │     │   │
│  │ │ Sortino比率  1.85       │ │ Beta        0.42        │     │   │
│  │ │ Calmar比率   1.82       │ │                          │     │   │
│  │ └─────────────────────────┘ └─────────────────────────┘     │   │
│  │ ┌─────────────────────────┐ ┌─────────────────────────┐     │   │
│  │ │ 交易统计                │ │ A股扩展指标              │     │   │
│  │ │ 交易次数    93          │ │ 换手率      385%        │     │   │
│  │ │ 胜率        62.5%       │ │ 日胜率      54.2%       │     │   │
│  │ │ 最佳交易   +57.1%       │ │ 盈亏比      1.38        │     │   │
│  │ │ 最差交易   -16.6%       │ │ 总手续费    ¥2,340      │     │   │
│  │ │ 平均交易    +1.96%      │ │                          │     │   │
│  │ │ Profit Factor 2.13      │ │                          │     │   │
│  │ │ SQN         1.78        │ │                          │     │   │
│  │ │ Kelly       0.61        │ │                          │     │   │
│  │ └─────────────────────────┘ └─────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ---- 交易 Tab ----                                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 交易明细表 (重构 TradeDetailTable)                            │   │
│  │ ┌───────┬───────┬───────┬──────┬──────┬───────┬──────────┐  │   │
│  │ │ #     │ 入场日 │ 出场日 │ 方向  │ 收益  │ 持仓天 │ 平仓原因 │  │   │
│  │ ├───────┼───────┼───────┼──────┼──────┼───────┼──────────┤  │   │
│  │ │ 1     │ 01-15 │ 01-22 │ 多   │+5.2% │ 7     │ 止盈     │  │   │
│  │ │ 2     │ 02-03 │ 02-08 │ 多   │-3.1% │ 5     │ 移动止损 │  │   │
│  │ │ 3     │ 02-15 │ 02-25 │ 多   │+8.7% │ 10    │ 信号消失 │  │   │
│  │ │ ...   │       │       │      │      │       │          │  │   │
│  │ └───────┴───────┴───────┴──────┴──────┴───────┴──────────┘  │   │
│  │                                                              │   │
│  │ 平仓原因分布 (Recharts PieChart)                              │   │
│  │ ┌──────────────────────────┐ ┌──────────────────────────┐   │   │
│  │ │ 🔵 止盈     22%          │ │ 原因  │ 次数 │ 平均收益  │   │   │
│  │ │ 🟠 移动止损 28%          │ │ 止盈  │ 18   │ +8.5%     │   │   │
│  │ │ 🟢 信号消失 18%          │ │ 移动止损│ 23  │ -2.3%     │   │   │
│  │ │ 🟣 固定天数 15%          │ │ 信号消失│ 15  │ +1.2%     │   │   │
│  │ │ 🔴 固定止损 12%          │ │ 固定天数│ 12  │ +3.1%     │   │   │
│  │ │ ⚪ 其他     5%           │ │ 固定止损│ 10  │ -3.8%     │   │   │
│  │ └──────────────────────────┘ └──────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ---- 风险 Tab ----                                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 回撤时序图 (Recharts AreaChart)                               │   │
│  │ ┌──────────────────────────────────────────────────────────┐ │   │
│  │ │  ▼-12.3%                                                 │ │   │
│  │ │  回撤面积图(红色)  ───── 最大回撤标记                     │ │   │
│  │ └──────────────────────────────────────────────────────────┘ │   │
│  │                                                              │   │
│  │ 月度收益热力图                                                │   │
│  │ ┌──────────────────────────────────────────────────────────┐ │   │
│  │ │        1月   2月   3月   4月   5月  ...  12月            │ │   │
│  │ │ 2024   +3.2  -1.5  +5.8  +2.1  -0.8     +4.1           │ │   │
│  │ │ 2025   +1.8  +3.5  -2.1  +6.3  +1.2     -1.5           │ │   │
│  │ │ 2026   +4.5  +2.1  +3.8  ...                            │ │   │
│  │ └──────────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ---- 可视化 Tab ----                                                │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ K 线图 + 指标叠加 + 交易标记 (Recharts ComposedChart)        │   │
│  │ ┌──────────────────────────────────────────────────────────┐ │   │
│  │ │  OHLC K线 + MA5/MA10/MA20 指标线                        │ │   │
│  │ │  🟢 买入标记 ▲  🔴 卖出标记 ▼                           │ │   │
│  │ │  蓝色止损线 / 绿色止盈线                                 │ │   │
│  │ └──────────────────────────────────────────────────────────┘ │   │
│  │                                                              │   │
│  │ [下载 HTML 报告] [下载交易记录 CSV] [下载权益曲线 PNG]       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  [StickyActionBar:  ← 重新配置  |  导出报告  |  分享结果  ]          │
└─────────────────────────────────────────────────────────────────────┘
```

#### 14.2.4 参数优化 Tab 布局

```
┌─────────────────────────────────────────────────────────────────────┐
│  参数优化                                                            │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 1. 选择策略和标的 (复用策略回测的标的选择+策略选择组件)       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 2. 优化参数范围 (自动从 YAML factors 读取)                    │   │
│  │                                                              │   │
│  │ 短期均线窗口  起始 [3]  终止 [15]  步长 [1]  ☑ 参与优化      │   │
│  │ 中期均线窗口  起始 [10] 终止 [40]  步长 [5]  ☑ 参与优化      │   │
│  │ 长期均线窗口  起始 [30] 终止 [120] 步长 [10] ☐ 不参与优化    │   │
│  │ 金叉得分      起止 [5]~[25] 步长 [1.0]    ☐ 不参与优化      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 3. 优化配置                                                   │   │
│  │ 优化目标: [Sharpe Ratio ▾] (Return / Sortino / Calmar)       │   │
│  │ 优化方法: [网格搜索 ▾] (网格搜索 / 贝叶斯优化)               │   │
│  │ 约束条件: short_window < mid_window  (可编辑)                │   │
│  │ 最大尝试: [200]                                               │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ---- 优化结果 ----                                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 最优参数: short_window=8, mid_window=25                      │   │
│  │ 最优 Sharpe: 1.45 (vs 默认参数 1.23)                        │   │
│  │                                                              │   │
│  │ 参数热力图 (Recharts HeatMap)                                 │   │
│  │ ┌──────────────────────────────────────────────────────────┐ │   │
│  │ │  short_window × mid_window → Sharpe Ratio 热力图         │ │   │
│  │ │  深色=高值 浅色=低值  最优点标记⭐                        │ │   │
│  │ └──────────────────────────────────────────────────────────┘ │   │
│  │                                                              │   │
│  │ [应用最优参数到策略回测]  [导出优化报告]                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 14.3 新增/重构前端组件清单

#### 14.3.1 新增组件

| 组件路径 | 功能 | 优先级 |
|----------|------|--------|
| `components/backtest/StrategySelector.tsx` | 策略列表+分类筛选+搜索 | P0 |
| `components/backtest/StrategyParamForm.tsx` | 根据 YAML factors 动态生成参数表单 | P0 |
| `components/backtest/PresetSelector.tsx` | 参数预设选择器（蓝筹/成长/科技/量化） | P0 |
| `components/backtest/ExitRuleForm.tsx` | 平仓规则配置表单 | P0 |
| `components/backtest/EquityCurveChart.tsx` | 重构：策略权益 vs 买入持有基准 | P0 |
| `components/backtest/DrawdownChart.tsx` | 回撤时序图 | P0 |
| `components/backtest/KlineTradeChart.tsx` | K线+指标+交易标记叠加图 | P0 |
| `components/backtest/ExitReasonPieChart.tsx` | 平仓原因饼图 | P1 |
| `components/backtest/MonthlyHeatmap.tsx` | 月度收益热力图 | P1 |
| `components/backtest/OptimizeConfigForm.tsx` | 参数优化配置表单 | P1 |
| `components/backtest/ParamHeatmap.tsx` | 参数优化热力图 | P1 |
| `components/backtest/MonteCarloResult.tsx` | 蒙特卡洛结果分布图 | P1 |
| `components/backtest/BacktestReportExport.tsx` | 导出 HTML/PNG/CSV | P0 |

#### 14.3.2 重构组件

| 组件 | 重构内容 | 优先级 |
|------|---------|--------|
| `OverviewTab.tsx` | 增加买入持有对比、超额收益、策略信息 | P0 |
| `PerformanceTab.tsx` | 扩展至 25+ 指标，按四维分组展示 | P0 |
| `TradeTab.tsx` | 增加 `ExitReason` 列和 `PositionPct` 列 | P0 |
| `RiskTab.tsx` | 增加回撤时序图、月度收益热力图 | P1 |
| `BacktestProgress.tsx` | 适配新引擎的 SSE 进度事件格式 | P0 |
| `TradeDetailTable.tsx` | 增加排序、筛选、平仓原因筛选 | P0 |

#### 14.3.3 新增 Hooks

| Hook | 功能 | 优先级 |
|------|------|--------|
| `useStrategyList.ts` | 获取可用策略列表（从 `GET /api/v1/backtest/strategies`） | P0 |
| `useBacktestPreset.ts` | 获取/匹配参数预设 | P0 |
| `useStrategyBacktest.ts` | 策略回测请求+结果管理 | P0 |
| `useBacktestOptimize.ts` | 参数优化请求+结果管理 | P1 |
| `useMonteCarlo.ts` | 蒙特卡洛请求+结果管理 | P1 |

#### 14.3.4 新增 Zustand Store

```typescript
// stores/backtestStore.ts
interface BacktestStore {
  // 回测模式
  mode: 'strategy' | 'verify' | 'optimize' | 'montecarlo';
  
  // 策略回测配置
  strategyConfig: {
    codes: string[];
    strategyName: string;
    factors: Record<string, number>;
    preset: string | null;
    cash: number;
    commission: number;
    slippage: number;
    startDate: string;
    endDate: string;
    exitRules: ExitRuleConfig;
  };
  
  // 结果
  result: BacktestResult | null;
  optimizeResult: OptimizeResult | null;
  montecarloResult: MontecarloResult | null;
  
  // Actions
  setMode: (mode: BacktestStore['mode']) => void;
  updateStrategyConfig: (patch: Partial<BacktestStore['strategyConfig']>) => void;
  setResult: (result: BacktestResult) => void;
  reset: () => void;
}
```

#### 14.3.5 新增 TypeScript 类型

```typescript
// types/backtest.ts 新增

// ---- 策略回测 ----
interface StrategyBacktestRequest {
  strategy: string;              // YAML 策略名
  codes: string[];               // 股票代码列表
  cash: number;                  // 初始资金
  commission: number;            // 佣金率
  slippage: number;              // 滑点率
  stampDuty: number;             // 印花税率
  startDate: string;             // 开始日期
  endDate: string;               // 结束日期
  factors?: Record<string, number>;  // 因子覆盖
  preset?: string;               // 参数预设名
  exitRules?: ExitRuleConfig;    // 平仓规则
}

interface ExitRuleConfig {
  trailingStopPct?: number;      // 移动止损回撤百分比
  takeProfitPct?: number;        // 目标止盈百分比
  stopLossPct?: number;          // 固定止损百分比
  maxHoldDays?: number;          // 最大持仓天数
  partialExitEnabled?: boolean;  // 部分止盈
  partialExitPct?: number;       // 部分止盈比例
  signalThreshold?: number;      // 信号消失阈值
  fixedDays?: number;            // 固定持仓天数
}

type ExitReason = 
  | 'stop_loss' | 'trailing_stop' | 'take_profit' 
  | 'partial_take_profit' | 'signal_lost' | 'fixed_days' 
  | 'max_hold_days' | 'force_close';

interface BacktestResult {
  strategyName: string;
  symbol: string;
  startDate: string;
  endDate: string;
  initialCash: number;
  stats: BacktestStats;
  equityCurve: EquityCurvePoint[];
  trades: BacktestTrade[];
  engineVersion: string;
  presetName: string | null;
}

interface BacktestStats {
  // 收益
  returnPct: number;
  returnAnnPct: number;
  cagrPct: number;
  buyHoldReturnPct: number;
  // 风险
  volatilityAnnPct: number;
  maxDrawdownPct: number;
  avgDrawdownPct: number;
  maxDrawdownDuration: string;
  avgDrawdownDuration: string;
  // 风险调整
  sharpeRatio: number;
  sortinoRatio: number;
  calmarRatio: number;
  // CAPM
  alphaPct: number;
  beta: number;
  // 交易
  tradeCount: number;
  winRatePct: number;
  bestTradePct: number;
  worstTradePct: number;
  avgTradePct: number;
  profitFactor: number;
  expectancyPct: number;
  sqn: number;
  kellyCriterion: number;
  // A股扩展
  turnoverRate: number;
  dayWinRate: number;
  profitLossRatio: number;
  totalCommission: number;
  exposureTimePct: number;
}

interface BacktestTrade {
  size: number;
  entryBar: number;
  exitBar: number;
  entryPrice: number;
  exitPrice: number;
  sl: number | null;
  tp: number | null;
  pnl: number;
  returnPct: number;
  commission: number;
  entryTime: string;
  exitTime: string;
  duration: string;
  tag: string | null;
  exitReason: ExitReason;
  positionPct: number;
}

// ---- 参数优化 ----
interface OptimizeRequest {
  strategy: string;
  codes: string[];
  startDate: string;
  endDate: string;
  maximize: string;
  method: 'grid' | 'bayesian';
  factorRanges: Record<string, number[]>;
  constraint?: string;
  maxTries?: number;
}

interface OptimizeResult {
  bestParams: Record<string, number>;
  bestValue: number;
  bestStats: BacktestStats;
  heatmap: Record<string, number>;  // 参数组合 → 目标值
  totalTrials: number;
  elapsedSeconds: number;
}

// ---- 蒙特卡洛 ----
interface MontecarloRequest {
  strategy: string;
  codes: string[];
  nSimulations: number;
  frac: number;
}

interface MontecarloResult {
  originalStats: BacktestStats;
  simulationStats: {
    meanSharpe: number;
    medianSharpe: number;
    p5Sharpe: number;
    p95Sharpe: number;
    sharpeGreaterThanZero: number;  // 夏普>0的比例
  };
  distribution: Array<{ sharpe: number; count: number }>;
  elapsedSeconds: number;
}

// ---- 预设 ----
interface BacktestPreset {
  name: string;
  displayName: string;
  activityLevel: string;
  capSize: string;
  threshold: number;
  trailingStopPct: number;
  takeProfitPct: number;
  stopLossPct: number | null;
  maxHoldDays: number | null;
  positionSizing: string;
  feeRate: number;
  minConfidence: number | null;
  minRet5d: number | null;
  partialExitEnabled: boolean;
}

// ---- 策略信息 ----
interface StrategyInfo {
  name: string;
  displayName: string;
  description: string;
  category: string;
  factors: StrategyFactor[];
  marketRegimes: string[];
}

interface StrategyFactor {
  id: string;
  displayName: string;
  type: 'int' | 'float';
  default: number;
  range: [number, number];
  step: number;
}
```

### 14.4 前端开发规则

#### 14.4.1 组件开发规范

```
规则 F-001: 所有新组件必须使用函数式组件 + TypeScript
规则 F-002: 样式必须使用 Tailwind CSS，禁止内联 style 属性（动态值除外）
规则 F-003: 组件文件命名：PascalCase.tsx，Hook 文件命名：camelCase.ts
规则 F-004: 每个组件必须有 Props 类型定义，使用 interface 而非 type
规则 F-005: 状态管理使用 Zustand，禁止在页面级组件使用大量 useState（>5个时应抽 Store）
规则 F-006: API 响应必须通过 toCamelCase() 转换，请求参数必须转为 snake_case
规则 F-007: 复用已有 common 组件（StatCard/SectionCard/Button/Select 等），禁止重复实现
规则 F-008: 图表必须使用 Recharts，禁止引入其他图表库
规则 F-009: 新增组件必须在 components/index.ts 或对应模块的 index.ts 中导出
规则 F-010: 每个新增组件必须有对应的 __tests__ 测试文件
```

#### 14.4.2 数据流规范

```
规则 F-011: API 调用统一通过 src/api/backtest.ts 中的 backtestApi 对象
规则 F-012: SSE 流式数据使用现有 useBacktestStream hook，扩展事件类型
规则 F-013: 回测结果缓存在 Zustand store 中，页面切换不丢失
规则 F-014: 所有数值展示必须格式化：百分比保留2位、比率保留2位、金额保留0位
规则 F-015: 错误处理统一使用 ApiErrorAlert 组件，SSE 错误通过 ToastViewport 通知
```

---

## 15. 后端功能布局与实现细节

> **前提**：基于现有 `api/` 层的 FastAPI + Pydantic 架构，在现有 `api/v1/endpoints/backtest.py` 基础上扩展。

### 15.1 现有后端资源盘点

#### 15.1.1 已有 API 端点

```
api/v1/endpoints/backtest.py:
  POST   /run                # 触发 AI 验证回测
  POST   /run/stream         # SSE 流式回测
  GET    /run/stream         # SSE 流式回测(EventSource兼容)
  GET    /results            # 分页获取回测结果
  GET    /performance        # 整体绩效指标
  GET    /performance/{code} # 单股绩效指标
  GET    /equity-curve       # 权益曲线
  GET    /kline-stats        # K线数据统计
  GET    /portfolio/stream   # SSE 流式组合回测
  POST   /portfolio          # 运行组合回测
```

#### 15.1.2 已有 Schema

```
api/v1/schemas/backtest.py:
  BacktestRunRequest     # 回测运行请求
  BacktestRunResponse    # 回测运行响应
  BacktestResultItem     # 单条回测结果（28个字段）
  BacktestResultsResponse # 分页结果
  PerformanceMetrics     # 绩效指标
  EquityCurveResponse    # 权益曲线
```

#### 15.1.3 已有服务层

```
src/alpha/portfolio_simulator.py  # 组合模拟器（需重构）
src/alpha/alpha_evaluator.py      # Alpha 评估器
src/alpha/alpha_scorer.py         # Alpha 评分器
```

### 15.2 新增后端模块结构

```
src/backtest/                          # 🔑 新增：回测引擎模块
├── __init__.py                        # 公共 API 导出
├── engine.py                          # Backtest 主类 (FR-001)
├── strategy.py                        # BacktestStrategy 基类 (FR-001)
├── order.py                           # Order / Trade / Position 数据类 (FR-004)
├── broker.py                          # _Broker 模拟经纪商 (FR-005/006)
├── stats.py                           # compute_stats() 统计引擎 (FR-009)
├── plotting.py                        # HTML 报告生成 (FR-010)
├── optimizer.py                       # 参数优化器 (FR-012/014)
├── presets.py                         # BacktestPresets 参数预设 (FR-011)
├── exit_rules.py                      # ExitRule / ExitReason (FR-007)
├── position_sizing.py                 # 仓位管理策略 (FR-008)
├── lib.py                             # 辅助函数
├── strategies/                        # 内置策略
│   ├── __init__.py
│   ├── signal_strategy.py             # SignalStrategy (FR-017)
│   ├── trailing_strategy.py           # TrailingStrategy (FR-015/018)
│   └── ai_prediction_strategy.py      # AI 预测策略 (FR-003)
├── adapters/                          # 策略适配器
│   ├── __init__.py
│   ├── yaml_strategy.py               # YAML → Strategy (FR-002)
│   └── ai_signal_adapter.py           # AI 信号适配器
└── tests/                             # 测试

# 后端服务层
src/services/
├── backtest_service.py                # 🔑 新增：回测服务（调度层）
└── ...

# API 层扩展
api/v1/
├── endpoints/
│   ├── backtest.py                    # ⚠️ 扩展：新增策略回测/优化/MC 端点
│   └── ...
├── schemas/
│   ├── backtest.py                    # ⚠️ 扩展：新增 Schema
│   └── ...
```

### 15.3 新增 API 端点详细设计

#### 15.3.1 策略回测端点

```python
# api/v1/endpoints/backtest.py 新增

@router.post("/strategy", response_model=StrategyBacktestResponse)
async def run_strategy_backtest(
    request: StrategyBacktestRequest,
    db: DatabaseManager = Depends(get_database_manager),
):
    """
    运行策略回测。
    
    流程：
    1. 验证策略名存在
    2. 加载 YAML 策略 → 生成 YAMLStrategy
    3. 加载 K 线数据
    4. 应用参数预设（如有）
    5. 应用因子覆盖（如有）
    6. 执行 Backtest.run()
    7. 保存结果到数据库
    8. 返回结果
    """

@router.post("/strategy/stream")
async def run_strategy_backtest_stream(
    request: StrategyBacktestRequest,
    db: DatabaseManager = Depends(get_database_manager),
):
    """SSE 流式策略回测"""

@router.get("/strategies", response_model=List[StrategyInfoResponse])
async def list_strategies():
    """
    获取可用策略列表。
    扫描 strategies/*.yaml，返回每个策略的元信息和 factors 定义。
    """

@router.get("/presets", response_model=List[PresetResponse])
async def list_presets():
    """获取参数预设列表（16种）"""

@router.get("/presets/{stock_code}", response_model=PresetResponse)
async def get_preset_for_stock(stock_code: str):
    """根据股票代码自动匹配参数预设"""
```

#### 15.3.2 参数优化端点

```python
@router.post("/optimize", response_model=OptimizeResponse)
async def run_optimization(
    request: OptimizeRequest,
    background_tasks: BackgroundTasks,
    db: DatabaseManager = Depends(get_database_manager),
):
    """
    运行参数优化。
    
    注意：优化可能耗时较长，对于网格搜索建议：
    - 参数组合 < 100：同步执行
    - 参数组合 ≥ 100：后台执行，返回 task_id
    """

@router.get("/optimize/{task_id}", response_model=OptimizeResponse)
async def get_optimization_result(task_id: str):
    """查询优化任务结果"""
```

#### 15.3.3 蒙特卡洛端点

```python
@router.post("/montecarlo", response_model=MontecarloResponse)
async def run_montecarlo(
    request: MontecarloRequest,
    background_tasks: BackgroundTasks,
):
    """运行蒙特卡洛模拟"""
```

#### 15.3.4 报告端点

```python
@router.get("/report/{result_id}")
async def get_backtest_report(result_id: str):
    """获取 HTML 回测报告"""

@router.get("/report/{result_id}/download")
async def download_backtest_report(result_id: str):
    """下载 HTML 报告文件"""
```

### 15.4 新增 Pydantic Schema

```python
# api/v1/schemas/backtest.py 新增

class ExitRuleConfig(BaseModel):
    trailing_stop_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    max_hold_days: Optional[int] = None
    partial_exit_enabled: bool = False
    partial_exit_pct: float = 0.5
    signal_threshold: Optional[float] = None
    fixed_days: Optional[int] = None

class StrategyBacktestRequest(BaseModel):
    strategy: str                          # 策略名（如 ma_golden_cross）
    codes: List[str] = []                  # 股票代码列表
    cash: float = 100000                   # 初始资金
    commission: float = 0.0003             # 佣金率
    slippage: float = 0.001                # 滑点率
    stamp_duty: float = 0.001              # 印花税率
    start_date: Optional[str] = None       # 开始日期
    end_date: Optional[str] = None         # 结束日期
    factors: Optional[Dict[str, float]] = None  # 因子覆盖
    preset: Optional[str] = None           # 预设名
    exit_rules: Optional[ExitRuleConfig] = None  # 平仓规则

class StrategyBacktestResponse(BaseModel):
    result_id: str
    strategy_name: str
    symbol: str
    start_date: str
    end_date: str
    initial_cash: float
    stats: BacktestStatsSchema
    trades: List[BacktestTradeSchema]
    equity_curve: List[EquityCurvePointSchema]
    engine_version: str = "v2"
    preset_name: Optional[str] = None
    elapsed_seconds: float

class BacktestStatsSchema(BaseModel):
    # 收益（7项）
    return_pct: float
    return_ann_pct: float
    cagr_pct: Optional[float] = None
    buy_hold_return_pct: float
    exposure_time_pct: float
    equity_final: float
    equity_peak: float
    # 风险（5项）
    volatility_ann_pct: float
    max_drawdown_pct: float
    avg_drawdown_pct: float
    max_drawdown_duration: Optional[str] = None
    avg_drawdown_duration: Optional[str] = None
    # 风险调整（3项）
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    calmar_ratio: Optional[float] = None
    # CAPM（2项）
    alpha_pct: Optional[float] = None
    beta: Optional[float] = None
    # 交易（9项）
    trade_count: int
    win_rate_pct: float
    best_trade_pct: Optional[float] = None
    worst_trade_pct: Optional[float] = None
    avg_trade_pct: Optional[float] = None
    profit_factor: Optional[float] = None
    expectancy_pct: Optional[float] = None
    sqn: Optional[float] = None
    kelly_criterion: Optional[float] = None
    # A股扩展（4项）
    turnover_rate: Optional[float] = None
    day_win_rate: Optional[float] = None
    profit_loss_ratio: Optional[float] = None
    total_commission: Optional[float] = None

class BacktestTradeSchema(BaseModel):
    size: float
    entry_bar: int
    exit_bar: int
    entry_price: float
    exit_price: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    pnl: float
    return_pct: float
    commission: float
    entry_time: str
    exit_time: str
    duration: Optional[str] = None
    tag: Optional[str] = None
    exit_reason: Optional[str] = None
    position_pct: float = 1.0

class StrategyInfoResponse(BaseModel):
    name: str
    display_name: str
    description: str
    category: str
    factors: List[StrategyFactorSchema]
    market_regimes: List[str]

class StrategyFactorSchema(BaseModel):
    id: str
    display_name: str
    type: str       # 'int' | 'float'
    default: float
    range: List[float]
    step: float

class PresetResponse(BaseModel):
    name: str
    display_name: str
    activity_level: str
    cap_size: str
    threshold: float
    trailing_stop_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    max_hold_days: Optional[int] = None
    position_sizing: str = 'full'
    fee_rate: float = 0.0015
    min_confidence: Optional[float] = None
    min_ret_5d: Optional[float] = None
    partial_exit_enabled: bool = False

class OptimizeRequest(BaseModel):
    strategy: str
    codes: List[str] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    maximize: str = "sharpe_ratio"
    method: str = "grid"          # 'grid' | 'bayesian'
    factor_ranges: Dict[str, List[float]]
    constraint: Optional[str] = None
    max_tries: Optional[int] = None

class OptimizeResponse(BaseModel):
    task_id: Optional[str] = None
    status: str                   # 'running' | 'completed' | 'failed'
    best_params: Optional[Dict[str, float]] = None
    best_value: Optional[float] = None
    best_stats: Optional[BacktestStatsSchema] = None
    heatmap: Optional[Dict[str, float]] = None
    total_trials: Optional[int] = None
    elapsed_seconds: Optional[float] = None

class MontecarloRequest(BaseModel):
    strategy: str
    codes: List[str] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    n_simulations: int = 1000
    frac: float = 1.0

class MontecarloResponse(BaseModel):
    original_stats: BacktestStatsSchema
    simulation_stats: MontecarloStatsSchema
    distribution: List[Dict[str, float]]
    elapsed_seconds: float
```

### 15.5 后端服务层设计

```python
# src/services/backtest_service.py

class BacktestService:
    """回测服务层 — 调度回测引擎和现有模块"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    # ---- 策略回测 ----
    async def run_strategy_backtest(
        self,
        strategy_name: str,
        codes: List[str],
        cash: float = 100000,
        commission: float = 0.0003,
        slippage: float = 0.001,
        stamp_duty: float = 0.001,
        start_date: str = None,
        end_date: str = None,
        factors: Dict[str, float] = None,
        preset: str = None,
        exit_rules: Dict = None,
    ) -> BacktestResult:
        """
        策略回测完整流程：
        1. 加载 YAML 策略
        2. 应用预设参数
        3. 应用因子覆盖
        4. 加载 K 线数据（通过现有 data_provider）
        5. 构建 ExitRule
        6. 创建 YAMLStrategy 实例
        7. 执行 Backtest.run()
        8. 保存结果
        9. 返回 BacktestResult
        """
        pass
    
    # ---- 参数优化 ----
    async def run_optimization(
        self,
        strategy_name: str,
        codes: List[str],
        maximize: str,
        method: str,
        factor_ranges: Dict[str, List[float]],
        constraint: str = None,
        max_tries: int = None,
        **kwargs,
    ) -> OptimizeResult:
        """
        参数优化流程：
        1. 验证参数范围
        2. 创建 Backtest 实例
        3. 调用 Backtest.optimize()
        4. 保存结果
        5. 返回 OptimizeResult
        """
        pass
    
    # ---- 蒙特卡洛 ----
    async def run_montecarlo(
        self,
        strategy_name: str,
        codes: List[str],
        n_simulations: int = 1000,
        frac: float = 1.0,
        **kwargs,
    ) -> MontecarloResult:
        """
        蒙特卡洛模拟流程：
        1. 加载原始数据
        2. 生成 n_simulations 组随机数据
        3. 逐个执行回测
        4. 统计结果分布
        5. 返回 MontecarloResult
        """
        pass
    
    # ---- 报告生成 ----
    async def generate_html_report(self, result_id: str) -> str:
        """根据回测结果 ID 生成 HTML 报告文件"""
        pass
    
    # ---- 策略列表 ----
    async def list_strategies(self) -> List[StrategyInfo]:
        """扫描 strategies/*.yaml，解析返回策略列表"""
        pass
    
    # ---- 预设匹配 ----
    async def match_preset(self, stock_code: str) -> BacktestPreset:
        """根据股票属性（活跃度+市值）自动匹配参数预设"""
        pass
```

### 15.6 后端开发规则

```
规则 B-001: 所有新端点必须在 api/v1/endpoints/backtest.py 中添加，使用 APIRouter
规则 B-002: 所有新 Schema 必须在 api/v1/schemas/backtest.py 中添加，继承 BaseModel
规则 B-003: 回测引擎代码必须放在 src/backtest/ 目录，不与 API 层混用
规则 B-004: 服务层(src/services/backtest_service.py)是 API 和引擎之间的唯一调度层
规则 B-005: 数据库操作必须通过现有 DatabaseManager，禁止直接 sqlite3
规则 B-006: K线数据获取必须通过现有 data_provider 层，禁止直接读文件
规则 B-007: 所有耗时操作(>5s)必须支持 SSE 流式进度或后台任务
规则 B-008: 错误处理统一返回 {error: str, message: str} 格式，中文错误信息
规则 B-009: 回测结果必须持久化到数据库，result_id 作为唯一标识
规则 B-010: 现有 /run, /results, /performance 等 API 必须保持向后兼容
规则 B-011: 新增的策略回测 API 不影响现有 AI 验证回测的逻辑
规则 B-012: 印花税仅在卖出时收取，佣金双向收取，T+1 限制在 Broker 中实现
规则 B-013: 回测引擎必须支持引擎版本号(engine_version='v2')，与 v1 结果可区分
```

---

## 16. Agent 开发规则（Harness 框架扩展）

> **核心原则**：这份 PRD 是给 Agent 程序执行的，必须包含足够的约束、边界和判断规则，确保 Agent 在无人监督下能正确实现。

### 16.1 总则

```
规则 A-001: 本文档是回测系统优化的唯一权威需求来源，Agent 在实现中遇到歧义时以本 PRD 为准
规则 A-002: Agent 必须按照 Phase 1 → Phase 2 → Phase 3 → Phase 4 的顺序实施，禁止跨 Phase 开发
规则 A-003: 每个 Phase 完成后，Agent 必须运行该 Phase 对应的所有测试，测试通过后方可进入下一 Phase
规则 A-004: Agent 禁止修改现有 /run, /results, /performance 等 API 的行为，仅允许新增端点
规则 A-005: Agent 禁止删除或重命名现有文件，仅允许新增文件或在现有文件中追加代码
规则 A-006: Agent 必须在每次代码变更后运行 lint 检查，确保无 error 级别问题
规则 A-007: Agent 每完成一个 FR（功能需求），必须在代码中添加 # FR-XXX 标记注释
```

### 16.2 代码实现规则

#### 16.2.1 Python 后端规则

```
规则 BP-001: 回测引擎核心模块(src/backtest/)禁止导入 api/ 或 services/ 层的代码（单向依赖）
规则 BP-002: BacktestStrategy 基类的 public 方法签名必须与本文档 6.1 FR-001 完全一致
规则 BP-003: 统计指标的计算逻辑必须与 backtesting.py 的 _stats.py 对齐，偏差 < 0.01%
规则 BP-004: A股 T+1 规则：当日买入的股票不可当日卖出，在 broker._process_orders() 中实现
规则 BP-005: 印花税：仅卖出时收取，税率 0.1%，在 broker fee_model 中实现
规则 BP-006: 佣金：双向收取，最低 5 元，在 broker fee_model 中实现
规则 BP-007: 所有浮点数比较必须使用 math.isclose() 或 np.isclose()，禁止 ==
规则 BP-008: 回测主循环禁止使用 pandas.DataFrame.iterrows()，必须使用 numpy 数组操作
规则 BP-009: 保存到数据库的 JSON 字段必须使用 json.dumps(ensure_ascii=False)
规则 BP-010: YAML 策略解析失败时必须抛出明确的 YAMLParseError，包含策略名和具体错误行
规则 BP-011: K线数据缺失日期时使用前向填充(ffill)，跳过非交易日
规则 BP-012: 回测结果中所有时间必须为 UTC+8 时区的 ISO 8601 格式
```

#### 16.2.2 TypeScript 前端规则

```
规则 BF-001: 新增组件必须在 components/backtest/ 目录下，文件名 PascalCase.tsx
规则 BF-002: 新增 Hook 必须在 hooks/ 目录下，文件名 camelCase.ts
规则 BF-003: 新增 Store 必须在 stores/ 目录下，文件名 camelCaseStore.ts
规则 BF-004: 新增 Type 必须在 types/backtest.ts 中追加，禁止创建新类型文件
规则 BF-005: 新增 API 方法必须在 api/backtest.ts 的 backtestApi 对象中追加
规则 BF-006: 所有 API 响应必须通过 toCamelCase() 转换键名
规则 BF-007: 所有 API 请求参数必须转为 snake_case
规则 BF-008: 图表必须使用 Recharts，Recharts 不支持的功能使用 Plotly（需新增依赖）
规则 BF-009: 表格排序/筛选必须在前端实现，禁止每次操作发 API 请求
规则 BF-010: 权益曲线数据点 > 1000 时使用 Recharts 的 isAnimationActive={false} 优化渲染
规则 BF-011: 回测结果页面的核心指标卡片(StatCard)必须在 3s 内渲染完成
规则 BF-012: 参数预设选择器必须显示预设的完整参数列表，供用户确认
```

### 16.3 测试规则

```
规则 T-001: 每个 FR 必须至少有一个对应的测试用例
规则 T-002: Python 测试使用 pytest，放在 src/backtest/tests/ 目录
规则 T-003: TypeScript 测试使用 vitest，放在 components/backtest/__tests__/ 目录
规则 T-004: 回测引擎的统计指标必须使用 backtesting.py 的标准数据集(GOOG)做对照测试
规则 T-005: A股 T+1 规则必须有专门的测试用例：验证当日买入不可当日卖出
规则 T-006: 手续费计算必须有专门的测试用例：验证佣金双向+印花税卖出+最低5元
规则 T-007: 平仓规则优先级必须有专门的测试用例：验证多规则同时触发时的优先级
规则 T-008: YAML 策略适配器必须有针对每个策略的集成测试（至少覆盖 5 个策略）
规则 T-009: 前端组件必须有渲染快照测试
规则 T-010: API 端点必须有集成测试，验证请求/响应格式
```

### 16.4 文件变更规则

```
规则 FC-001: 新增文件清单（Agent 必须创建这些文件）：

src/backtest/__init__.py
src/backtest/engine.py
src/backtest/strategy.py
src/backtest/order.py
src/backtest/broker.py
src/backtest/stats.py
src/backtest/plotting.py
src/backtest/optimizer.py
src/backtest/presets.py
src/backtest/exit_rules.py
src/backtest/position_sizing.py
src/backtest/lib.py
src/backtest/strategies/__init__.py
src/backtest/strategies/signal_strategy.py
src/backtest/strategies/trailing_strategy.py
src/backtest/strategies/ai_prediction_strategy.py
src/backtest/adapters/__init__.py
src/backtest/adapters/yaml_strategy.py
src/backtest/adapters/ai_signal_adapter.py
src/services/backtest_service.py

apps/dsa-web/src/components/backtest/StrategySelector.tsx
apps/dsa-web/src/components/backtest/StrategyParamForm.tsx
apps/dsa-web/src/components/backtest/PresetSelector.tsx
apps/dsa-web/src/components/backtest/ExitRuleForm.tsx
apps/dsa-web/src/components/backtest/EquityCurveChart.tsx
apps/dsa-web/src/components/backtest/DrawdownChart.tsx
apps/dsa-web/src/components/backtest/KlineTradeChart.tsx
apps/dsa-web/src/components/backtest/ExitReasonPieChart.tsx
apps/dsa-web/src/components/backtest/MonthlyHeatmap.tsx
apps/dsa-web/src/components/backtest/OptimizeConfigForm.tsx
apps/dsa-web/src/components/backtest/ParamHeatmap.tsx
apps/dsa-web/src/components/backtest/MonteCarloResult.tsx
apps/dsa-web/src/components/backtest/BacktestReportExport.tsx
apps/dsa-web/src/stores/backtestStore.ts
apps/dsa-web/src/hooks/useStrategyList.ts
apps/dsa-web/src/hooks/useBacktestPreset.ts
apps/dsa-web/src/hooks/useStrategyBacktest.ts
apps/dsa-web/src/hooks/useBacktestOptimize.ts
apps/dsa-web/src/hooks/useMonteCarlo.ts

规则 FC-002: 修改文件清单（Agent 必须在这些文件中追加代码，禁止删除现有代码）：

api/v1/endpoints/backtest.py        # 追加新端点
api/v1/schemas/backtest.py          # 追加新 Schema
apps/dsa-web/src/types/backtest.ts  # 追加新类型
apps/dsa-web/src/api/backtest.ts    # 追加新 API 方法
apps/dsa-web/src/pages/BacktestPage.tsx  # 重构为多 Tab 布局
apps/dsa-web/src/components/backtest/OverviewTab.tsx      # 扩展
apps/dsa-web/src/components/backtest/PerformanceTab.tsx   # 扩展
apps/dsa-web/src/components/backtest/TradeTab.tsx         # 扩展
apps/dsa-web/src/components/backtest/RiskTab.tsx          # 扩展
apps/dsa-web/src/components/backtest/TradeDetailTable.tsx # 扩展
apps/dsa-web/src/components/backtest/BacktestProgress.tsx # 适配
apps/dsa-web/src/hooks/index.ts      # 追加导出
apps/dsa-web/src/stores/index.ts     # 追加导出
```

### 16.5 分阶段交付规则

```
规则 PD-001: Phase 1 完成标准 = 以下测试全部通过：
  - test_engine.py: Backtest.run() 返回 25+ 指标
  - test_broker.py: 市价单/限价单/止损单/止盈单撮合正确
  - test_broker.py: T+1 限制正确、手续费计算正确
  - test_stats.py: 与 backtesting.py 标准数据集对照偏差 < 0.01%
  - test_exit_rules.py: 所有 8 种平仓规则独立正确，优先级正确
  - test_strategy.py: 自定义 Strategy 子类 init/next 正确调用

规则 PD-002: Phase 2 完成标准 = Phase 1 测试 + 以下测试全部通过：
  - test_yaml_strategy.py: 至少 5 个 YAML 策略可正确解析和执行
  - test_presets.py: 16 种预设参数正确
  - 前端: /backtest 页面策略回测 Tab 可用，结果可展示
  - 前端: 核心指标卡片 + 权益曲线图 + 交易明细表可渲染

规则 PD-003: Phase 3 完成标准 = Phase 2 测试 + 以下测试全部通过：
  - test_optimizer.py: 网格搜索遍历完整，约束过滤正确
  - 前端: 参数优化 Tab 可用，热力图可渲染
  - 前端: 追踪止损策略可执行

规则 PD-004: Phase 4 完成标准 = Phase 3 测试 + 以下测试全部通过：
  - 性能基准: 1年日线 < 5s，3年日线 < 15s
  - 前端: 蒙特卡洛 Tab 可用
  - 前端: HTML 报告可下载
```

### 16.6 禁止操作清单

```
规则 FB-001: 禁止删除现有回测 API 端点
规则 FB-002: 禁止修改现有 BacktestResultItem 的字段名
规则 FB-003: 禁止在回测引擎中引入 TensorFlow/PyTorch 等深度学习框架
规则 FB-004: 禁止在前端引入 Ant Design / Material UI 等 UI 组件库
规则 FB-005: 禁止修改 tailwind.config.js 的主题配置
规则 FB-006: 禁止修改现有 Zustand store（analysisStore/stockPoolStore/agentChatStore）的结构
规则 FB-007: 禁止在回测引擎中使用全局变量或单例模式
规则 FB-008: 禁止在回测主循环中使用 try/except 静默吞掉异常
规则 FB-009: 禁止提交大于 500KB 的数据文件到 Git
规则 FB-010: 禁止硬编码股票代码、日期或策略名（必须通过参数传入）
```

### 16.7 错误处理规则

```
规则 EH-001: 回测引擎内部错误必须使用自定义异常类：
  - BacktestError (基类)
  - InsufficientDataError (数据不足)
  - StrategyError (策略执行错误)
  - BrokerError (经纪商错误)
  - YAMLParseError (YAML 解析错误)
  - OptimizationError (优化器错误)

规则 EH-002: API 层错误必须返回统一格式：
  {"error": "error_code", "message": "中文错误描述"}
  HTTP 状态码：400(参数错误) / 404(资源不存在) / 422(验证失败) / 500(内部错误)

规则 EH-003: 前端错误展示：
  - API 错误：ApiErrorAlert 组件
  - SSE 连接断开：Toast 通知 + 自动重连
  - 回测结果为空：EmptyState 组件
  - 参数验证失败：Input 下方红色提示文字

规则 EH-004: 回测引擎遇到 NaN/Inf 数据时必须抛出 InsufficientDataError，禁止静默跳过
规则 EH-005: 权益归零时必须停止回测，记录已执行的交易，在结果中标注 _bankrupt=True
```

### 16.8 性能规则

```
规则 PF-001: 回测主循环必须使用 numpy 向量化操作，禁止逐行 Python 循环计算指标
规则 PF-002: K线数据必须一次性加载为 numpy 数组，禁止逐 bar 从数据库查询
规则 PF-003: 参数优化必须支持多进程并行（multiprocessing.Pool）
规则 PF-004: 前端权益曲线数据点 > 2000 时必须降采样展示
规则 PF-005: HTML 报告生成时间 < 10s（含图表渲染）
规则 PF-006: 策略列表 API 响应时间 < 200ms
规则 PF-007: 回测结果 API 响应时间 < 500ms（不含回测执行时间）
```

### 16.9 安全规则

```
规则 SEC-001: 回测参数中的 constraint 表达式禁止包含 import/exec/eval/__ 等危险关键字
规则 SEC-002: YAML 策略文件禁止包含 Python 代码执行（如 !!python/object）
规则 SEC-003: 回测结果中禁止包含用户敏感信息（API Key、账户信息等）
规则 SEC-004: 参数优化后台任务必须有超时限制（max 30 分钟）
规则 SEC-005: 蒙特卡洛模拟次数上限为 10000
```

---

## 17. 验收检查清单

### 17.1 Phase 1 验收

- [ ] `BacktestStrategy` 基类可被继承，init/next 正确调用
- [ ] `Backtest(data, MyStrategy).run()` 返回 25+ 统计指标
- [ ] 市价单、限价单、止损单、止盈单正确执行
- [ ] A股 T+1 规则正确（当日买入不可卖出）
- [ ] 手续费正确（佣金双向 + 印花税卖出 + 最低5元）
- [ ] 8 种平仓规则独立正确，优先级正确
- [ ] 统计指标与 backtesting.py 对照偏差 < 0.01%
- [ ] 所有 Phase 1 测试通过

### 17.2 Phase 2 验收

- [ ] 21 个 YAML 策略可自动转换为 Strategy 子类
- [ ] 16 种参数预设可正确加载
- [ ] `/backtest` 页面策略回测 Tab 可用
- [ ] 策略选择器、参数表单、预设选择器、平仓规则表单正常工作
- [ ] 回测结果核心指标卡片 + 权益曲线图 + 交易明细表可渲染
- [ ] HTML 交互式报告可生成
- [ ] 所有 Phase 2 测试通过

### 17.3 Phase 3 验收

- [ ] 参数优化（网格搜索）可用
- [ ] 热力图可视化可用
- [ ] 追踪止损策略可用
- [ ] 信号策略可用
- [ ] 平仓原因统计饼图可用
- [ ] 月度收益热力图可用
- [ ] 所有 Phase 3 测试通过

### 17.4 Phase 4 验收

- [ ] 蒙特卡洛模拟可用
- [ ] 多标的并行回测可用
- [ ] 性能基准达标（1年<5s, 3年<15s）
- [ ] 完整文档和用户指南
- [ ] 所有 Phase 4 测试通过

---

## 18. 透明度与用户可理解性体系

> **核心原则**：用户永远不会面对一个"黑箱"——无论系统在计算、等待、决策还是输出，用户都应清楚知道：**现在在干什么、干到哪里了、什么时候干完、为什么这么做**。

### 18.1 设计哲学

#### 18.1.1 透明度五层模型

```
┌─────────────────────────────────────────────────┐
│  L5: 可解释层    为什么得出这个结果？为什么这样做？   │
├─────────────────────────────────────────────────┤
│  L4: 可追溯层    这个数字从哪里来？经过了哪些变换？   │
├─────────────────────────────────────────────────┤
│  L3: 可观测层    系统当前状态是什么？进度如何？       │
├─────────────────────────────────────────────────┤
│  L2: 可预期层    下一步会发生什么？预计需要多久？     │
├─────────────────────────────────────────────────┤
│  L1: 可感知层    系统是活的还是死了？正在忙还是空闲？  │
└─────────────────────────────────────────────────┘
```

**每层必须覆盖所有异步操作和长时间计算场景。** 任何用户等待超过 **500ms** 的操作都必须提供 L1-L2 反馈；超过 **3s** 的操作必须提供 L1-L3 反馈；所有输出结果必须满足 L4-L5 要求。

#### 18.1.2 透明度设计原则

| 原则 | 说明 | 违反示例 |
|------|------|----------|
| **零静默** | 系统永远不"沉默"——任何操作都有视觉/文字反馈 | 点"开始回测"后页面无任何变化 |
| **渐进披露** | 默认展示概要，点击可展开详情 | 一上来就显示完整日志 |
| **人话优先** | 专业术语必须附带一句话人话解释 | 只写"Sharpe Ratio: 1.23" |
| **时间预期** | 所有等待都给出预估剩余时间 | 只显示"loading..."转圈 |
| **因果可见** | 任何决策/计算结果都能追溯到输入 | 用户不知道为什么某笔交易触发止损 |
| **变更醒目** | 参数变化的影响实时可视化预览 | 改了止损百分比但不知道效果 |

### 18.2 数据流转透明度

#### 18.2.1 数据管线可视化

用户在回测执行过程中，应看到数据如何一步步从原始行情变为最终结果。

**Pipeline 可视化组件** (`BacktestPipeline`)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  📊 回测数据管线                                                         │
│                                                                          │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────┐│
│  │ 原始行情  │──▶│ 策略解析  │──▶│ 信号生成  │──▶│ 订单执行  │──▶│ 统计计算││
│  │ ✓ 1205条 │   │ ✓ 完成   │   │ ⟳ 847/…  │   │ ○ 等待   │   │ ○ 等待 ││
│  └─────────┘   └──────────┘   └──────────┘   └──────────┘   └────────┘│
│                                                                          │
│  当前: 信号生成阶段 ── 已处理 847/1205 条K线 (70.3%) ── 预计剩余 2s       │
│  ████████████████████████████░░░░░░░░░░░  70%                           │
└──────────────────────────────────────────────────────────────────────────┘
```

**每个阶段的信息卡片**（点击展开）：

| 阶段 | 展开内容 | 数据示例 |
|------|----------|----------|
| 原始行情 | 数据源、时间范围、频率、缺失值处理 | "沪深 SH600519, 2024-01-02~2025-03-28, 日K, 0条缺失, 前值填充" |
| 策略解析 | YAML→Strategy 映射、参数解析、规则加载 | "趋势跟踪策略, 7个因子, 4条平仓规则, 16种参数预设可用" |
| 信号生成 | 每根K线的信号判断逻辑、触发条件 | "第847根: MA5上穿MA20 → 买入信号 (强度0.82)" |
| 订单执行 | 撮合逻辑、手续费计算、T+1约束 | "买入 500股 @185.20, 佣金¥5.00, 实付¥92,605.00" |
| 统计计算 | 各指标的计算公式和输入数据 | "最大回撤 = (谷值-峰值)/峰值 = (152,340-198,760)/198,760 = -23.3%" |

#### 18.2.2 数据溯源链

每个输出数字都有"从哪来"的溯源路径：

```typescript
// 数据溯源接口
interface DataProvenance {
  /** 指标名称 */
  metric: string;
  /** 计算公式（人话版） */
  formula_human: string;
  /** 计算公式（精确版） */
  formula_exact: string;
  /** 输入数据来源 */
  inputs: {
    field: string;       // 如 "equity_curve"
    range: string;       // 如 "2024-01-02 ~ 2025-03-28"
    record_count: number; // 如 1205
  }[];
  /** 中间计算步骤 */
  steps: {
    description: string;  // 如 "计算每日收益率"
    result_sample: string; // 如 "[-0.023, 0.015, 0.008, ...]"
  }[];
}
```

**前端展示**：指标卡片右上角显示 `🔍` 图标，点击弹出溯源面板：

```
┌─────────────────────────────────────────────────┐
│  🔍 最大回撤: -23.3%                              │
│                                                  │
│  📐 计算方式                                      │
│  人话: 从最高点跌到最低点的最大跌幅                    │
│  公式: max((谷值 - 峰值) / 峰值)                    │
│                                                  │
│  📥 输入数据                                      │
│  • 权益曲线: 2024-01-02 ~ 2025-03-28 (1205条)     │
│  • 峰值出现: 2024-10-08, ¥198,760                 │
│  • 谷值出现: 2024-12-23, ¥152,340                 │
│                                                  │
│  📝 计算步骤                                      │
│  1. 找到权益曲线的累计最高点: ¥198,760              │
│  2. 从该点向后找最低点: ¥152,340                    │
│  3. 计算回撤: (152340-198760)/198760 = -23.3%     │
│                                                  │
│  ⚠️ 含义说明                                      │
│  这意味着在最坏的情况下，你的资金从高点缩水了近1/4    │
│  一般认为 >20% 的最大回撤属于高风险                  │
└─────────────────────────────────────────────────┘
```

### 18.3 决策过程透明度

#### 18.3.1 交易决策日志

每笔交易的决策过程完整记录并可视化展示。

**交易时间线组件** (`TradeTimeline`)

```
┌──────────────────────────────────────────────────────────────────────┐
│  📋 交易 #3 决策日志                                                  │
│                                                                      │
│  🔵 2024-03-15 10:00  信号触发                                       │
│     │  MA5(185.20) 上穿 MA20(184.80) → 金叉形成                      │
│     │  信号强度: 0.82 / 阈值: 0.60 → ✅ 通过                          │
│     │  概率过滤: 72% > 65% → ✅ 通过                                  │
│     │  置信度过滤: 4.2 > 3.0 → ✅ 通过                                │
│     │  预期收益: 5.8% > 3.0% → ✅ 通过                                │
│     ▼                                                                │
│  🟢 2024-03-15 10:00  下单                                           │
│     │  买入 SH600519 @185.50 (滑点+0.30)                             │
│     │  500股 × ¥185.50 = ¥92,750.00                                  │
│     │  佣金: ¥5.00 | 过户费: ¥0.93                                   │
│     │  总成本: ¥92,755.93                                             │
│     │  同时挂出: 止盈 ¥204.05 (+10%) | 止损 ¥166.95 (-10%)            │
│     ▼                                                                │
│  🟡 2024-03-22 14:30  移动止损调整                                    │
│     │  最高价达到 ¥195.80, 移动止损从 ¥166.95 → ¥176.22 (回撤5%)      │
│     ▼                                                                │
│  🔴 2024-04-12 10:15  止损触发                                       │
│     │  当前价 ¥175.80 < 移动止损 ¥176.22                              │
│     │  卖出 SH600519 @175.50 (滑点-0.30)                             │
│     │  500股 × ¥175.50 = ¥87,750.00                                  │
│     │  佣金: ¥5.00 | 印花税: ¥87.75 | 过户费: ¥0.88                  │
│     │  总收入: ¥87,656.37                                             │
│     │                                                                │
│     │  💰 本笔盈亏: -¥5,099.56 (-5.50%)                               │
│     │  📌 平仓原因: 移动止损触发 (优先级1)                              │
│     │  📊 持仓天数: 28天                                               │
└──────────────────────────────────────────────────────────────────────┘
```

**决策日志数据结构**：

```typescript
interface TradeDecisionLog {
  trade_id: string;
  entry_date: string;
  exit_date: string | null;

  /** 入场决策链 */
  entry_decisions: {
    step: number;
    timestamp: string;        // K线日期
    type: 'signal' | 'filter' | 'risk_check' | 'order';
    description: string;      // 人话描述
    detail: string;           // 精确描述
    passed: boolean;          // 是否通过
    actual_value?: number;    // 实际值
    threshold?: number;       // 阈值
  }[];

  /** 持仓期间事件 */
  holding_events: {
    timestamp: string;
    type: 'trailing_stop_adjust' | 'partial_tp' | 'signal_disappear' | 'rebalance';
    description: string;
    before_value: number;
    after_value: number;
    reason: string;
  }[];

  /** 出场决策链 */
  exit_decisions: {
    step: number;
    timestamp: string;
    type: 'stop_loss' | 'take_profit' | 'trailing_stop' | 'signal_exit' | 
          'max_holding' | 'end_of_backtest' | 'opposite_signal';
    triggered_rule: string;       // 触发的平仓规则名
    priority: number;             // 优先级
    description: string;
    detail: string;
  }[];
}
```

#### 18.3.2 信号过滤漏斗

可视化展示信号如何被层层过滤，让用户理解"为什么有些信号没进场"。

**信号漏斗组件** (`SignalFunnel`)

```
┌──────────────────────────────────────────────────────────┐
│  🕳️ 信号过滤漏斗                                          │
│                                                          │
│  原始信号        ████████████████████████████  156 个      │
│                   │                                      │
│                   │ 概率过滤 (>65%)                        │
│                   ▼                                      │
│  概率通过        ██████████████████         98 个 (62.8%) │
│                   │                                      │
│                   │ 置信度过滤 (>3.0)                       │
│                   ▼                                      │
│  置信度通过      ██████████████           67 个 (42.9%)   │
│                   │                                      │
│                   │ 预期收益过滤 (>3.0%)                    │
│                   ▼                                      │
│  收益通过        ███████████             52 个 (33.3%)    │
│                   │                                      │
│                   │ T+1 约束 (当日买入不可卖出)              │
│                   ▼                                      │
│  可执行信号      ██████████              48 个 (30.8%)    │
│                   │                                      │
│                   │ 资金/仓位限制                          │
│                   ▼                                      │
│  实际成交        ████████                38 个 (24.4%)    │
│                                                          │
│  💡 损失分析:                                            │
│  • 概率过滤淘汰最多 (58个, 37.2%) → 考虑降低概率阈值     │
│  • 置信度过滤次之 (31个, 19.9%) → 信号质量可提升         │
│  • 资金限制淘汰10个 → 仓位管理过于保守？                  │
└──────────────────────────────────────────────────────────┘
```

#### 18.3.3 平仓原因归因

每笔平仓的触发原因和优先级判断完整展示。

```typescript
interface ExitReasonAttribution {
  trade_id: string;
  /** 所有已触发的平仓规则（按优先级排序） */
  triggered_rules: {
    priority: number;
    rule_name: string;
    rule_description: string;     // 人话：如"价格从最高点回撤超过5%"
    triggered: boolean;
    trigger_value: number | null; // 如 5.2 (回撤百分比)
    threshold: number | null;     // 如 5.0
    would_exit: boolean;          // 如果不考虑优先级，是否会导致平仓
  }[];
  /** 最终生效的规则 */
  effective_rule: string;
  effective_reason: string;       // 人话解释
}
```

**前端展示**：在交易明细表中，"平仓原因"列显示可点击的标签，点击后弹出归因面板：

```
┌──────────────────────────────────────────────────────┐
│  交易 #3 平仓原因归因                                  │
│                                                      │
│  优先级  规则            触发?  详情                    │
│  ─────  ──────────────  ────  ──────────────────     │
│  1       移动止损(5%)     ✅   回撤5.2% > 阈值5.0%    │
│  2       固定止盈(10%)    ❌   收益-5.5% < 阈值10%    │
│  3       信号消失         ❌   信号仍存在               │
│  4       最大持仓(30天)   ❌   持仓28天 < 阈值30天     │
│  5       固定止损(8%)     ❌   亏损5.5% < 阈值8%      │
│                                                      │
│  ✅ 最终触发: 移动止损(5%) — 优先级最高且已触发          │
│                                                      │
│  💡 如果关闭移动止损, 下一个会触发的是: 无               │
│     (其他规则均未触发, 该笔交易将在回测结束时强制平仓)    │
└──────────────────────────────────────────────────────┘
```

### 18.4 参数变更透明度

#### 18.4.1 参数影响预览

用户修改参数时，实时预览该参数变更对历史回测结果的影响范围。

**参数影响面板** (`ParamImpactPanel`)

```
┌────────────────────────────────────────────────────────────────────┐
│  ⚙️ 参数调整                                                        │
│                                                                    │
│  止损百分比: ────●────── 8%   (原值: 10%)                           │
│                                                                    │
│  📊 影响预览 (基于最近一次回测)                                      │
│  ┌──────────────────────────────────────────┐                      │
│  │           原值(10%)   新值(8%)   变化      │                      │
│  │  交易次数    38        42       +4        │                      │
│  │  胜率       52.6%     50.0%    -2.6%     │                      │
│  │  最大回撤   -23.3%    -19.8%   +3.5% ✅   │                      │
│  │  总收益     +12.4%    +10.1%   -2.3% ⚠️   │                      │
│  │  止损触发   8次       12次     +4次 ⚠️    │                      │
│  └──────────────────────────────────────────┘                      │
│                                                                    │
│  ⚠️ 更紧的止损会减少单笔亏损，但可能增加止损触发频率                    │
│  💡 建议: 在8%-10%之间做网格搜索，找到最优平衡点                       │
│                                                                    │
│  [▶ 用新参数重新回测]  [📋 对比两次结果]  [🔍 参数敏感性分析]          │
└────────────────────────────────────────────────────────────────────┘
```

#### 18.4.2 参数敏感性热力图

展示每个参数对关键指标的敏感程度，帮助用户理解"哪个参数最值得调"。

```typescript
interface ParamSensitivity {
  /** 参数名 */
  param_name: string;
  /** 参数当前值 */
  current_value: number;
  /** 参数范围 */
  range: [number, number];
  /** 对各指标的敏感度 (归一化到 0-1) */
  sensitivity: {
    metric: string;        // 如 "total_return"
    sensitivity_score: number; // 0-1, 1 = 极度敏感
    direction: 'positive' | 'negative' | 'non_monotonic';
    description: string;   // 如 "止损越小，总收益越低（因为频繁止损）"
  }[];
}
```

**前端展示**：

```
┌─────────────────────────────────────────────────────────────┐
│  🔬 参数敏感性分析                                            │
│                                                             │
│  参数 \ 指标   总收益   最大回撤   夏普比   胜率    交易次数    │
│  ─────────────────────────────────────────────────────────── │
│  止损%        🟡0.72   🟢0.95    🟡0.61   🟠0.45  🔴0.89    │
│  止盈%        🟡0.68   🟠0.52    🟡0.58   🟡0.63  🟠0.51    │
│  MA周期       🟠0.45   🟡0.61    🟠0.48   🟡0.55  🟡0.67    │
│  概率阈值     🔴0.85   🟡0.58    🔴0.82   🟡0.71  🔴0.91    │
│  置信度阈值   🟡0.62   🟠0.42    🟡0.59   🟠0.48  🟡0.65    │
│                                                             │
│  🔴 >0.8 极敏感  🟠 0.5-0.8 较敏感  🟡 0.3-0.5 一般         │
│  🟢 <0.3 不敏感                                            │
│                                                             │
│  💡 结论: 概率阈值和止损%对你的策略影响最大                     │
│     建议优先对这两个参数做优化                                  │
└─────────────────────────────────────────────────────────────┘
```

#### 18.4.3 参数变更历史

记录每次参数变更，支持回溯和对比。

```typescript
interface ParamChangeRecord {
  id: string;
  timestamp: string;
  /** 变更类型 */
  change_type: 'manual' | 'preset' | 'optimization' | 'reset';
  /** 变更的参数 */
  changes: {
    param: string;
    old_value: number | string;
    new_value: number | string;
  }[];
  /** 触发者 */
  source: string; // 如 "用户手动" / "预设: 活跃-大盘" / "优化结果"
  /** 变更后的回测快照ID */
  backtest_snapshot_id: string | null;
}
```

**前端展示**：参数面板底部有"变更历史"按钮，点击显示时间线：

```
  10:15  用户手动  止损: 10% → 8%       → 回测结果 #3
  10:18  预设切换  活跃-大盘 → 保守-小盘  → 回测结果 #4
  10:22  优化结果  止损: 8% → 6.5%      → 回测结果 #5
```

### 18.5 计算过程透明度

#### 18.5.1 实时进度系统

**分级进度反馈**：

| 等待时长 | 反馈级别 | UI 表现 | 信息内容 |
|----------|----------|---------|----------|
| 0-500ms | L1 静默 | 无反馈 | 操作足够快，无需打断用户 |
| 500ms-3s | L2 感知 | 按钮加载态 + 全局进度条 | "正在准备回测环境..." |
| 3s-15s | L3 观测 | Pipeline 组件 + 阶段进度 | "信号生成阶段: 45% / 预计剩余3s" |
| 15s-60s | L4 详细 | Pipeline + 日志流 + 阶段指标 | "已处理 548/1205 根K线, 产生23个买入信号, 当前权益 ¥195,420" |
| 60s+ | L5 完整 | 全部 + 中间结果预览 + 可取消 | "长期计算中, 可随时取消查看已有结果" |

#### 18.5.2 SSE 进度事件协议

**后端 SSE 事件定义**（在现有 API 设计基础上扩展）：

```python
# 进度事件类型枚举
class ProgressEventType(str, Enum):
    # 管线阶段事件
    PIPELINE_START = "pipeline_start"         # 整体开始
    PIPELINE_STAGE_START = "stage_start"      # 某阶段开始
    PIPELINE_STAGE_PROGRESS = "stage_progress" # 阶段进度更新
    PIPELINE_STAGE_COMPLETE = "stage_complete" # 某阶段完成
    PIPELINE_COMPLETE = "pipeline_complete"   # 整体完成

    # 数据加载事件
    DATA_LOADING = "data_loading"             # 数据加载中
    DATA_LOADED = "data_loaded"               # 数据加载完成
    DATA_STATS = "data_stats"                 # 数据统计信息

    # 策略解析事件
    STRATEGY_PARSING = "strategy_parsing"     # 策略解析中
    STRATEGY_PARSED = "strategy_parsed"       # 策略解析完成
    STRATEGY_PARAMS = "strategy_params"       # 解析出的参数

    # 回测执行事件
    BACKTEST_BAR_PROCESSED = "bar_processed"  # 每处理N根K线
    BACKTEST_TRADE_OPENED = "trade_opened"    # 开仓事件
    BACKTEST_TRADE_CLOSED = "trade_closed"    # 平仓事件
    BACKTEST_SIGNAL_GENERATED = "signal_gen"  # 信号产生

    # 统计计算事件
    STATS_COMPUTING = "stats_computing"       # 统计计算中
    STATS_COMPUTED = "stats_computed"         # 统计计算完成

    # 报告生成事件
    REPORT_GENERATING = "report_generating"   # 报告生成中
    REPORT_GENERATED = "report_generated"     # 报告生成完成

    # 错误事件
    ERROR = "error"                           # 错误
    WARNING = "warning"                       # 警告

    # 优化专用
    OPTIMIZATION_TRIAL = "opt_trial"          # 优化单次试验
    OPTIMIZATION_PROGRESS = "opt_progress"    # 优化整体进度
    OPTIMIZATION_BEST_UPDATE = "opt_best"     # 最优结果更新

    # 蒙特卡洛专用
    MONTECARLO_SIMULATION = "mc_sim"          # 单次模拟
    MONTECARLO_PROGRESS = "mc_progress"       # 整体进度
```

**SSE 事件数据结构**：

```python
class ProgressEvent(BaseModel):
    """统一的进度事件结构"""
    event_type: ProgressEventType
    timestamp: str                # ISO 8601
    stage: str                    # 当前阶段名称 (中文)
    stage_index: int              # 当前阶段序号 (0-based)
    total_stages: int             # 总阶段数

    # 进度信息
    progress: float               # 当前阶段进度 0.0-1.0
    overall_progress: float       # 总体进度 0.0-1.0
    elapsed_seconds: float        # 已用时间
    estimated_remaining: float | None  # 预估剩余秒数 (None=无法预估)

    # 阶段详情 (根据 event_type 不同而不同)
    detail: dict | None = None

    # 人话描述
    human_message: str            # 用户可见的中文描述

    # 子步骤 (可选, 长时间阶段内部可再分)
    sub_steps: list[dict] | None = None
```

**后端实现示例**（engine.py 中嵌入进度回调）：

```python
class BacktestEngine:
    def __init__(self, progress_callback: Callable[[ProgressEvent], None] | None = None):
        self._progress = progress_callback or (lambda e: None)

    async def run(self, data, strategy, **kwargs) -> BacktestResult:
        total_bars = len(data)

        # Stage 1: 数据加载
        self._progress(ProgressEvent(
            event_type=ProgressEventType.PIPELINE_STAGE_START,
            stage="数据加载", stage_index=0, total_stages=5,
            progress=0.0, overall_progress=0.0,
            elapsed_seconds=0, estimated_remaining=None,
            human_message="正在加载行情数据..."
        ))
        # ... 加载数据 ...
        self._progress(ProgressEvent(
            event_type=ProgressEventType.DATA_LOADED,
            stage="数据加载", stage_index=0, total_stages=5,
            progress=1.0, overall_progress=0.2,
            elapsed_seconds=elapsed, estimated_remaining=None,
            detail={"bars": total_bars, "start": str(data.index[0]),
                    "end": str(data.index[-1]), "missing": 0},
            human_message=f"已加载 {total_bars} 条K线数据"
        ))

        # Stage 2-4: 逐K线回测 (核心循环, 最频繁的进度上报)
        for i, bar in data.iterrows():
            # ... 策略逻辑 ...

            # 每处理 50 根K线 或 每 200ms 上报一次进度 (取较早者)
            if self._should_report_progress(i, last_report_time):
                pct = (i + 1) / total_bars
                remaining = (time.time() - start_time) / pct * (1 - pct)
                self._progress(ProgressEvent(
                    event_type=ProgressEventType.BACKTEST_BAR_PROCESSED,
                    stage="回测执行", stage_index=2, total_stages=5,
                    progress=pct, overall_progress=0.2 + pct * 0.6,
                    elapsed_seconds=time.time() - start_time,
                    estimated_remaining=remaining,
                    detail={
                        "bars_processed": i + 1,
                        "bars_total": total_bars,
                        "trades_opened": len(strategy._trades),
                        "current_equity": strategy._equity,
                        "signals_generated": strategy._signal_count,
                    },
                    human_message=f"正在回测... 已处理 {i+1}/{total_bars} 根K线 ({pct:.0%})"
                ))

        # Stage 5: 统计计算
        # ... 类似 ...
```

#### 18.5.3 优化/蒙特卡洛的特殊进度

**参数优化进度**：

```
┌──────────────────────────────────────────────────────────────┐
│  🔧 参数优化进行中                                            │
│                                                              │
│  方法: 网格搜索 | 总组合: 240 | 已完成: 156 (65.0%)           │
│  ████████████████████████████████░░░░░░░░░░░░░░░░  65%       │
│  预计剩余: 45s                                                │
│                                                              │
│  📊 当前最优 (实时更新):                                      │
│  ┌────────────────────────────────────────────┐              │
│  │  止损=6.5%  止盈=12%  MA=10               │              │
│  │  总收益=+28.3%  夏普=1.45  最大回撤=-17.2%  │              │
│  └────────────────────────────────────────────┘              │
│                                                              │
│  📈 收益收敛曲线:                                            │
│  28%│              ●━━━━━●━━━●                               │
│  24%│         ●━━━●                                         │
│  20%│    ●━━━●                                              │
│  16%│ ●━●                                                   │
│  12%│●                                                      │
│     └──────────────────────────────────                      │
│      0   40   80  120  156  200  240 (试验次数)               │
│                                                              │
│  最近5次试验:                                                 │
│  #156  止损=5.0% 止盈=10%  → 收益+19.8%  夏普0.92           │
│  #155  止损=7.0% 止盈=8%   → 收益+22.1%  夏普1.03           │
│  #154  止损=6.5% 止盈=12%  → 收益+28.3%  夏普1.45 ⭐最优     │
│                                                              │
│  [⏹ 停止优化]  [📋 导出中间结果]                              │
└──────────────────────────────────────────────────────────────┘
```

**蒙特卡洛模拟进度**：

```
┌──────────────────────────────────────────────────────────────┐
│  🎲 蒙特卡洛模拟                                             │
│                                                              │
│  模拟次数: 1000 | 已完成: 342 (34.2%)                         │
│  ██████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  34%       │
│  预计剩余: 1m 20s                                            │
│                                                              │
│  📊 实时分布 (已模拟342次):                                   │
│  收益率分布:                                                  │
│  -20%│░░                                                    │
│  -10%│░░░░░░                                                │
│    0%│░░░░░░░░░░░░                                          │
│   10%│░░░░░░░░░░░░░░░░░                                     │
│   20%│░░░░░░░░░░░░░░░░░░░░░                                 │
│   30%│░░░░░░░░░░░░░                                         │
│   40%│░░░░░░                                                │
│   50%│░                                                     │
│      └────────────                                          │
│                                                              │
│  当前统计:                                                    │
│  中位收益: +12.3% | 5%分位: -8.7% | 95%分位: +38.2%         │
│  破产概率(亏损>50%): 0.6%                                    │
│                                                              │
│  [⏹ 停止模拟]                                                │
└──────────────────────────────────────────────────────────────┘
```

### 18.6 结果输出透明度

#### 18.6.1 指标人话解释系统

每个专业指标都附带人话解释和风险等级评估。

```typescript
interface MetricExplanation {
  /** 指标ID */
  metric_id: string;
  /** 指标中文名 */
  name_cn: string;
  /** 一句话人话解释 */
  one_liner: string;
  /** 详细解释 (2-3句话) */
  detailed: string;
  /** 好坏判断标准 */
  rating: {
    excellent: number;  // 如 夏普>2
    good: number;       // 如 夏普>1
    fair: number;       // 如 夏普>0.5
    poor: number;       // 如 夏普<0.5
  };
  /** 当前值的评级 */
  current_rating: 'excellent' | 'good' | 'fair' | 'poor';
  /** 风险提示 */
  risk_warning?: string;
  /** 类比 (如果适用) */
  analogy?: string;
}
```

**指标解释字典**（所有 25+ 指标）：

| 指标 | 一句话人话 | 评级标准 | 类比 |
|------|-----------|----------|------|
| 总收益率 | 你的钱总共涨了(或跌了)多少 | >50%优秀, >20%良好, >0%一般, <0%差 | 存银行一年约2% |
| 年化收益率 | 折算成每年能赚多少 | >30%优秀, >15%良好, >5%一般, <5%差 | 沪深300长期约8% |
| 夏普比率 | 每承担1份风险能换来多少收益 | >2优秀, >1良好, >0.5一般, <0.5差 | 巴菲特约0.7-1.5 |
| 最大回撤 | 最惨的一次从高点跌了多少 | <10%优秀, <20%良好, <30%一般, >30%差 | 2008年A股跌了约70% |
| 卡玛比率 | 年化收益和最大回撤的比值 | >3优秀, >1.5良好, >0.75一般, <0.75差 | 衡量"值不值得冒这个险" |
| 胜率 | 赚钱交易占总交易的比例 | >60%优秀, >50%良好, >40%一般, <40%差 | 抛硬币50% |
| 盈亏比 | 平均赚的是平均亏的几倍 | >3优秀, >2良好, >1一般, <1差 | 赚3次小的亏1次大的 |
| Sortino比率 | 只算下行风险的夏普比率 | >2优秀, >1良好, >0.5一般, <0.5差 | 比夏普更关注"亏的风险" |
| Calmar比率 | 年化收益与最大回撤之比 | >3优秀, >1.5良好, >0.75一般, <0.75差 | 类似卡玛但用3年窗口 |
| 尾部比率 | 最好与最差收益的比 | >1.5优秀, >1.2良好, >1.0一般, <1.0差 | 衡量极端情况下的抗打击力 |

#### 18.6.2 结果对比面板

支持多次回测结果并列对比，差异高亮。

```
┌──────────────────────────────────────────────────────────────┐
│  📊 回测结果对比                                               │
│                                                              │
│              策略A(默认)    策略A(止损8%)   差异               │
│  ─────────────────────────────────────────────────────────── │
│  总收益      +12.4%        +10.1%         -2.3% ⚠️           │
│  年化收益    +8.2%         +6.7%          -1.5% ⚠️           │
│  夏普比率    0.95          0.88           -0.07              │
│  最大回撤    -23.3%        -19.8%         +3.5% ✅           │
│  胜率        52.6%         50.0%          -2.6%              │
│  交易次数    38            42             +4                 │
│  止损触发    8次(21%)      12次(29%)      +4次 ⚠️           │
│  平均持仓    12天          9天            -3天               │
│                                                              │
│  💡 总结: 收紧止损降低了最大回撤(好), 但增加了止损触发频率     │
│     导致整体收益下降。如果在意风控, 8%止损更优。               │
└──────────────────────────────────────────────────────────────┘
```

#### 18.6.3 AI 解读摘要

对回测结果生成一段人话总结，帮助用户快速理解。

```typescript
interface BacktestSummary {
  /** 一句话总结 */
  headline: string;
  // 示例: "该策略在过去14个月中获得12.4%收益，但最大回撤达23.3%，风险偏高"

  /** 优势列表 */
  strengths: string[];
  // 示例: ["夏普比率0.95，风险收益比尚可", "胜率52.6%，略优于随机"]

  /** 风险列表 */
  risks: string[];
  // 示例: ["最大回撤23.3%，可能超出多数人承受范围", "止损触发率21%，部分可能为假突破"]

  /** 改进建议 */
  suggestions: string[];
  // 示例: ["考虑加入移动止损减少回撤", "止损百分比从10%调至8%可能降低最大回撤"]

  /** 与基准对比 */
  benchmark_comparison: string;
  // 示例: "相比持有沪深300(同期+5.2%), 超额收益+7.2%"
}
```

**前端展示**：在结果页面顶部显示为醒目的摘要卡片：

```
┌────────────────────────────────────────────────────────────────────┐
│  🤖 回测结果解读                                                    │
│                                                                    │
│  该策略在过去14个月中获得了12.4%的收益，但期间最大回撤达到            │
│  23.3%，风险偏高。相比同期持有沪深300(+5.2%)，超额收益7.2%。        │
│                                                                    │
│  ✅ 优势                    ⚠️ 风险                                │
│  • 夏普0.95, 风险收益比尚可  • 最大回撤23.3%可能难以承受            │
│  • 胜率52.6%略优于随机       • 21%止损触发率暗示假突破较多           │
│  • 月度正收益占比66.7%       • 尾部风险偏高(尾部比率0.92)            │
│                                                                    │
│  💡 建议: 加入移动止损可降低回撤; 止损%从10→8预计降低最大回撤3.5%    │
│                                                                    │
│  [📋 查看详细指标]  [🔧 按建议优化]  [📄 生成完整报告]              │
└────────────────────────────────────────────────────────────────────┘
```

### 18.7 等待状态透明度

#### 18.7.1 等待状态分类与 UI 规范

| 等待场景 | 典型时长 | 进度类型 | UI 组件 | 最低反馈 |
|----------|----------|----------|---------|----------|
| 加载行情数据 | 1-5s | 确定进度 | 数据加载条 | "正在从数据源获取 SH600519 行情..." |
| 策略解析 | <1s | 不定进度 | 按钮加载态 | "正在解析策略..." |
| 回测执行 | 3-60s | 确定进度 | Pipeline+进度条 | 阶段+百分比+预估时间 |
| 参数优化 | 30s-10min | 确定进度 | 优化面板+收敛图 | 已完成/总数+当前最优 |
| 蒙特卡洛 | 10s-5min | 确定进度 | 模拟面板+分布图 | 已完成/总数+实时统计 |
| 生成HTML报告 | 2-10s | 确定进度 | 简单进度条 | "正在生成交互式报告..." |
| 数据抓取(外部) | 5-30s | 不定进度 | 脉冲动画+状态文字 | "正在连接数据源..." |
| 导出数据 | 1-3s | 不定进度 | 按钮加载态 | "正在导出..." |

#### 18.7.2 数据加载等待

**行情数据加载**（最常见等待场景）：

```
┌──────────────────────────────────────────────────────────────┐
│  📡 数据加载                                                  │
│                                                              │
│  ✅ SH600519 贵州茅台  日K  2024-01-02~2025-03-28  1205条    │
│  ⟳ SH000001 上证指数  日K  加载中... (2/3)                    │
│  ○ 策略参数数据     等待中                                    │
│                                                              │
│  ████████████████████░░░░░░░░░░  66%                         │
│  预计剩余: 1s                                                │
│                                                              │
│  💡 正在从本地数据库获取行情，如遇网络问题会自动重试(最多3次)     │
└──────────────────────────────────────────────────────────────┘
```

**数据源连接失败场景**：

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠️ 数据加载异常                                              │
│                                                              │
│  ❌ SH600519 数据获取失败                                     │
│  原因: 连接Tushare API超时 (等待10s后无响应)                   │
│  重试: 第2次/共3次                                           │
│                                                              │
│  [🔄 立即重试]  [📂 使用本地缓存]  [❌ 取消]                   │
│                                                              │
│  💡 提示: 可以使用本地缓存数据(截至2025-03-27)继续回测          │
│     结果可能略有差异                                          │
└──────────────────────────────────────────────────────────────┘
```

#### 18.7.3 长时间计算等待

**回测执行**（最核心等待场景）：

```
┌──────────────────────────────────────────────────────────────┐
│  🔄 回测执行中                                                │
│                                                              │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ 数据加载 │─▶│ 策略解析  │─▶│ 信号执行  │─▶│ 统计计算  │     │
│  │   ✅    │  │   ✅    │  │   ⟳    │  │   ○    │     │
│  └─────────┘  └──────────┘  └──────────┘  └──────────┘     │
│                                                              │
│  当前: 信号执行阶段                                          │
│  已处理: 847/1205 根K线 (70.3%)                               │
│  ██████████████████████████████░░░░░░░░░░░░░  70%            │
│  ⏱️ 已用时: 3.2s | 预计剩余: 1.4s                            │
│                                                              │
│  📊 实时统计:                                                │
│  信号: 买入 23次 / 卖出 19次 | 持仓中: 4笔                    │
│  当前权益: ¥195,420 (起始 ¥100,000)                           │
│  当前回撤: -8.3%                                             │
│                                                              │
│  [⏸ 暂停]  [⏹ 取消并查看已有结果]  [📋 查看实时日志]          │
└──────────────────────────────────────────────────────────────┘
```

#### 18.7.4 不可预估时长的等待

对于无法预估时长的操作（如外部API调用），使用脉冲动画 + 状态文字轮播：

```typescript
// 状态文字轮播组件
const WAITING_MESSAGES = {
  data_fetch: [
    "正在连接数据源...",
    "数据源已响应，正在获取行情...",
    "行情数据传输中...",
    "数据校验中..."
  ],
  optimization: [
    "正在搜索最优参数组合...",
    "已发现更优参数，继续搜索...",
    "优化收敛中，接近最优解...",
    "精炼搜索范围..."
  ]
};

// 每 2-3s 切换一条消息，让用户感知系统在工作
```

### 18.8 前端组件新增

#### 18.8.1 新增组件清单

| 组件名 | 所属 Tab | 功能 | 对应需求 |
|--------|----------|------|----------|
| `BacktestPipeline` | 策略回测 | 数据管线5阶段可视化 | 18.2.1 |
| `DataProvenancePanel` | 策略回测 | 指标数据溯源面板 | 18.2.2 |
| `TradeTimeline` | 策略回测 | 交易决策时间线 | 18.3.1 |
| `SignalFunnel` | 策略回测 | 信号过滤漏斗图 | 18.3.2 |
| `ExitReasonPanel` | 策略回测 | 平仓原因归因面板 | 18.3.3 |
| `ParamImpactPanel` | 策略回测 | 参数影响预览面板 | 18.4.1 |
| `ParamSensitivityHeatmap` | 参数优化 | 参数敏感性热力图 | 18.4.2 |
| `ParamChangeHistory` | 策略回测 | 参数变更历史时间线 | 18.4.3 |
| `ProgressOverlay` | 全局 | 分级进度浮层 | 18.5.1 |
| `OptimizationLivePanel` | 参数优化 | 优化实时面板(收敛图+试验列表) | 18.5.3 |
| `MonteCarloLivePanel` | 蒙特卡洛 | 蒙特卡洛实时面板(分布图+统计) | 18.5.3 |
| `MetricExplanationCard` | 策略回测 | 指标人话解释卡片 | 18.6.1 |
| `ResultComparison` | 策略回测 | 多次结果对比面板 | 18.6.2 |
| `AISummaryCard` | 策略回测 | AI解读摘要卡片 | 18.6.3 |
| `DataLoadingPanel` | 策略回测 | 数据加载等待面板 | 18.7.2 |
| `WaitingPulse` | 全局 | 不可预估等待脉冲动画 | 18.7.4 |

#### 18.8.2 新增 Hook

| Hook 名 | 功能 |
|---------|------|
| `useBacktestProgress` | 订阅 SSE 进度流，返回管线状态、当前阶段、进度百分比、预估时间 |
| `useParamSensitivity` | 请求参数敏感性分析，返回热力图数据 |
| `useTradeDecisionLog` | 获取某笔交易的完整决策日志 |
| `useResultComparison` | 管理多次回测结果的对比状态 |
| `useMetricExplanation` | 获取指标解释字典和当前评级 |

#### 18.8.3 Zustand Store 扩展

```typescript
// 在现有 backtestStore 基础上扩展
interface BacktestStore {
  // ... 现有字段 ...

  // === 透明度相关 ===
  
  /** 当前管线状态 */
  pipeline: {
    stages: {
      id: string;
      name: string;
      status: 'pending' | 'running' | 'completed' | 'error';
      progress: number;
      detail: Record<string, unknown> | null;
    }[];
    current_stage_index: number;
    overall_progress: number;
    estimated_remaining: number | null;
  };

  /** 参数变更历史 */
  paramHistory: ParamChangeRecord[];

  /** 对比结果集 */
  comparisonResults: Map<string, BacktestResult>;

  /** 实时优化状态 */
  optimizationLive: {
    total_trials: number;
    completed_trials: number;
    best_result: BacktestStats | null;
    best_params: Record<string, number> | null;
    convergence_data: { trial: number; value: number }[];
    recent_trials: { params: Record<string, number>; stats: BacktestStats }[];
  } | null;

  /** 实时蒙特卡洛状态 */
  monteCarloLive: {
    total_simulations: number;
    completed_simulations: number;
    distribution: number[];         // 收益率分布
    current_stats: {
      median: number;
      p5: number;
      p95: number;
      ruin_probability: number;
    } | null;
  } | null;
}
```

#### 18.8.4 TypeScript 新增类型

```typescript
// === 18.2 数据溯源 ===
interface DataProvenance {
  metric: string;
  formula_human: string;
  formula_exact: string;
  inputs: { field: string; range: string; record_count: number }[];
  steps: { description: string; result_sample: string }[];
}

// === 18.3 决策日志 ===
interface TradeDecisionLog {
  trade_id: string;
  entry_date: string;
  exit_date: string | null;
  entry_decisions: {
    step: number;
    timestamp: string;
    type: 'signal' | 'filter' | 'risk_check' | 'order';
    description: string;
    detail: string;
    passed: boolean;
    actual_value?: number;
    threshold?: number;
  }[];
  holding_events: {
    timestamp: string;
    type: 'trailing_stop_adjust' | 'partial_tp' | 'signal_disappear' | 'rebalance';
    description: string;
    before_value: number;
    after_value: number;
    reason: string;
  }[];
  exit_decisions: {
    step: number;
    timestamp: string;
    type: string;
    triggered_rule: string;
    priority: number;
    description: string;
    detail: string;
  }[];
}

interface ExitReasonAttribution {
  trade_id: string;
  triggered_rules: {
    priority: number;
    rule_name: string;
    rule_description: string;
    triggered: boolean;
    trigger_value: number | null;
    threshold: number | null;
    would_exit: boolean;
  }[];
  effective_rule: string;
  effective_reason: string;
}

// === 18.4 参数变更 ===
interface ParamChangeRecord {
  id: string;
  timestamp: string;
  change_type: 'manual' | 'preset' | 'optimization' | 'reset';
  changes: { param: string; old_value: number | string; new_value: number | string }[];
  source: string;
  backtest_snapshot_id: string | null;
}

interface ParamSensitivity {
  param_name: string;
  current_value: number;
  range: [number, number];
  sensitivity: {
    metric: string;
    sensitivity_score: number;
    direction: 'positive' | 'negative' | 'non_monotonic';
    description: string;
  }[];
}

// === 18.6 指标解释 ===
interface MetricExplanation {
  metric_id: string;
  name_cn: string;
  one_liner: string;
  detailed: string;
  rating: { excellent: number; good: number; fair: number; poor: number };
  current_rating: 'excellent' | 'good' | 'fair' | 'poor';
  risk_warning?: string;
  analogy?: string;
}

interface BacktestSummary {
  headline: string;
  strengths: string[];
  risks: string[];
  suggestions: string[];
  benchmark_comparison: string;
}

// === 18.5 SSE 进度 ===
interface ProgressEvent {
  event_type: string;
  timestamp: string;
  stage: string;
  stage_index: number;
  total_stages: number;
  progress: number;
  overall_progress: number;
  elapsed_seconds: number;
  estimated_remaining: number | null;
  detail: Record<string, unknown> | null;
  human_message: string;
  sub_steps: Record<string, unknown>[] | null;
}
```

### 18.9 后端新增

#### 18.9.1 新增 API 端点

| 方法 | 路径 | 功能 | 返回 |
|------|------|------|------|
| GET | `/api/v1/backtest/trade-decision/{trade_id}` | 获取交易决策日志 | `TradeDecisionLog` |
| GET | `/api/v1/backtest/exit-attribution/{trade_id}` | 获取平仓原因归因 | `ExitReasonAttribution` |
| GET | `/api/v1/backtest/signal-funnel/{run_id}` | 获取信号过滤漏斗数据 | 漏斗各层数量和百分比 |
| GET | `/api/v1/backtest/metric-explanation` | 获取指标解释字典 | `MetricExplanation[]` |
| GET | `/api/v1/backtest/provenance/{run_id}/{metric}` | 获取指标数据溯源 | `DataProvenance` |
| POST | `/api/v1/backtest/sensitivity` | 触发参数敏感性分析 | `ParamSensitivity[]` |
| GET | `/api/v1/backtest/sensitivity/{task_id}` | 查询敏感性分析结果 | `ParamSensitivity[]` |
| POST | `/api/v1/backtest/summary` | 生成回测结果AI解读 | `BacktestSummary` |
| GET | `/api/v1/backtest/compare` | 获取对比数据 | 对比结果 |
| GET | `/api/v1/backtest/param-history` | 获取参数变更历史 | `ParamChangeRecord[]` |

#### 18.9.2 后端新增模块

```
src/backtest/
├── ... (现有模块)
├── transparency/               # 透明度模块
│   ├── __init__.py
│   ├── decision_logger.py      # 交易决策日志记录器
│   ├── signal_funnel.py        # 信号过滤漏斗追踪器
│   ├── exit_attribution.py     # 平仓原因归因引擎
│   ├── metric_explainer.py     # 指标解释引擎
│   ├── data_provenance.py      # 数据溯源追踪器
│   ├── param_tracker.py        # 参数变更追踪器
│   ├── sensitivity.py          # 参数敏感性分析器
│   ├── progress.py             # 进度事件发射器
│   └── summary_generator.py    # AI摘要生成器
```

#### 18.9.3 Pydantic 新增 Schema

```python
# === 透明度相关 Schema ===

class TradeDecisionLogResponse(BaseModel):
    """交易决策日志响应"""
    trade_id: str
    entry_date: str
    exit_date: str | None = None
    entry_decisions: list[dict]
    holding_events: list[dict]
    exit_decisions: list[dict]

class ExitAttributionResponse(BaseModel):
    """平仓原因归因响应"""
    trade_id: str
    triggered_rules: list[dict]
    effective_rule: str
    effective_reason: str

class SignalFunnelResponse(BaseModel):
    """信号过滤漏斗响应"""
    run_id: str
    layers: list[dict]  # [{name, input_count, output_count, filter_pct, description}]
    total_signals: int
    executed_trades: int
    loss_analysis: list[dict]

class MetricExplanationResponse(BaseModel):
    """指标解释响应"""
    metrics: list[dict]  # MetricExplanation 列表

class DataProvenanceResponse(BaseModel):
    """数据溯源响应"""
    metric: str
    formula_human: str
    formula_exact: str
    inputs: list[dict]
    steps: list[dict]

class ParamSensitivityRequest(BaseModel):
    """参数敏感性分析请求"""
    run_id: str
    params: list[str]  # 要分析的参数名
    metrics: list[str]  # 要评估的指标名
    perturbation: float = 0.1  # 扰动比例, 默认10%

class ParamSensitivityResponse(BaseModel):
    """参数敏感性分析响应"""
    task_id: str
    status: str
    results: list[dict] | None = None

class BacktestSummaryRequest(BaseModel):
    """AI解读摘要请求"""
    run_id: str
    result: dict  # BacktestResult

class BacktestSummaryResponse(BaseModel):
    """AI解读摘要响应"""
    headline: str
    strengths: list[str]
    risks: list[str]
    suggestions: list[str]
    benchmark_comparison: str

class ParamChangeRecordResponse(BaseModel):
    """参数变更记录响应"""
    records: list[dict]
```

#### 18.9.4 进度回调集成

在 `BacktestEngine` 中嵌入进度发射逻辑（详见 18.5.2），关键实现点：

```python
# src/backtest/transparency/progress.py

class ProgressEmitter:
    """进度事件发射器 - 将引擎内部状态转换为SSE事件"""

    def __init__(self, sse_queue: asyncio.Queue | None = None):
        self._queue = sse_queue
        self._start_time = time.time()
        self._last_report_time = 0
        self._report_interval = 0.2  # 最少200ms间隔上报一次

    def _should_report(self, force_index: int | None = None) -> bool:
        """判断是否应该上报进度 (避免过于频繁)"""
        now = time.time()
        if now - self._last_report_time >= self._report_interval:
            return True
        if force_index is not None and force_index % 50 == 0:
            return True  # 每50根K线强制上报
        return False

    async def emit(self, event: ProgressEvent):
        """发射进度事件"""
        self._last_report_time = time.time()
        if self._queue:
            await self._queue.put(event)

    async def emit_stage_start(self, stage: str, stage_index: int, total: int,
                                human_msg: str):
        await self.emit(ProgressEvent(
            event_type=ProgressEventType.PIPELINE_STAGE_START,
            timestamp=datetime.now().isoformat(),
            stage=stage, stage_index=stage_index, total_stages=total,
            progress=0.0,
            overall_progress=stage_index / total,
            elapsed_seconds=time.time() - self._start_time,
            estimated_remaining=None,
            human_message=human_msg,
        ))

    async def emit_stage_progress(self, stage: str, stage_index: int, total: int,
                                   pct: float, human_msg: str, detail: dict | None = None):
        await self.emit(ProgressEvent(
            event_type=ProgressEventType.PIPELINE_STAGE_PROGRESS,
            timestamp=datetime.now().isoformat(),
            stage=stage, stage_index=stage_index, total_stages=total,
            progress=pct,
            overall_progress=(stage_index + pct) / total,
            elapsed_seconds=time.time() - self._start_time,
            estimated_remaining=self._estimate_remaining(pct),
            detail=detail,
            human_message=human_msg,
        ))

    def _estimate_remaining(self, pct: float) -> float | None:
        """根据已用时间和进度估算剩余时间"""
        if pct <= 0.01:
            return None  # 进度太少, 估算不准
        elapsed = time.time() - self._start_time
        return elapsed / pct * (1 - pct)
```

### 18.10 Agent 透明度开发规则

> 在第16章 Agent 规则基础上，追加以下透明度专项规则。

#### 18.10.1 进度反馈规则 (TP-001 ~ TP-008)

| 规则ID | 规则 | 严重级别 |
|--------|------|----------|
| TP-001 | **所有超过 500ms 的异步操作必须提供进度反馈**。包括：数据加载、回测执行、优化计算、蒙特卡洛模拟、报告生成、数据导出。不得出现空白转圈或静态"loading" | P0 |
| TP-002 | **SSE 进度事件间隔不得低于 200ms、不得超过 2s**。低于200ms 会造成前端渲染压力；超过2s 用户感知不到进展 | P0 |
| TP-003 | **预估剩余时间必须显示**。若无法精确预估，显示范围（如"约1-3分钟"）而非不显示。进度>10%后才显示预估值 | P1 |
| TP-004 | **回测执行阶段的进度必须包含已处理K线数/总数和当前权益**。不得只显示百分比 | P0 |
| TP-005 | **优化/蒙特卡洛长时间运行必须支持"取消并查看已有结果"**。取消后返回已完成的中间结果，不得丢弃 | P1 |
| TP-006 | **数据加载失败必须提供备选方案**（重试/使用缓存/取消），不得只显示错误 | P0 |
| TP-007 | **所有进度反馈文字使用中文**，格式为"正在{动作}... {已完成}/{总数} {单位} ({百分比})" | P1 |
| TP-008 | **Pipeline 可视化必须与实际后端阶段严格对应**。前端展示的阶段名和顺序必须与后端SSE事件一致 | P0 |

#### 18.10.2 决策可追溯规则 (TD-001 ~ TD-006)

| 规则ID | 规则 | 严重级别 |
|--------|------|----------|
| TD-001 | **每笔交易必须记录完整的入场决策链**（信号→过滤→风控→下单），包括每步的实际值和阈值 | P0 |
| TD-002 | **每笔交易必须记录完整的出场决策链**，包括所有已触发的平仓规则、优先级和最终生效规则 | P0 |
| TD-003 | **持仓期间事件必须记录**（移动止损调整、部分止盈、信号消失等），含变更前后值 | P1 |
| TD-004 | **平仓原因必须可归因**：用户应能看到"哪些规则触发了、哪些没触发、如果关闭某规则会怎样" | P1 |
| TD-005 | **信号过滤漏斗必须完整记录每层的输入输出数量**，不得只展示最终结果 | P1 |
| TD-006 | **决策日志数据必须持久化到数据库**，页面刷新后仍可查看 | P2 |

#### 18.10.3 指标可理解规则 (TM-001 ~ TM-006)

| 规则ID | 规则 | 严重级别 |
|--------|------|----------|
| TM-001 | **所有 25+ 统计指标必须附带人话解释**。展示方式：指标卡片右上角 `🔍` 按钮，点击弹出解释面板 | P0 |
| TM-002 | **人话解释必须包含**：一句话解释、评级标准、当前评级、风险提示(如有)、类比(如有) | P0 |
| TM-003 | **指标值必须带颜色编码**：优秀(绿)、良好(蓝)、一般(黄)、差(红)。不得全部同色 | P1 |
| TM-004 | **数据溯源必须可查**：每个指标可追溯到输入数据来源和计算步骤 | P1 |
| TM-005 | **回测结果必须生成AI解读摘要**，包含一句话总结、优势、风险、建议、与基准对比 | P1 |
| TM-006 | **摘要中不得出现没有依据的判断**。所有结论必须追溯到具体的指标值 | P0 |

#### 18.10.4 参数变更规则 (TPA-001 ~ TP-005)

| 规则ID | 规则 | 严重级别 |
|--------|------|----------|
| TPA-001 | **参数修改必须实时显示影响预览**（基于最近一次回测的近似计算），不得需要完整重新回测才能看到影响 | P1 |
| TPA-002 | **参数变更必须记录历史**（谁改的、改了什么、何时改的），支持回溯 | P1 |
| TPA-003 | **参数敏感性分析必须可触发**，结果以热力图形式展示 | P2 |
| TPA-004 | **多次回测结果必须支持并列对比**，差异高亮，附带AI总结 | P1 |
| TPA-005 | **预设切换必须展示变更了哪些参数**（前后对比），不得静默切换 | P0 |

#### 18.10.5 交互规范规则 (TI-001 ~ TI-004)

| 规则ID | 规则 | 严重级别 |
|--------|------|----------|
| TI-001 | **所有可点击的数据元素必须有 hover 提示**，解释点击后能看到什么 | P1 |
| TI-002 | **专业术语首次出现时必须显示虚线下划线**，hover 显示人话解释 | P1 |
| TI-003 | **渐进披露**：默认显示概要级信息（指标值+评级），点击展开详情（计算过程+溯源） | P0 |
| TI-004 | **空白状态必须有引导**。首次进入回测页面时，展示简要说明（3步上手）而非空白 | P1 |

### 18.11 透明度验证清单

#### Phase 1 验收（透明度相关）

- [ ] Pipeline 5阶段可视化组件正确渲染
- [ ] SSE 进度事件正确推送（间隔200ms-2s）
- [ ] 预估剩余时间显示（进度>10%后）
- [ ] 回测执行进度包含K线数和当前权益
- [ ] 数据加载失败提供重试/缓存/取消选项
- [ ] 指标卡片 `🔍` 按钮弹出人话解释面板
- [ ] 指标值颜色编码（优秀绿/良好蓝/一般黄/差红）
- [ ] 所有进度文字使用中文

#### Phase 2 验收（透明度相关）

- [ ] 交易决策时间线组件正确渲染
- [ ] 信号过滤漏斗图正确渲染
- [ ] 平仓原因归因面板正确展示优先级和触发状态
- [ ] 参数影响预览面板实时响应参数变更
- [ ] 预设切换展示参数变更对比
- [ ] AI 解读摘要卡片生成正确
- [ ] 空白状态引导页面展示
- [ ] 专业术语 hover 提示正常工作

#### Phase 3 验收（透明度相关）

- [ ] 参数敏感性热力图正确渲染
- [ ] 参数变更历史时间线正确展示
- [ ] 优化实时面板（收敛图+试验列表+当前最优）正确渲染
- [ ] 优化过程支持"取消并查看已有结果"
- [ ] 多次结果对比面板正确展示差异高亮

#### Phase 4 验收（透明度相关）

- [ ] 蒙特卡洛实时面板（分布图+统计）正确渲染
- [ ] 蒙特卡洛过程支持"取消并查看已有结果"
- [ ] 数据溯源面板展示指标计算过程
- [ ] 决策日志持久化到数据库
- [ ] 所有透明度组件响应式适配（移动端可用）
- [ ] 全流程端到端测试：从点击"开始回测"到查看"AI解读摘要"，用户全程无困惑时刻
