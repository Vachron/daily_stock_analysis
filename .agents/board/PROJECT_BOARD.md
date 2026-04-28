# 项目任务看板

> Harness Engineering — 跨会话 AI 记忆系统。  
> PM Orchestrator 在新会话启动时，先读此看板重建项目全貌。

## 使用说明

- PM 在新任务开始前搜索是否有历史相关任务
- Reporter 在任务完成后更新此看板
- 每个任务完成后追加一条记录，不删除历史

---

## 活跃任务

| 任务ID | 任务名称 | 当前阶段 | 当前 Agent | 文档路径 | 开始日期 |
|--------|---------|---------|-----------|---------|---------|
| - | - | - | - | - | - |

## 已完成任务

| 任务ID | 任务名称 | 完成日期 | 关键发现 | 文档路径 |
|--------|---------|---------|---------|---------|
| - | - | - | - | - |

---

## 项目架构快照

> 每次重大架构变更后更新此区域

### 当前架构关键决策

1. 后端：FastAPI (Python 3.10+)，目录结构 `src/`, `api/`, `data_provider/`
2. 前端：React + TypeScript + Vite，目录 `apps/dsa-web/`
3. 数据库：SQLite (通过 SQLAlchemy ORM)
4. 数据源优先级：Tushare > Eastmoney > Baostock > Tencent > Sina
5. AI 模型：通过 LLM 配置化接入
6. Harness 系统：7 Agent 流水线，Rules/Skills/Scripts 三层分离

### 关键模块依赖

```
前端 (ScreenerPage)
  ↓ HTTP
API (/api/v1/screener/*)
  ↓
ScreenerService → ScreenerEngine → StockPool
  ↓                                 ↓
ScreenerRepo ← SQLite          MarketData (多源 fallback)
```

---

## 历史任务知识沉淀

> 以下记录跨任务重复出现的模式、踩过的坑和技术约束

### 数据源相关
- Tushare 需要 token，需设置环境变量 `TUSHARE_TOKEN`
- Eastmoney push2 接口有反爬，需多源 fallback
- 代理冲突：所有 fetcher 需清除 `HTTP_PROXY/HTTPS_PROXY` 环境变量
- 市场数据缓存格式：CSV (`src/cache/market_quotes.csv`)，7 天过期

### 选股引擎相关
- 股票池初始化用全市场快照（快），选股需逐只获取历史数据（慢）
- 选股速度优化方案：ThreadPoolExecutor 并发获取历史数据
- 科创板高成长股：PE/PB 可能为负，使用 PS、PEG 等替代指标
- 质量分类：quality_speculative 标签用于高成长/亏损股

### 前端相关
- SSE 流用于实时进度更新
- 进度跟踪：ScreenerProgressBroadcaster 单例 + 线程安全
- 观察池去重：使用 SQL 窗口函数，不信任应用层去重
- 前端构建命令：`npx tsc -b --noEmit` 不等于 `npm run build`

### Git 工作流
- main 分支保护，commit message 英文
- 自动 tag 需 commit title 含 `#patch`/`#minor`/`#major`
