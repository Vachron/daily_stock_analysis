# Skill: Frontend Build

前端 TypeScript/React 代码构建验证。

## 执行条件
- Node.js 18+
- 已安装依赖：`cd apps/dsa-web && npm ci`

## 执行命令

### 1. 类型检查
```bash
cd apps/dsa-web && npx tsc -b --noEmit
```

### 2. Lint 检查
```bash
cd apps/dsa-web && npm run lint
```

### 3. 生产构建
```bash
cd apps/dsa-web && npm run build
```

## 验收标准
- 所有命令退出码 0 表示通过
- `tsc` 无类型错误
- `lint` 无新增 lint 错误
- `build` 产物生成到 `apps/dsa-web/dist/`

## 快速验证（改动后必跑）
```bash
cd apps/dsa-web && npx tsc -b --noEmit && npm run lint
```

## 完整验证（PR 前必跑）
```bash
cd apps/dsa-web && npm ci && npm run lint && npm run build
```

## 常见错误处理

### "Cannot find module"
→ 运行 `npm ci` 重新安装依赖

### "Type error: XXX is not assignable to YYY"
→ 修复类型定义，不要使用 `any`

### "ESLint error"
→ 根据提示修复，或在 `.eslintrc.js` 中有充足理由时添加 `// eslint-disable-next-line`

## 集成到 Agent 工作流

Coder Agent 在改动前端代码后必须执行快速验证。
