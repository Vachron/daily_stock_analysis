# 需求分析：Alpha超额收益系统

## 1. 需求概述

构建 Alpha 因子迭代系统，使 Agent 能像调试代码一样调试因子——"改因子权重 → 算截面 IC → 跑组合超额回测 → 看信息比率 → 再改"，循环直到因子组合 IR > 0.8 或超额年化 > 15%。

核心转变：从「绝对收益打分」升级为「预测相对 benchmark 的超额收益（alpha）」——即私募量化的标准框架。

## 2. 消歧义记录

| 歧义点 | 解读 A | 解读 B | 决策 | 决策时间 |
|--------|--------|--------|------|---------|
| AMB-01 Benchmark选择 | 单一沪深300 | 多Benchmark（300+500+1000） | **A** — Phase1-3用沪深300，Phase5扩展多benchmark | 2026-04-28 |
| AMB-02 因子改造范围 | 全部22策略参数化 | 先选5个核心策略试水 | **B** — bottom_volume/bull_trend/emotion_cycle/momentum_reversal/ma_golden_cross | 2026-04-28 |
| AMB-03 风险模型复杂度 | 简化版（行业+市值） | 完整Barra（含10类风格） | **A** — 行业+市值优先，后续扩展 | 2026-04-28 |
| AMB-04 回测区间 | 1年（2025全年） | 3年含熊市（2023-2025） | **B** — 含熊市，否则过拟合风险高 | 2026-04-28 |
| AMB-05 Agent优化策略 | 贝叶斯优化 | 强化学习（PPO） | **A** — 因子空间小，贝叶斯效率更高 | 2026-04-28 |

## 3. 功能需求 (FR)

### FR-01: 因子参数化
- **描述**：策略 YAML 支持 `factors` 段，包含 id/type/default/range/step 字段。`instructions` 中用 `{{factor_id}}` 占位符引用因子值。Agent 修改因子值即可改变策略行为，无需重写自然语言。
- **验收标准**：
  - Given: 一个含 `factors` 段的 YAML 文件
  - When: 修改某个因子值并渲染 instructions
  - Then: instructions 中的 `{{factor_id}}` 被替换为对应值，其余内容不变
- **边界场景**：因子值超出 range 时渲染报错而非静默；旧版无 factors 段的 YAML 仍可正常加载（向后兼容）
- **优先级**：P0

### FR-02: 截面 Alpha 预测
- **描述**：给定指定日期 + 因子组合，对全市场候选池输出标准化 alpha 预测值。alpha 含义：预测该股票在未来 N 日跑赢同行业同类股票的幅度（Z-score）
- **验收标准**：
  - Given: 某交易日 2961 只股票池 + 5 个参数化策略
  - When: AlphaScorer.score_cross_section(date, factors, pool_codes)
  - Then: 返回每只股票的 alpha_score（float，截面标准化），mean≈0，std≈1
- **边界场景**：停牌股（无当日数据）输出 alpha_score=None；新股（历史数据不足）使用可用数据窗口
- **优先级**：P0

### FR-03: 风险中性化
- **描述**：对原始 alpha 做行业中性化 + 市值中性化，消除系统性偏差
- **验收标准**：
  - Given: 截面 alpha 预测值列表
  - When: RiskNeutralizer.neutralize(alphas, industry_map, market_cap_map)
  - Then: 中性化后，同一行业内 alpha 均值为 0；alpha 与市值对数的相关系数 < 0.05
- **边界场景**：行业分类缺失的股票归入"其他"行业；市值缺失的股票不参与市值中性化
- **优先级**：P1（Phase2 实现，Phase1 可跳过）

### FR-04: 组合构建与调仓
- **描述**：基于截面 alpha 构造投资组合，支持 Top-N 和 alpha 加权两种模式。输出每日调仓指令。
- **验收标准**：
  - Given: 截面 alpha 列表 + 当前持仓
  - When: PortfolioBuilder.build(alphas, mode="alpha_weighted", top_n=20)
  - Then: 返回调仓指令列表（买入/卖出/持有），alpha 加权模式按 alpha 分配仓位
- **边界场景**：空持仓初始化时一次性建仓；单票权重超过 10% 时强制截断
- **优先级**：P0

### FR-05: 组合级别模拟
- **描述**：逐日执行调仓指令，生成组合净值曲线。支持交易成本模型。
- **验收标准**：
  - Given: 调仓指令序列 + 成本模型
  - When: PortfolioSimulator.simulate(orders, start_date, end_date)
  - Then: 输出每日组合净值、持仓列表、交易记录；单次模拟耗时 < 30 秒
- **边界场景**：遇到停牌股时延迟调仓；资金不足时按 alpha 优先级分批买入
- **优先级**：P0

### FR-06: 超额收益评估
- **描述**：计算组合相对于 benchmark（沪深300）的超额收益、信息比率、tracking error
- **验收标准**：
  - Given: 组合净值序列 + benchmark 净值序列
  - When: AlphaEvaluator.evaluate(portfolio_nav, benchmark_nav)
  - Then: 输出年化超额收益、信息比率（IR）、tracking error、超额最大回撤
- **边界场景**：回测区间不足 60 天时年化指标标注"样本不足"而非显示NaN
- **优先级**：P0

### FR-07: 因子 IC 监控
- **描述**：每日/每周计算每个因子的截面 Rank IC（因子暴露与未来超额收益的 Spearman 秩相关系数）
- **验收标准**：
  - Given: 因子值序列 + 未来 N 日超额收益序列
  - When: AlphaEvaluator.compute_ic(factor_values, forward_returns)
  - Then: 返回 Rank IC 值和 IC IR（IC 均值 / IC 标准差）
- **边界场景**：截面股票数 < 50 时 IC 标的"样本不足"
- **优先级**：P1（Phase4 实现）

### FR-08: Agent 交互工具
- **描述**：Agent 通过工具集与环境交互——修改因子、查看 IC、跑模拟、对比结果
- **验收标准**：
  - Given: Agent 工具集已注册
  - When: Agent 调用 modify_factor("bottom_volume", "volume_ratio_threshold", 4.0)
  - Then: 因子值被修改，策略重新渲染，Agent 收到确认
- **边界场景**：修改不存在的策略/因子时返回错误信息；同时修改多个因子时保证原子性
- **优先级**：P1（Phase5 实现）

### FR-09: 自动优化循环
- **描述**：Agent 自主迭代优化因子参数，基于贝叶斯优化搜索策略空间
- **验收标准**：
  - Given: 初始因子配置 + 回测区间
  - When: 启动 --auto --iterations 50
  - Then: 50 轮后组合信息比率有统计显著提升（IR 提升 > 0.1），最优配置持久化
- **边界场景**：连续 10 轮无改善时早停；最优配置保存到 `data/optimized_strategies/`
- **优先级**：P2（Phase6 实现）

## 4. 非功能需求 (NFR)

### NFR-01: 性能
- **描述**：全截面 alpha 计算耗时
- **量化指标**：2961 只股票 × 5 个策略，单次截面打分 < 5 秒
- **验证方式**：benchmark 测试

### NFR-02: 向后兼容
- **描述**：现有 22 个策略 YAML 无 factors 段仍可加载
- **量化指标**：旧版策略加载成功率 100%，现有选股流程不受影响
- **验证方式**：CI gate 中增加旧格式加载测试

### NFR-03: 数据一致性
- **描述**：同一策略配置在同一回测区间跑两次，结果完全一致（确定性）
- **量化指标**：两次模拟的超额净值序列差异 = 0
- **验证方式**：固定随机种子 + 回归测试

### NFR-04: 可追溯性
- **描述**：每次策略修改和模拟结果均可追溯
- **量化指标**：修改记录包含时间戳、修改人、修改前后的值
- **验证方式**：检查日志完整性

## 5. 风险预判

| 风险 | 影响 | 等级 | 缓解措施 |
|------|------|------|---------|
| 过拟合历史数据 | 策略在回测中表现好但实盘差 | 高 | 样本外验证、Walk-forward、限制因子自由度 |
| 全市场打分性能 | 4000 股 × 多策略计算量大 | 中 | 向量化计算（pandas/numpy）、缓存中间结果 |
| 数据质量问题 | 停牌/ST/新股导致模拟偏差 | 中 | 过滤非正常交易股票、复权处理 |
| 策略变异不可解释 | Agent 修改后策略逻辑混乱 | 中 | 限制单步修改幅度、保留变更历史 |
| Benchmark 数据不足 | 沪深300 某些日期无数据 | 低 | 前值填充 + 告警 |

## 6. 与本需求相关的历史任务

- 选股系统（screener_engine.py）：AlphaScorer 可复用其数据获取和进度推送机制
- 回测系统（backtest_engine.py）：组合模拟器内部调用 compute_summary
- 股票池（stock_pool.py）：候选池来源
- 质量分类（stock_quality_classifier.py）：风险中性化的行业/质量约束维度

## 7. 待用户确认项

全部消歧义项已确认。可进入 S2 方案设计阶段。
