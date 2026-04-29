# 方案设计：策略回测系统 UX 重构

> Harness S2 产物 | 角色: Solution Architect
> 状态: 草案 | 创建: 2026-04-29

## 1. 方案概述

将 BacktestPage 从"双 Tab 分裂设计"重构为"统一入口 + TradingView 4-Tab 结果"的专业级量化回测工作台。

## 2. 架构变更

### 2.1 当前架构

```
BacktestPage
├── [验证模式 Tab] ─→ backtestApi.run() ─→ BacktestService.run_backtest()
│   └── 结果: RunResultBanner + PerformancePanel + EquityCurveChart + 明细表
└── [策略回测 Tab] ─→ apiClient.post('/backtest/portfolio') ─→ PortfolioBacktestEngine.run()
    └── 结果: 指标卡片 + 资金曲线 + TradeDetailTable
```

### 2.2 目标架构

```
BacktestPage — 统一入口
├── [顶部] 参数面板 (自适应模式提示)
│   ├── K线就绪 → "策略回测" 模式提示 ← 绿色
│   └── K线未就绪 → "历史验证" 模式提示 ← 蓝色
│
├── [中间] 股票选择 + 日期范围 + 评估窗口 + 因子slider
│
├── [底部] 「开始回测」按钮
│
├── [运行时] SSE 进度条 (阶段 + 日期 + 净值)
│
└── [结果区] TradingView 4-Tab
    ├── Tab1 概览 — 核心指标 + 净值曲线 + Benchmark对比 + 月度热力图
    ├── Tab2 绩效 — 详细指标表 (Sharpe/Sortino/Calmar/IR/TE/换手率)
    ├── Tab3 交易 — 完整明细 + 分组 + 筛选 + 搜索
    └── Tab4 风险 — 回撤曲线 + VaR + 滚动Sharpe + 最大回撤期列表
```

## 3. 模块变更清单

### 3.1 前端

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `BacktestPage.tsx` | **重构** | 去掉 Tab 分裂 → 统一入口 + 4-Tab 结果 |
| `components/backtest/OverviewTab.tsx` | **新增** | Tab1 概览 (指标+曲线+对比) |
| `components/backtest/PerformanceTab.tsx` | **新增** | Tab2 绩效 (详细指标表+热力图) |
| `components/backtest/TradeTab.tsx` | **新增** | Tab3 交易 (明细+分组+筛选) |
| `components/backtest/RiskTab.tsx` | **新增** | Tab4 风险 (回撤+VaR+滚动Sharpe) |
| `components/backtest/BacktestProgress.tsx` | **新增** | SSE 进度条组件 |
| `hooks/useBacktestProgress.ts` | **新增** | SSE Hook — 复用 useAlphaStream 模式 |
| `components/backtest/BacktestHistoryList.tsx` | **新增** | 回测历史列表 (可选对比) |
| `components/backtest/TradeDetailTable.tsx` | **增强** | +日期筛选 +按股票分组 +虚拟滚动 |
| `api/backtest.ts` | **修改** | +`runPortfolio()` 独立 120s timeout |
| `types/backtest.ts` | **修改** | +`PortfolioRunRequest/Response` 类型 |

### 3.2 后端

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `api/v1/endpoints/backtest.py` | **修改** | portfolio 端点改为异步 SSE |
| `src/core/portfolio_backtest_engine.py` | **修改** | +`run_async()` 支持 yield 进度事件 |
| `src/services/backtest_service.py` | **不修改** | 保持现有向后兼容 |

### 3.3 不修改文件 (保持兼容)

- `src/core/backtest_engine.py` — 旧引擎继续支持
- `BacktestService.run_backtest()` — 后端 API 路径不变
- `reports/` / `strategies/` — 不受影响

## 4. 接口定义

### 4.1 统一回测入口 (前端状态机)

```typescript
// BacktestPage 核心状态
type BacktestMode = 'idle' | 'running' | 'results';
type ResultTab = 'overview' | 'performance' | 'trades' | 'risk';

// 模式判断
const dataAvailable = klineStats?.ready === true;
// true  → portfolio engine (策略回测)
// false → verify engine (历史验证)
```

### 4.2 SSE 进度 API

```
GET /api/v1/backtest/portfolio/stream
  → SSE events:
    - "progress": { date: "2024-03-15", day: 45, total_days: 250, nav: 105230, stage: "scoring" }
    - "completed": { run_id: "...", metrics: {...}, nav: [...], trades: [...] }
    - "error": { message: "..." }
```

### 4.3 4-Tab 结果数据流

```
GET /api/v1/backtest/portfolio?start_date=...&end_date=...
  → POST 提交回测任务
  → 返回 { run_id: "..." }

SSE /api/v1/backtest/portfolio/stream?run_id=...
  → 实时进度 + 最终结果

回测完成后，前端持有完整的 result 对象 → 4个Tab各取所需:
  - OverviewTab: result.metrics + result.nav + result.benchmarkNav
  - PerformanceTab: result.metrics (全量指标)
  - TradeTab: result.trades
  - RiskTab: result.nav (计算回撤/VaR/滚动Sharpe)
```

## 5. 组件树设计

```
BacktestPage
├─ <header>
│  ├─ <h1>策略回测</h1>
│  ├─ <StepIndicator current={mode} />
│  └─ <DataStatusBadge />  ← Kline就绪/未就绪 指示器
│
├─ <BacktestHistoryButton />  ← 打开历史列表抽屉
│
├─ {mode === 'idle' && <ConfigPanel/>}
│  ├─ <StockSelector />  ← 复用现有代码
│  ├─ <DateRangePicker />  ← 起止日期 (默认最近3个月)
│  ├─ <EvalWindowSelector />  ← 评估窗口
│  ├─ <FactorSliders />  ← 整合 AlphaFactorPanel mini
│  └─ <button>开始回测</button>
│
├─ {mode === 'running' && <BacktestProgress />}
│
└─ {mode === 'results' && <ResultTabs />}
   ├─ <TabBar active={resultTab} onChange={setResultTab} />
   ├─ {resultTab === 'overview' && <OverviewTab />}
   ├─ {resultTab === 'performance' && <PerformanceTab />}
   ├─ {resultTab === 'trades' && <TradeTab />}
   └─ {resultTab === 'risk' && <RiskTab />}
```

## 6. 风险矩阵

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| 重构破坏现有功能 | 中 | 保留现有 API 路径不变，前端渐进替换 |
| SSE 实现复杂度 | 中 | 复用 useAlphaStream 的 EventSource 模式 |
| 4-Tab 数据量大渲染慢 | 低 | Tab懒加载 + 交易表虚拟滚动 |
| 日历缓存路径错误 | 低 | 已在本次修复中完成 (trading_calendar.json) |

## 7. 与 S1 需求的对照

| FR | 覆盖 | 实现方式 |
|----|------|---------|
| FR-01 统一入口 | ✅ | 去掉双Tab，单一ConfigPanel |
| FR-02 智能模式 | ✅ | `klineStats.ready` 决定引擎 |
| FR-03 SSE进度 | ✅ | `/backtest/portfolio/stream` |
| FR-04 4-Tab结果 | ✅ | Overview/Performance/Trade/Risk |
| FR-05 因子联动 | ✅ | FactorSliders 整合 |
| FR-06 回测历史 | ✅ | BacktestHistoryList |
| FR-07 Benchmark对比 | ✅ | OverviewTab 双曲线 |
