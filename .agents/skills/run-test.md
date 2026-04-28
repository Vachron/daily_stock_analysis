# Skill: Run Tests

运行项目测试套件。

## 执行条件
- Python 3.10+ (后端测试)
- Node.js 18+ (前端测试)

## Python 后端测试

### 1. 非网络测试（默认）
```bash
python -m pytest -m "not network" -v
```

### 2. 完整测试
```bash
python -m pytest -v
```

### 3. 指定模块
```bash
python -m pytest tests/test_screener_repo.py -v
```

### 4. 带覆盖率
```bash
python -m pytest --cov=src --cov-report=html
```

## TypeScript 前端测试

```bash
cd apps/dsa-web && npm test
```

## 验收标准
- 所有测试通过（PASSED）
- 无新增失败的测试
- 覆盖率无大幅下降（> 5%）

## 标记说明

| 标记 | 说明 | 何时运行 |
|------|------|---------|
| `network` | 需要外网访问 | CI network-smoke |
| `unit` | 单元测试 | 本地 + CI |
| `integration` | 集成测试 | CI |

## 常见问题

### "ModuleNotFoundError"
→ 确保依赖已安装：`pip install -r requirements.txt`

### "Connection refused"
→ 这是 `network` 标记的测试，网络不可用时跳过是正常行为

### 测试超时
→ 检查是否有网络请求未设置 timeout

## 集成到 Agent 工作流

- Coder Agent 修复 bug 时，必须先写测试复现 bug，再修复
- PR 合入前必须运行完整测试套件
