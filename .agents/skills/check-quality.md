# Skill: Check Quality

代码质量综合检查，包括安全、性能、最佳实践。

## 执行条件
- Python 3.10+ (后端代码检查)
- Node.js 18+ (前端代码检查)

## Python 后端质量检查

### 1. Flake8 Lint
```bash
flake8 <files_or_dirs> --max-line-length=120 --extend-ignore=E203,W503
```

### 2. 安全检查（Bandit）
```bash
bandit -r src/ -f json
```

### 3. 代码复杂度
```bash
flake8 <file> --max-complexity=10
```

### 4. 未使用的导入
```bash
flake8 <file> --select=F401
```

## TypeScript 前端质量检查

### 1. ESLint
```bash
cd apps/dsa-web && npm run lint
```

### 2. 类型严格模式
```bash
cd apps/dsa-web && npx tsc -b --noEmit --strict
```

### 3. 未使用的变量/导入
```bash
cd apps/dsa-web && npx tsc -b --noEmit --noUnusedLocals
```

## 检查清单

### 安全
- [ ] 无硬编码密钥
- [ ] 无 SQL 注入风险
- [ ] 无未验证的用户输入

### 性能
- [ ] 无 N+1 查询
- [ ] 无大循环内数据库操作
- [ ] 前端无内存泄漏（useEffect cleanup）

### 最佳实践
- [ ] 类型注解完整
- [ ] 错误处理得当
- [ ] 日志记录适当

## 输出格式

质量报告：
```
## 质量检查报告

### 安全
- [x] 通过 Bandit 检查
- [x] 无高风险问题

### 性能
- [ ] 发现 2 处 N+1 查询
  - `src/repositories/screener_repo.py:45`
  - `src/services/analysis_service.py:78`

### 最佳实践
- [x] 类型检查通过
- [ ] 发现 1 处未使用导入
```

## 集成到 Agent 工作流

Reviewer Agent 必须执行此技能包中的检查项。
