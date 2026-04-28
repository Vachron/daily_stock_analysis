# 模型选择策略

按照 Harness Engineering 成本优化原则：只有写代码的角色用顶级模型。

## 模型分配表

| Agent | 模型 | 理由 |
|-------|------|------|
| PM Orchestrator | 轻量 | 调度逻辑不需要写代码 |
| Requirement Analyst | 轻量 | 纯文本分析 |
| Solution Architect | 轻量 | 偏文档输出，不写实现 |
| Gate Reviewer | 轻量 | 审查模板化，固定格式 |
| **Developer** | **顶级** | **唯一需要写代码的角色** |
| Code Reviewer | 中级 | 需深度理解代码但不自己写 |
| QA Tester | 轻量 | 测试用例偏文档 |
| Reporter | 轻量 | 文档汇总 |

## 模型等级定义

| 等级 | Trae/Claude 等效 | 适用场景 | 选型原则 |
|------|-----------------|---------|---------|
| 轻量 | Haiku / Gemini Flash / 本地模型 | 文档处理、模板化输出、调度 | 够用就行，省 token |
| 中级 | Sonnet / GPT-4o | 深度理解代码但不需要写 | 能读懂，不要求写出最优解 |
| 顶级 | Opus / Sonnet high-thinking / GPT-4.5 | 需要产出最优代码 | 不省钱，要效率 |

## 成本意识

- 6/7 的 Agent 用轻量模型，只有 Developer 用顶级模型
- 每个任务中 6 个文档处理阶段的总 token 消耗 ≈ Developer 一个阶段的 60-80%
- 不要对所有 Agent 使用相同模型——那是浪费

## 实际映射到 Trae

在 Trae 中，可以通过以下方式控制：
1. 不同的会话使用不同的模型设置
2. PM 会话：普通模型 + 读取看板 + 读取规则
3. Developer 会话：顶级模型 + 读取方案 + 读取规则 + 运行脚本
4. Reviewer 会话：中级模型 + 读取全部文档 + 读取代码
