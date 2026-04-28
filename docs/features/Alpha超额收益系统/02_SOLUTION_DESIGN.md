# 方案设计：Alpha超额收益系统

## 1. 方案概述

新增 `src/alpha/` 模块，在现有选股/回测基础上构建 Alpha 超额收益框架。核心理念：因子预测超额收益（alpha）而非绝对收益，对标沪深300 Benchmark，与私募量化框架一致。

分 6 个 Phase 递进实现，Phase1 为最小闭环（因子参数化 + 截面打分 + 组合模拟 + 超额评估），后续 Phase 叠加风险中性化、IC 监控、Agent 自动优化。

## 2. 模块变更清单

### Phase 1 新增文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/alpha/__init__.py` | 新增 | 模块入口 |
| `src/alpha/factor_model.py` | 新增 | 因子定义解析、参数化渲染 |
| `src/alpha/alpha_scorer.py` | 新增 | 截面 alpha 预测（复用 data_provider） |
| `src/alpha/portfolio_simulator.py` | 新增 | 组合级别逐日模拟 |
| `src/alpha/alpha_evaluator.py` | 新增 | 超额收益评估 + IC 计算 |
| `src/alpha/cli.py` | 新增 | CLI 入口 |

### Phase 1 修改文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `strategies/bottom_volume.yaml` | 修改 | 新增 `factors` 段，5 个参数 |
| `strategies/bull_trend.yaml` | 修改 | 新增 `factors` 段，4 个参数 |
| `strategies/emotion_cycle.yaml` | 修改 | 新增 `factors` 段，5 个参数 |
| `strategies/momentum_reversal.yaml` | 修改 | 新增 `factors` 段，4 个参数 |
| `strategies/ma_golden_cross.yaml` | 修改 | 新增 `factors` 段，5 个参数 |
| `main.py` | 修改 | 新增 `--alpha-debug` 参数入口 |

### Phase 2-6 新增文件（不在 Phase 1 范围内）

| 文件 | Phase | 说明 |
|------|-------|------|
| `src/alpha/risk_neutralizer.py` | Phase 2 | 行业/市值中性化 |
| `src/alpha/factor_debug_env.py` | Phase 3 | RL 风格调试环境 |
| `src/agent/agents/alpha_debug_agent.py` | Phase 3 | Alpha 调试 Agent |
| `src/agent/tools/alpha_tools.py` | Phase 3 | 环境交互工具集 |
| `strategies/factors/*.yaml` | Phase 4 | 可复用因子库 |
| `data_provider/benchmark_fetcher.py` | Phase 1 | Benchmark 数据接口 |

## 3. API / 接口定义

### 3.1 FactorModel — 因子参数化

```python
# 文件: src/alpha/factor_model.py
# 变更类型: 新增

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import yaml

@dataclass
class FactorDefinition:
    id: str
    display_name: str
    type: str  # "float" | "int" | "bool"
    default: float
    range: Tuple[float, float]
    step: float

@dataclass
class StrategyTemplate:
    name: str
    display_name: str
    description: str
    category: str
    factors: List[FactorDefinition]
    instructions_template: str
    weight: float = 1.0

class FactorModel:
    @classmethod
    def load_strategy(cls, path: str) -> StrategyTemplate:
        """加载策略 YAML，兼容旧版（无 factors 段）"""

    @classmethod
    def render_instructions(cls, template: StrategyTemplate, 
                            factor_values: Dict[str, float]) -> str:
        """将 {{factor_id}} 占位符替换为实际值"""

    @classmethod
    def get_factor_space(cls, template: StrategyTemplate) -> Dict[str, Dict[str, Any]]:
        """返回因子搜索空间：{factor_id: {type, range, step}}"""
```

### 3.2 AlphaScorer — 截面 Alpha 预测

```python
# 文件: src/alpha/alpha_scorer.py
# 变更类型: 新增

@dataclass
class AlphaPrediction:
    code: str
    name: str
    alpha_score: float          # 截面标准化后的超额预测
    factor_scores: Dict[str, float]  # 各因子得分

class AlphaScorer:
    def __init__(self, pool_codes: List[str]):
        """初始化，加载候选池代码列表"""

    def score_cross_section(
        self,
        date: date,
        strategies: List[StrategyTemplate],
        factor_values: Dict[str, Dict[str, float]],  # {strategy_name: {factor_id: value}}
    ) -> List[AlphaPrediction]:
        """
        对给定日期的全截面计算 alpha 预测。
        
        算法：
        1. 对每只股票，每个策略渲染 instructions
        2. 从 daily_history 提取因子所需数据（OHLCV）
        3. 按 strategy instructions 中的条件判断打分
        4. 各策略得分加权求和 → 原始 alpha
        5. 截面 Z-score 标准化 → 最终 alpha_score
        
        返回：按 alpha_score 降序排列的 AlphaPrediction 列表
        """
```

**快速打分逻辑（不调 LLM）**：

每个策略渲染后的 instructions 中的条件被翻译为 Python 判断函数。例如：
```yaml
# bottom_volume.yaml 中的条件：
# "跌幅 > 15%"  →  calculated = True if (20d_high - recent_low) / 20d_high > decline_threshold
# "量比 > 3.0"  →  calculated = True if volume / 5d_avg_volume > volume_ratio_threshold
# 满足条件 → strategy_score += score_base
```

### 3.3 Benchmark 数据接口

```python
# 文件: data_provider/benchmark_fetcher.py
# 变更类型: 新增

def get_benchmark_history(
    code: str = "000300",
    start_date: date = None,
    end_date: date = None,
) -> pd.DataFrame:
    """
    获取指数日线数据。
    
    支持:
    - "000300": 沪深300
    - "000905": 中证500
    - "000852": 中证1000
    
    返回 columns: [date, open, high, low, close, volume]
    
    实现：调用现有 tushare_fetcher 的 index_daily 接口，
    失败时 fallback 到 akshare 的 stock_zh_index_daily
    """
```

### 3.4 PortfolioSimulator — 组合模拟

```python
# 文件: src/alpha/portfolio_simulator.py
# 变更类型: 新增

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import date

@dataclass
class PortfolioConfig:
    initial_capital: float = 1_000_000.0
    max_positions: int = 20
    max_single_weight: float = 0.10
    commission_rate: float = 0.0003
    slippage_pct: float = 0.001
    rebalance_freq_days: int = 5

@dataclass
class PortfolioSnapshot:
    date: date
    nav: float
    positions: Dict[str, float]  # code → weight
    cash: float

class PortfolioSimulator:
    def __init__(self, config: PortfolioConfig):
        """初始化"""

    def simulate(
        self,
        alphas_by_date: Dict[date, List[AlphaPrediction]],
        price_data: Dict[str, pd.DataFrame],  # code → daily OHLCV
        benchmark_nav: Optional[pd.Series] = None,
    ) -> Tuple[
        pd.DataFrame,       # 每日净值（含超额）
        List[PortfolioSnapshot],  # 每日持仓快照
        List[Dict],          # 交易记录
    ]:
        """
        逐日模拟：
        for each trading day:
            if rebalance_day:
                scores = alphas_by_date.get(day)
                target_weights = build_portfolio(scores, config)
                orders = compute_orders(current, target)
            execute_orders(orders, price_data)
            update_nav(day_price_data)
        """
```

### 3.5 AlphaEvaluator — 超额评估

```python
# 文件: src/alpha/alpha_evaluator.py
# 变更类型: 新增

@dataclass
class AlphaMetrics:
    total_return_pct: float
    annualized_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    excess_return_pct: float          # 超额收益
    information_ratio: float           # 信息比率
    tracking_error_pct: float          # 跟踪误差
    max_excess_drawdown_pct: float     # 超额最大回撤
    win_rate_pct: float
    turnover_rate_pct: float

@dataclass
class FactorICReport:
    factor_id: str
    rank_ic: float                     # Rank IC
    ic_ir: float                       # IC Information Ratio
    ic_series: List[float]             # 逐期 IC 序列
    is_aged: bool                      # 是否老化（IC连续<0.02超过N期）

class AlphaEvaluator:
    @classmethod
    def evaluate(
        cls,
        portfolio_nav: pd.Series,
        benchmark_nav: pd.Series,
        risk_free_rate: float = 0.02,
    ) -> AlphaMetrics:
        """计算完整超额收益指标"""

    @classmethod
    def compute_factor_ic(
        cls,
        factor_values: pd.Series,
        forward_returns: pd.Series,
    ) -> FactorICReport:
        """计算单个因子的 Rank IC 及 IC IR"""
```

### 3.6 CLI 入口

```python
# 文件: src/alpha/cli.py
# 变更类型: 新增

# 在 main.py 中新增入口:
# python main.py --alpha-debug --from 2023-01-01 --to 2025-12-31
# python main.py --alpha-debug --auto --iterations 50
```

## 4. 数据流

```
                    ┌──────────────────────────┐
                    │  data_provider/           │
                    │  get_daily_history()      │
                    │  get_benchmark_history()  │  ← NEW
                    └──────────┬───────────────┘
                               │
                    ┌──────────▼───────────────┐
                    │  FactorModel              │
                    │  load 5 strategies YAML   │
                    │  render {{factor_id}}     │
                    └──────────┬───────────────┘
                               │
                    ┌──────────▼───────────────┐
                    │  AlphaScorer              │
                    │  for each stock × strategy│
                    │  compute condition scores │
                    │  weighted → alpha Z-score │
                    └──────────┬───────────────┘
                               │
                    ┌──────────▼───────────────┐
                    │  PortfolioSimulator      │
                    │  alpha → target weights  │
                    │  execute orders daily    │
                    │  track nav + positions   │
                    └──────────┬───────────────┘
                               │
                    ┌──────────▼───────────────┐
                    │  AlphaEvaluator           │
                    │  nav vs benchmark        │
                    │  → AlphaMetrics          │
                    │  → FactorICReport        │
                    └──────────────────────────┘
```

## 5. 数据库变更

Phase 1 不新增数据库表。后续 Phase 可能新增：

| 表名 | Phase | 用途 |
|------|-------|------|
| `alpha_runs` | Phase 3 | 记录每次 Alpha 调试运行 |
| `alpha_configs` | Phase 3 | 最优策略配置持久化 |
| `factor_ic_history` | Phase 4 | 因子 IC 历史监控 |

Phase 1 使用 JSON 文件持久化模拟结果。

## 6. 配置变更

新增配置项（`.env.example` 同步）：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ALPHA_BENCHMARK_CODE` | `000300` | Benchmark 股票代码 |
| `ALPHA_DEFAULT_POOL_SIZE` | `500` | 候选池大小 |
| `ALPHA_REBALANCE_DAYS` | `5` | 调仓频率（交易日） |

## 7. 风险评估

| 风险 | 等级 | 缓解措施 | 验收要求 |
|------|------|---------|---------|
| 新模块破坏现有选股流程 | 高 | `src/alpha/` 独立于 `src/core/`，不修改 screener_engine.py | CI 中现有选股流程回归测试通过 |
| 快速打分精度不足 | 中 | 快速打分为主力，Phase5 引入 LLM 抽样校验 | 5 只股票 LLM vs 快速打分偏差 < 20% |
| Benchmark 数据源不稳定 | 中 | tushare → akshare fallback，前值填充 | 压力测试：连续 5 天 benchmark 缺失不崩溃 |
| 策略 YAML 改造向后兼容 | 中 | FactorModel.load_strategy 兼容无 factors 段 | 22 个现有策略加载成功率 100% |
| 性能瓶颈 | 低 | 向量化计算、增量更新 alpha | 2961 股 × 5 策略 < 5 秒 |

## 8. 开发阶段高概率疑问点

1. **快速打分怎么实现？**
   — 不调 LLM。把 YAML 中的条件翻译为 Python 函数。5 个策略各自的判断逻辑约 20-40 行/个，总计约 150 行。

2. **复权数据怎么处理？**
   — 使用 data_provider 已有的前复权数据。simulator 中买卖价格用当日 close（前复权）。

3. **停牌股怎么处理？**
   — AlphaScorer 跳过无当日行情的股票。Simulator 中已有持仓遇到停牌：不强制卖出，保留仓位，价格用最后交易日价格。

4. **调仓日与 Calender 对齐？**
   — 使用 A 股交易日历（akshare.tool_trade_date_hist_sina）。非调仓日只更新净值，不产生交易。

5. **Reward 函数怎么设计？**
   — 当前 Phase 1 不涉及 Agent 自动优化。Phase 5 的 reward = α×IR_improvement + β×excess_return_improvement - γ×turnover_penalty。

## 9. 对需求分析的反馈

需求文档覆盖完整，无遗漏。建议 S3 闸门评估重点验证：
- FR-02 截面标准化是否真的 mean≈0 std≈1
- FR-05 单次模拟耗时是否 < 30 秒
- 旧版策略 YAML 加载是否 100% 通过
