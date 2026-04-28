# 闸门评估：Alpha超额收益系统

## 判定
**结论**：✅ 通过

无阻塞项。开发可开工。

## 8 维度审查

### 1. 需求完整性
✅ 通过
- 9 个 FR 均有给定/当/则验收标准
- 4 个 NFR 有量化指标和验证方式
- 5 个消歧义项全部已确认
- 边界场景已覆盖：停牌、新股、样本不足、向后兼容

### 2. 方案可行性
✅ 通过
- FactorModel 向后兼容方案明确：`load_strategy` 检查 `factors` 段是否存在
- AlphaScorer 快速打分方案可行：YAML 条件 → Python 判断函数，5 个策略各 20-40 行
- PortfolioSimulator 可依赖现有 `backtest_engine.py` 的 sharpe/max_drawdown 计算
- Benchmark 数据已有 tushare `index_daily` 接口（见 `tushare_fetcher.py` L822）

### 3. 接口一致性
✅ 通过
- AlphaPrediction 字段命名与现有 ScreenerCandidate 风格一致
- AlphaMetrics 字段与 BacktestSummary 已有 sharpe_ratio、max_drawdown_pct 对齐
- CLI 入口 `--alpha-debug` 遵循现有 `--debug` 命名风格

### 4. 文件变更完整性 — 关键检查
✅ 通过 — 已验证所有方案提到的依赖文件真实存在。

| 文件路径 | 是否存在 | 方案是否提及 | 备注 |
|----------|---------|-------------|------|
| `src/core/backtest_engine.py` | ✅ | ✅ | 可复用 compute_summary, EvaluationConfig |
| `src/core/screener_engine.py` | ✅ | ✅ | 可复用进度推送机制 |
| `src/core/stock_pool.py` | ✅ | ✅ | 可复用 get_pool_codes() |
| `data_provider/tushare_fetcher.py` | ✅ | ✅ | 已有 index_daily (L822) 和 沪深300 代码 (L804) |
| `strategies/bottom_volume.yaml` | ✅ | ✅ | 待参数化改造 |
| `strategies/bull_trend.yaml` | ✅ | ✅ | 待参数化改造 |
| `strategies/emotion_cycle.yaml` | ✅ | ✅ | 待参数化改造 |
| `strategies/momentum_reversal.yaml` | ✅ | ✅ | 待参数化改造 |
| `strategies/ma_golden_cross.yaml` | ✅ | ✅ | 待参数化改造 |
| `src/core/screener_progress.py` | ✅ | ✅ | SSE 广播器可复用 |
| `src/core/stock_quality_classifier.py` | ✅ | ✅ | 行业/质量标签可复用 |

**反向搜索**：方案中提到的 `src/alpha/` 目录不存在（预期，Phase1 创建），`data_provider/benchmark_fetcher.py` 不存在（预期，Phase1 创建）。无不合理的依赖引用。

### 5. 兼容性检查
✅ 通过
- `src/alpha/` 为新模块，不修改 `src/core/` 现有文件
- 策略 YAML 改造为**追加** `factors` 段，非替换原有字段 → 向后兼容
- 方案明确 `load_strategy` 兼容无 factors 段的旧 YAML
- main.py 仅追加 `--alpha-debug` 新参数，不改变现有 CLI 行为
- 无数据库 Schema 变更（Phase1），不影响现有回测数据

### 6. 安全审计
✅ 通过
- 无需新增 API 端点（Phase 1 纯 CLI 模式）
- 无新增用户输入到文件路径的拼接
- 无新增数据库操作
- 无新增网络请求（复用 data_provider）

### 7. 性能影响评估
✅ 通过 — 潜在性能问题已识别并有缓解措施

- 全截面打分（2961 × 5 策略）：方案承诺 < 5 秒/日，使用向量化计算可行
- 组合模拟（~730 日）：每日仅更新净值和执行调仓日交易，计算量线性
- 不引入 N+1 查询（Phase1 无数据库操作）
- 无循环内网络请求

**关注点**：`AlphaScorer.score_cross_section` 中"5 策略 × 2961 股"可能导致 14805 次策略条件判断。建议开发者使用 pandas 向量化操作而非逐股循环，并在 `04_DEVELOPMENT.md` 中记录实际性能数据。

### 8. 开发阶段高概率疑问点

| 疑问点 | 解答（开发前须知） |
|--------|-------------------|
| 快速打分中 YAML 条件如何翻译为 Python？ | 用 `eval()` 不安全。用字典映射 `{condition_key: lambda df: bool}`。每种条件类型一个处理函数 |
| 复权数据是否一致？ | data_provider 输出已前复权，直接使用。simulator 中用 close 价执行交易 |
| Benchmark 某日无数据？ | 前值填充 + `logger.warning` 记录缺失日期 |
| 策略因子修改后如何保证渲染正确？ | FactorModel 单元测试：10 组因子值 × 5 个策略 → 渲染结果含预期值 |
| 交易成本是否现实？ | 使用 EvaluationConfig 已有的 `commission_rate=0.0003, slippage_pct=0.001` |

## 阻塞项

无。

## 条件项

| 编号 | 条件 | 确认人 |
|------|------|--------|
| CND-01 | 开发者确认 `pandas` 版本 ≥ 1.3（向量化操作需要） | Developer |
| CND-02 | 5 个策略 YAML 参数化改造后需手动 review：因子范围是否合理 | Developer + User |

## 文件验证记录

| 文件路径 | 是否存在 | 方案是否提及 | 备注 |
|----------|---------|-------------|------|
| `src/core/backtest_engine.py` | ✅ | ✅ | |
| `data_provider/tushare_fetcher.py` | ✅ | ✅ | index_daily 接口已存在 |
| `strategies/bottom_volume.yaml` | ✅ | ✅ | |
| `strategies/bull_trend.yaml` | ✅ | ✅ | |
| `strategies/emotion_cycle.yaml` | ✅ | ✅ | |
| `strategies/momentum_reversal.yaml` | ✅ | ✅ | |
| `strategies/ma_golden_cross.yaml` | ✅ | ✅ | |
| `main.py` | ✅ | ✅ | |
