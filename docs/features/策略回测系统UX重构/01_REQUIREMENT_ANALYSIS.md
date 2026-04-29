# 需求分析：策略回测系统 UX 重构

> Harness S1 产物 | 角色: Requirement Analyst
> 状态: 草案 | 创建: 2026-04-29

## 1. 需求概述

对标 QuantConnect、TradingView、聚宽等主流量化平台，重构 DSA 回测系统为专业级量化回测工作台。解决当前"验证模式"和"策略回测"两个 Tab 的命名歧义、功能割裂、UX 不可理解的核心问题。

## 2. 业界调研

### 2.1 主流量化平台回测系统对比

| 维度 | QuantConnect | TradingView | 聚宽(JQ) | DSA 当前 |
|------|-------------|-------------|---------|---------|
| 策略编写 | C#/Python 代码 | Pine Script 可视化代码 | Python Notebook | ❌ 无策略编写 |
| 回测入口 | 一键 Deploy | 图表底部 Tab | 编译运行按钮 | 两按钮双模式 ❌ |
| 回测进度 | 实时 SSE 更新 | 即时完成 | 实时日志 | 无进度反馈 |
| 结果页 | 独立全屏 Results | 图表底部面板 | 右侧面板 | 内嵌在 Header 下 |
| 核心图表 | Strategy Equity + Drawdown + Benchmark | Equity + 价格叠加 | 收益曲线 + 基准 | 仅资金曲线 |
| 交易明细 | 完整交易日志 | List of Trades | 每日持仓/交易 | TradeDetailTable |
| 风险指标 | Sharpe/PSR/Return/Drawdown/Volume/Fees | Net Profit/Drawdown/Win%/Sharpe | 夏普/最大回撤/胜率 | 仅 5 指标 |
| 参数优化 | LEAN 引擎内置 | Strategy Tester 多参数 | Notebook 循环 | ❌ 无 UI |
| 命名方式 | "Backtest" | "Strategy Tester" | "回测" | "验证模式"/"策略回测" ❌ |

### 2.2 关键洞察

1. **TradingView 的 4-Tab 设计是行业最直观的**：Overview → Performance → Trades → Risk，认知递进
2. **QuantConnect 的独立全屏 Results 页** 体现了"回测是核心操作，值得独占页面"
3. **聚宽的 Notebook 模式** 适合开发者，但不适合非技术用户
4. **三大平台都没有 "验证模式" / "策略回测" 的概念分裂** — 回测就是回测，不分模式

### 2.3 用户心智模型

```
用户预期:  [配置参数] → [点击回测] → [实时进度] → [查看结果]
DSA 现状:  [选Tab?] → [两套参数] → [不知点哪个] → [超时/空结果]
```

## 3. 功能需求 (FR)

### FR-01: 统一回测入口
- **描述**：去掉"验证模式"/"策略回测"双 Tab 分裂设计。合并为单一面板，参数根据数据源自动适配。
- **验收标准**：Given 用户进入回测页面，When 看到的是统一的面板（非两个 Tab），Then 可以自然地选择股票/日期并点击"开始回测"
- **优先级**: P0

### FR-02: 智能回测模式
- **描述**：系统自动判断可用数据源，优先使用 Parquet K线数据（策略回测），fallback 到 AnalysisHistory（历史验证）。
- **验收标准**：Given K线数据就绪，When 用户点击回测，Then 自动使用策略回测引擎；Given K线未就绪但有历史记录，Then 自动使用验证回测；两种模式下都显示统一的结果界面
- **优先级**: P0

### FR-03: 回测进度实时反馈
- **描述**：回测期间展示 SSE 进度条 + 当前阶段提示，而非无反馈的 spinner。
- **验收标准**：Given 回测启动，When 后端逐日模拟中，Then 前端显示"正在回测 2023-01-03 (125/730 天) — 当前净值 ¥105,230"
- **优先级**: P1

### FR-04: 回测结果布局 — TradingView 4-Tab 模式
- **描述**：
  - Tab 1 **概览** — 核心指标卡片 (总收益/年化/夏普/最大回撤/超额收益/胜率) + 资金曲线 + Benchmark 对比
  - Tab 2 **绩效** — 详细风险指标表 (Sharpe/Sortino/Calmar/IR/TE/换手率) + 月度收益热力图
  - Tab 3 **交易** — 完整交易明细表 + 按股票分组 + 按日期筛选
  - Tab 4 **风险** — 回撤曲线 + VaR + 滚动夏普
- **验收标准**：4 个 Tab 均可正常切换，内容不重复，每个 Tab 在 2 秒内完成渲染
- **优先级**: P0

### FR-05: 参数面板与策略因子联动
- **描述**：回测参数面板展示因子 slider（复用 AlphaFactorPanel），用户拖动即可调参回测
- **验收标准**：Given 用户拖动 trend_score slider，When 点击回测，Then 使用新参数值执行回测
- **优先级**: P2

### FR-06: 回测历史管理
- **描述**：保存每次回测结果，列表展示历史回测记录（日期/参数/收益/夏普），支持对比、删除
- **验收标准**：Given 3 次回测历史，When 用户进入历史列表，Then 看到日期/stock/收益/夏普，可选 2 条进行对比
- **优先级**: P1

### FR-07: Benchmark 对比图表
- **描述**：资金曲线图上叠加 Benchmark（沪深300）走势，Y 轴同步缩放
- **验收标准**：Given 回测完成且有 benchmark 数据，When 查看概览，Then 图表显示两条曲线（组合净值 + 基准净值），并标注超额收益区域

## 4. 非功能需求 (NFR)

### NFR-01: 性能
- 回测启动响应 < 200ms（提交后立即返回 run_id）
- 回测 SSE 推送频率 ≤ 1次/秒
- 交易明细表 1000 条数据渲染 < 1s（虚拟滚动）

### NFR-02: 可理解性
- 页面标题/按钮/标签用自然语言，不含技术缩写
- 所有指标带 tooltip 解释
- 空状态有明确的原因说明 + 操作指引

### NFR-03: 超时处理
- Portfolio 回测超时 120s
- 超时后提示"回测耗时较长，已切换为后台运行，完成后将自动展示结果"

## 5. 消歧义记录

| 歧义点 | 决策 |
|--------|------|
| AMB-01 是否保留双模式 Tab | **去 Tab，统一入口** — 系统根据数据源自动选择引擎 |
| AMB-02 结果页布局 | **TradingView 4-Tab** — 概览/绩效/交易/风险 |
| AMB-03 回测是否同步 | **异步 SSE** — 提交后立即返回，SSE 推送进度 |
| AMB-04 Benchmark 默认值 | **沪深300 (000300)** — 与 Alpha 系统一致 |

## 6. 与本需求相关的历史资产

- `PortfolioBacktestEngine` — 策略回测引擎（就绪）
- `BacktestService.run_backtest()` — 验证回测（就绪）
- `AlphaFactorPanel` — 因子 slider 组件（就绪，可复用）
- `KlineRepo` — Parquet K线数据（已导入 5724 文件 / 7.5M 行）
- `TradeDetailTable` — 交易明细组件（就绪，需增强虚拟滚动）
- `useAlphaStream` — SSE Hook 模式（可复用为回测进度 Hook）
- `BacktestPage.tsx` — 当前页面（需重构）
