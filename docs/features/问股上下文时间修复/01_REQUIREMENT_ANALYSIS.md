# 需求分析：问股多轮对话上下文时间感知修复

## 1. 需求概述

修复问股多轮对话中跨交易日时间错乱问题。根因：System Prompt无日期+历史消息无时间戳+AgentMemory默认关闭+缺少时间锚定。

## 2. 根因分析

| # | 根因 | 位置 |
|---|------|------|
| 1 | System Prompt没有日期 | executor.py CHAT_SYSTEM_PROMPT |
| 2 | 历史消息不含时间戳 | storage.py get_conversation_history() |
| 3 | AgentMemory默认关闭 | memory.py AGENT_MEMORY_ENABLED=false |
| 4 | Orchestrator不注入时间 | orchestrator.py chat() |

## 3. 功能需求

- FR-01: 每次对话注入当前日期/星期/交易日到System Prompt
- FR-02: 历史消息携带时间标签 [MM-DD HH:MM]
- FR-03: AgentMemory始终可用（不受memory.enabled限制）
- FR-04: 跨会话Session时间感知

## 4. 验收标准

- LLM能正确回答"今天周几"、"上次分析是什么时候"
- 跨交易日对话不会出现日期幻觉
