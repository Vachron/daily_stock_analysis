# Skill: CI Gate

运行完整的 CI 门禁检查。

## 执行条件
- Python 3.10+ (后端 gate)
- Node.js 18+ (前端 gate)
- 已在仓库根目录

## 后端 Gate（Backend Gate）

### 完整检查
```bash
./scripts/ci_gate.sh
```

### 包含检查项
1. `flake8` 代码风格检查
2. `python -m py_compile` 语法检查
3. `python -m pytest -m "not network"` 非网络测试

### 检查失败处理
- 查看输出中的 `ERROR` 或 `FAILED`
- 修复对应文件后重新运行
- 如需跳过 flake8 检查，理由必须写入 commit message

## 前端 Gate（Web Gate）

仅当 `apps/dsa-web/` 下有改动时触发。

```bash
cd apps/dsa-web && npm ci && npm run lint && npm run build
```

## AI Governance Check

当 `.claude/` 或 AI 协作资产有改动时：

```bash
python scripts/check_ai_assets.py
```

## Docker Build

当 `docker/` 或 `Dockerfile` 有改动时：

```bash
docker build -t dsa-test .
```

## 验收标准

| 检查项 | 退出码 | 说明 |
|--------|--------|------|
| flake8 | 0 | 无 lint 错误 |
| py_compile | 0 | 无语法错误 |
| pytest | 0 或 5 | 0=全部通过，5=无测试文件 |
| npm ci | 0 | 依赖安装成功 |
| npm run lint | 0 | 无 lint 错误 |
| npm run build | 0 | 构建成功 |

## 本地模拟 CI

在提交前，建议本地运行最接近 CI 的检查：

```bash
# 后端
./scripts/ci_gate.sh

# 前端
cd apps/dsa-web && npm ci && npm run lint && npm run build
```

## 集成到 Agent 工作流

- Coder Agent 每次 commit 前必须运行后端 gate
- 前端改动必须运行前端 gate
- PR 创建前必须确认所有 gate 通过
