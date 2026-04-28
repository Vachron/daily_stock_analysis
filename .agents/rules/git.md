# Git 规则

定义 Git 工作流的硬性约束。

## Commit 规范

### 格式
```
<type>: <简短描述>

[可选的正文]

[可选的脚注]
```

### Type 类型
| Type | 含义 | 示例 |
|------|------|------|
| feat | 新功能 | `feat: add stock pool initialization progress UI` |
| fix | Bug 修复 | `fix: resolve watchlist duplicate entries` |
| refactor | 重构（非功能变更） | `refactor: extract market data fetcher base class` |
| docs | 文档 | `docs: update API schema for screener` |
| test | 测试 | `test: add unit test for stock classifier` |
| chore | 维护任务 | `chore: update dependencies` |
| perf | 性能优化 | `perf: parallelize history data fetching` |

### 规则
- 每条 commit 描述一个独立的逻辑变更
- 简短描述不超过 72 字符
- Commit message 使用英文
- 正文解释 **WHY**，不解释 WHAT（代码已说明）
- 脚注注明 Breaking Changes 和 Issue 引用

## 分支规范

### 分支命名
```
<type>/<issue-id>-<简短描述>
```

示例：
- `feat/123-add-progress-ui`
- `fix/456-watchlist-dedup`
- `refactor/789-streamline-data-fetching`

### 规则
- 禁止在 `main` 分支直接 commit
- PR 必须经过 review 才能合入
- 分支命名使用 kebab-case

## PR 规范

### 标题
与 commit message 格式一致

### 描述模板
```markdown
## 改了什么

## 为什么这么改

## 验证情况
- [x] 后端构建验证
- [x] 前端构建验证
- [ ] 网络/集成测试（未覆盖，原因：xxx）

## 未验证项
- [ ] 原因：xxx

## 风险点
- 影响面：xxx
- 回滚方式：xxx
```

### 规则
- PR 描述必须包含"改了什么"和"为什么这么改"
- 缺少验证证据的 PR 不得合入
- 阻塞型 CI 未通过不得合入

## 合并策略

### Squash Merge
- 功能分支合并到 main 使用 squash merge
- 保持 main 分支历史整洁

### 规则
- 合入前必须 rebase 到最新 main
- 冲突必须由 PR 作者解决
- 合入后删除源分支

## 禁止事项

- 禁止 force push 到已发布的分支
- 禁止在 PR 中 commit 敏感信息（如密钥、Token）
- 禁止合并 CI 未通过的 PR
- 禁止绕过审查直接合入
