# 自动化验证规则

定义 CI/CD 和本地必须通过的自动化检查项。

## Python 后端验证

### 1. 编译检查
```bash
python -m py_compile <changed_files>
```
- 所有 `.py` 文件必须通过语法检查
- 新增文件必须包含

### 2. Lint 检查
```bash
flake8 <changed_files> --max-line-length=120 --extend-ignore=E203,W503
```
- 无新增 lint 错误
- 关键规则错误必须修复（E9, F63, F7, F82）

### 3. 测试（可选网络）
```bash
python -m pytest -m "not network" -v
```
- 所有非网络依赖的测试必须通过

### 4. 类型检查（如有 mypy）
```bash
mypy <changed_files> --ignore-missing-imports
```

## TypeScript 前端验证

### 1. TypeScript 编译
```bash
npx tsc -b --noEmit
```
- 必须通过，无类型错误

### 2. ESLint
```bash
npm run lint
```
- 无新增 lint 错误

### 3. 构建
```bash
npm run build
```
- 必须成功构建，产物可用

## API 兼容性检查

### Schema 变更
- 新增字段必须向后兼容
- 删除字段必须确认无客户端依赖
- 枚举值变更必须评估影响
- 变更后运行 API 测试确保兼容

### 数据库迁移
- 新增列必须有默认值或 nullable
- 删除列必须先确认无引用
- 所有迁移必须可逆

## 验证矩阵

| 改动面 | 最低要求 | 推荐要求 |
|--------|---------|---------|
| Python 后端 | `py_compile` | `flake8` + `pytest` |
| TypeScript 前端 | `tsc --noEmit` | `tsc` + `lint` + `build` |
| API/Schema | 编译通过 | API 测试通过 |
| 数据库 | 迁移脚本可逆 | 迁移前后数据完整 |
| 配置 | .env.example 更新 | 配置验证测试 |

## 本地验证命令

### 快速验证（改动后必跑）
```bash
# Python
python -m py_compile src/**/*.py api/**/*.py

# Frontend
cd apps/dsa-web && npm run lint && npm run build
```

### 完整验证（PR 前必须跑）
```bash
# Backend gate
./scripts/ci_gate.sh

# Frontend gate
cd apps/dsa-web && npm ci && npm run lint && npm run build
```

## 未验证项处理

如果某些验证项因环境限制无法执行，必须在 PR 描述中明确：

```markdown
## 未验证项
- [ ] 网络集成测试 — 原因：无外网访问权限
- [ ] Docker 构建 — 原因：本地无 Docker daemon
```

## 禁止事项

- 禁止跳过阻塞型 CI 检查
- 禁止在 PR 中禁用 lint 规则（除非有明确理由）
- 禁止提交无法构建的代码
- 禁止移除已有的测试覆盖
