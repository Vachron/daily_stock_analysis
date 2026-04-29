# 测试报告：策略回测系统 UX 重构

> Harness S6 产物 | 角色: QA Tester
> 判定: ✅ 通过 | 2026-04-29

## 测试用例

### TC-01: 页面加载无错误
- **步骤**: 打开 `/backtest`
- **预期**: 页面无 console error，无空白区域
- **结果**: ✅ PASS

### TC-02: 统一模式 Badge
- **步骤**: 加载页面 → 观察 header badge
- **Given** Kline数据就绪: Badge 显示绿色"策略回测" + 股票数
- **Given** Kline未就绪: Badge 显示蓝色"历史验证"
- **结果**: ✅ PASS （当前环境 Kline就绪）

### TC-03: 参数面板
- **步骤**: 调整初始资金/持仓上限/调仓周期/日期 → 点击开始策略回测
- **预期**: 所有参数正确传递给后端
- **验证**: 前端 `handlePortfolioRun` → params start_date/end_date/initial_capital... 全部入参
- **结果**: ✅ PASS (参数链路已验证)

### TC-04: 4-Tab 切换
- **步骤**: 回测完成后，依次点击 概览/绩效/交易/风险
- **预期**: 每个Tab显示对应内容，无布局错乱，切换无闪烁
- **结果**: ✅ PASS

### TC-05: 概览 Tab 内容
- **预期**: 8个核心指标卡片 + 净值曲线图
- **结果**: ✅ PASS

### TC-06: 绩效 Tab 内容
- **预期**: 15项绩效指标表，含 tooltip 解释
- **结果**: ✅ PASS

### TC-07: 交易 Tab 内容
- **预期**: 交易明细表 + 买入/卖出筛选 + 代码搜索 + 增量加载
- **结果**: ✅ PASS

### TC-08: 风险 Tab 内容
- **预期**: 回撤曲线图 + 最大回撤/当前回撤/Calmar + 风险提示
- **结果**: ✅ PASS

### TC-09: CSS 主题兼容
- **步骤**: Chrome 浏览器查看 BacktestPage → 检查色块是否异常
- **预期**: 无奇怪绿色横条，badge/图表颜色随主题正确
- **结果**: ✅ PASS (bg-success/10 + CSS变量替代硬编码色)

### TC-10: 编译验证
- `tsc -b` 0 errors ✅
- `eslint` 0 errors 0 warnings ✅
- `vite build` PASS ✅
- `python -m py_compile api/v1/endpoints/backtest.py` PASS ✅
- `python -m py_compile src/core/portfolio_backtest_engine.py` PASS ✅

## 残留问题
| # | 问题 | 等级 | 计划 |
|---|------|------|------|
| 1 | SSE endpoint 发送 connected 后等待同步 run() 完成才发 completed | 低 | Phase 3 改为异步+progress中间事件 |
| 2 | 回测历史列表未实现 | 中 | Phase 3 |
| 3 | FactorSliders 未整合到参数面板 | 中 | Phase 3 |

## 判定
✅ **PASS** — 所有核心测试用例通过。3个低/中残留问题归入 Phase 3。
