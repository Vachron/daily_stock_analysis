# KNOWLEDGE_INDEX.md

> 本文件是项目核心代码与核心文档的位置索引。新 agent 启动后应首先阅读本文件，再按需深入。
> 最后更新：2026-04-26

## 阅读顺序

1. **本文件** — 建立全局地图
2. **AGENTS.md** — 仓库协作硬规则（唯一真源）
3. 按任务类型，进入下方对应模块的代码与文档

---

## 一、项目概览

- **定位**：股票智能分析系统，覆盖 A 股、港股、美股
- **主流程**：抓取数据 → 技术分析/新闻检索 → LLM 分析 → 生成报告 → 通知推送
- **技术栈**：Python 后端 + FastAPI + React 前端 + Electron 桌面端

## 二、入口文件

| 入口 | 文件 | 用途 |
|------|------|------|
| CLI 主入口 | `main.py` | 分析任务、定时调度、服务启动 |
| API 服务 | `server.py` | FastAPI 服务入口 |
| Web 前端 | `apps/dsa-web/` | React SPA |
| 桌面端 | `apps/dsa-desktop/` | Electron 包装 |

---

## 三、核心代码索引

### 3.1 选股与策略系统（核心链路）

| 模块 | 文件 | 职责 | 关键文档 |
|------|------|------|----------|
| 策略信号提取 | `src/core/strategy_signal_extractor.py` | 21 种策略的信号计算与评分 | [因子优化方案](docs/factor-optimization.md) |
| 选股引擎 | `src/core/screener_engine.py` | 编排选股全流程：过滤→质量分级→策略评分→排名 | — |
| 市场状态识别 | `src/core/market_regime.py` | 市场状态检测 + 策略动态权重调整 | — |
| 策略优化器 | `src/core/strategy_optimizer.py` | 历史胜率驱动的权重优化（待改造为 IC/PBO/DSR） | [因子优化方案](docs/factor-optimization.md) |
| 股票池初始化 | `src/core/stock_pool.py` | 股票池构建、缓存与增量更新 | — |
| 质量分级 | `src/core/stock_quality_classifier.py` | 股票质量分层（优质/标准/边缘/排除） | — |
| 回测引擎 | `src/core/backtest_engine.py` | 单次回测评估 | — |
| 交易日历 | `src/core/trading_calendar.py` | 交易日判断 | — |

### 3.2 数据源层

| 模块 | 文件 | 职责 |
|------|------|------|
| 数据源工厂 | `data_provider/factory.py` | 多数据源适配与 fallback 调度 |
| AkShare | `data_provider/akshare_fetcher.py` | A 股/港股数据（前复权） |
| efinance | `data_provider/efinance_fetcher.py` | A 股/ETF 数据（前复权） |
| YFinance | `data_provider/yfinance_fetcher.py` | 美股数据（auto_adjust） |
| Tushare | `data_provider/tushare_fetcher.py` | A 股数据（需 token） |
| Baostock | `data_provider/baostock_fetcher.py` | A 股数据（支持复权模式选择） |
| Pytdx | `data_provider/pytdx_fetcher.py` | 通达信实时行情 |
| Longbridge | `data_provider/longbridge_fetcher.py` | 港股/美股数据 |
| TickFlow | `data_provider/tickflow_fetcher.py` | 实时行情 |
| 基本面适配 | `data_provider/fundamental_adapter.py` | 基本面数据统一接口 |

> ⚠️ 复权方式：当前所有数据源默认使用前复权（qfq/fqt=1），回测场景存在未来函数风险。详见 [未来函数防范规范](docs/lookahead-bias-prevention.md)。

### 3.3 服务层

| 模块 | 文件 | 职责 |
|------|------|------|
| 分析服务 | `src/services/analysis_service.py` | 编排单股分析流程 |
| 选股服务 | `src/services/screener_service.py` | 选股任务调度与结果持久化 |
| 回测服务 | `src/services/backtest_service.py` | 回测评估与汇总 |
| 报告渲染 | `src/services/report_renderer.py` | Markdown 报告生成 |
| 历史服务 | `src/services/history_service.py` | 历史报告管理 |
| 持仓服务 | `src/services/portfolio_service.py` | 持仓组合管理 |
| 系统配置 | `src/services/system_config_service.py` | .env 配置管理 |
| 任务队列 | `src/services/task_queue.py` | 异步任务队列 |

### 3.4 数据访问层

| 模块 | 文件 | 职责 |
|------|------|------|
| 分析记录 | `src/repositories/analysis_repo.py` | 分析历史 CRUD |
| 回测记录 | `src/repositories/backtest_repo.py` | 回测结果 CRUD |
| 选股记录 | `src/repositories/screener_repo.py` | 选股结果 CRUD（含去重逻辑） |
| 行情数据 | `src/repositories/stock_repo.py` | 日线/实时行情存取 |
| 持仓记录 | `src/repositories/portfolio_repo.py` | 持仓 CRUD |

### 3.5 API 层

| 模块 | 文件 | 职责 |
|------|------|------|
| 路由注册 | `api/v1/router.py` | 所有 v1 端点注册 |
| 选股 API | `api/v1/endpoints/screener.py` | 选股触发与结果查询 |
| 分析 API | `api/v1/endpoints/analysis.py` | 单股分析触发与查询 |
| 回测 API | `api/v1/endpoints/backtest.py` | 回测触发与汇总 |
| 认证 | `api/middlewares/auth.py` | API Key 认证 |

### 3.6 Agent 系统

| 模块 | 文件 | 职责 |
|------|------|------|
| 编排器 | `src/agent/orchestrator.py` | Agent 流程编排 |
| 技术分析 Agent | `src/agent/agents/technical_agent.py` | 技术面分析 |
| 情报 Agent | `src/agent/agents/intel_agent.py` | 新闻/舆情 |
| 决策 Agent | `src/agent/agents/decision_agent.py` | 综合决策 |
| 风控 Agent | `src/agent/agents/risk_agent.py` | 风险评估 |
| 组合 Agent | `src/agent/agents/portfolio_agent.py` | 持仓建议 |
| 策略路由 | `src/agent/strategies/router.py` | 策略选择与分发 |

### 3.7 前端

| 模块 | 文件 | 职责 |
|------|------|------|
| 选股页 | `apps/dsa-web/src/pages/ScreenerPage.tsx` | 选股结果展示与股票池初始化 |
| 分析页 | `apps/dsa-web/src/pages/AnalysisPage.tsx` | 单股分析 |
| 回测页 | `apps/dsa-web/src/pages/BacktestPage.tsx` | 回测结果展示 |
| 持仓页 | `apps/dsa-web/src/pages/PortfolioPage.tsx` | 持仓管理 |

---

## 四、核心文档索引

### 4.1 协作规范

| 文档 | 位置 | 说明 |
|------|------|------|
| 协作规则 | `AGENTS.md` | AI 协作硬规则，唯一真源 |
| 贡献指南 | `docs/CONTRIBUTING.md` | 人类贡献者指南 |
| 更新日志 | `docs/CHANGELOG.md` | 版本变更记录 |

### 4.2 部署与配置

| 文档 | 位置 | 说明 |
|------|------|------|
| 完整指南 | `docs/full-guide.md` | 配置、部署、排障一站式 |
| 部署指南 | `docs/DEPLOY.md` | Docker / 云部署 |
| LLM 配置 | `docs/LLM_CONFIG_GUIDE.md` | AI 模型配置 |
| 桌面端打包 | `docs/desktop-package.md` | Electron 打包流程 |
| Docker 部署 | `docs/docker/zeabur-deployment.md` | Zeabur 部署 |

### 4.3 专题设计文档

| 文档 | 位置 | 说明 |
|------|------|------|
| 因子优化方案 | `docs/factor-optimization.md` | IC/PBO/DSR 四层验证体系 + 因子改造计划 |
| 未来函数防范 | `docs/lookahead-bias-prevention.md` | 前复权/入场价/分形确认等 look-ahead bias 防范规范 |
| API 规范 | `docs/architecture/api_spec.json` | API 接口规范 |
| 图片提取 Prompt | `docs/image-extract-prompt.md` | 图片导入提取 Prompt |

### 4.4 Bot 配置

| 文档 | 位置 | 说明 |
|------|------|------|
| 钉钉 Bot | `docs/bot/dingding-bot-config.md` | 钉钉机器人配置 |
| 飞书 Bot | `docs/bot/feishu-bot-config.md` | 飞书机器人配置 |
| Discord Bot | `docs/bot/discord-bot-config.md` | Discord 机器人配置 |
| Bot 命令 | `docs/bot-command.md` | Bot 指令说明 |

---

## 五、数据流全景

```
用户/定时触发
    │
    ▼
main.py / server.py
    │
    ├─ 单股分析 ──→ src/services/analysis_service.py
    │                  ├─ data_provider/factory.py → 行情/新闻数据
    │                  ├─ src/agent/orchestrator.py → AI 分析
    │                  └─ src/services/report_renderer.py → 报告
    │
    ├─ 选股扫描 ──→ src/services/screener_service.py
    │                  ├─ src/core/stock_pool.py → 股票池
    │                  ├─ src/core/stock_quality_classifier.py → 质量过滤
    │                  ├─ src/core/market_regime.py → 市场状态
    │                  ├─ src/core/strategy_signal_extractor.py → 策略信号
    │                  ├─ src/core/strategy_optimizer.py → 权重优化
    │                  └─ src/repositories/screener_repo.py → 结果持久化
    │
    └─ 回测验证 ──→ src/services/backtest_service.py
                       ├─ src/repositories/stock_repo.py → 前向行情
                       └─ src/core/backtest_engine.py → 评估计算
```

---

## 六、关键约束速查

| 约束 | 说明 | 详见 |
|------|------|------|
| 前复权未来函数 | 回测必须使用不复权数据，策略信号使用后复权 | [lookahead-bias-prevention.md](docs/lookahead-bias-prevention.md) |
| 因子冗余 | 21 策略中均线组/超卖组/形态组/突破组高度冗余 | [factor-optimization.md](docs/factor-optimization.md) |
| 入场价偏差 | 回测入场价应为次日开盘价，非当日收盘价 | [lookahead-bias-prevention.md](docs/lookahead-bias-prevention.md) |
| 数据源 fallback | 单一数据源失败不应拖垮整个分析流程 | `AGENTS.md` §7 |
| API 兼容 | 追加字段优先，保留旧字段或提供兼容层 | `AGENTS.md` §7 |
| 单例模式 | `StockPoolInitializer` 必须通过 `get_instance()` 获取 | `src/core/stock_pool.py` |
