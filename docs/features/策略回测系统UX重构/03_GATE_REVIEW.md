# 闸门评估：策略回测系统 UX 重构

> Harness S3 产物 | 角色: Gate Reviewer
> 判定: ✅ 通过 | 2026-04-29

## 8 维度审查

### 1. 需求完整性
✅ 通过
- 7 FR + 4 NFR 均有 Given/When/Then 验收标准
- 消歧义 4 项全部确认
- 边界场景覆盖: K线未就绪/空结果/超时

### 2. 方案可行性
✅ 通过
- SSE 进度可复用 `useAlphaStream` EventSource 模式
- 4-Tab 可拆分为独立组件懒加载
- 交易日历缓存已实现并验证 (1529 日期, <1ms 读取)

### 3. 接口一致性
✅ 通过
- 新增端口 `/backtest/portfolio/stream` 与现有 `/alpha/stream` 风格一致
- 前端类型 `PortfolioRunRequest` 与后端 `BacktestParams` 字段对齐
- 4-Tab 命名与 TradingView/QuantConnect 行业惯例一致

### 4. 文件验证 — 关键检查
✅ 通过

| 文件 | 状态 | 备注 |
|------|------|------|
| `src/core/portfolio_backtest_engine.py` | ✅ 就绪 | 日历缓存已修复 |
| `src/alpha/portfolio_simulator.py` | ✅ 就绪 | 无需修改 |
| `useAlphaStream.ts` | ✅ 就绪 | 可复用 SSE 模式 |
| `TradeDetailTable.tsx` | ✅ 就绪 | 需增强虚拟滚动 |
| `BacktestPage.tsx` | ✅ 就绪 | 需重构 |

### 5. 兼容性检查
✅ 通过
- 现有 API `/backtest/results` `/backtest/overall-performance` 路径不变
- BacktestService 不修改
- 旧 `backtestApi.run()` 保留
- Portfolio endpoint 保持同步调用接口，新增 stream 变体

### 6. 安全审计
✅ 通过
- SSE 复用现有认证中间件
- 无新增文件上传/路径注入

### 7. 性能影响
✅ 通过
- `_get_trading_dates` 从 5724文件读 → 1文件读 + JSON缓存 (<10ms)
- 默认回测窗口 365→90天 (--约1/4耗时)
- 前端 4-Tab 懒加载, 交易表虚拟滚动 (<1000条)

### 8. 开发高概率疑问点
| 疑问 | 解答 |
|------|------|
| SSE 回测进度如何实现 | PortfolioBacktestEngine.run() 增加 yield 进度事件, FastAPI StreamingResponse |
| 4-Tab 如何保证不重复渲染 | React.lazy + Suspense + keepMounted=false |
| Benchmark 数据如何获取 | 复用 AlphaEvaluator 已有 benchmark_fetcher |

## 阻塞项
无。

## 条件项
| 编号 | 条件 |
|------|------|
| CND-01 | 开发前确认 `trading_calendar.json` 文件存在于 `data/kline/` |

## 验证记录
- [x] 交易日历缓存生成: 1529 日期, 2020-01-02 ~ 2026-04-27
- [x] `python -m py_compile src/core/portfolio_backtest_engine.py` ✅
- [x] `data/kline/trading_calendar.json` 文件已生成

## 判定
✅ **通过** — 可进入 S4 开发阶段。
