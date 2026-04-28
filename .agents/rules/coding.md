# 编码规则

定义代码编写的硬性约束，Agent 必须遵守。

## Python 后端

### 导入规范
- 标准库 → 第三方库 → 本地包的顺序组织 import，每组之间空一行
- 禁止使用 `from xxx import *`
- 循环依赖是致命错误：必须重构解决，不能 `import at bottom of file`

### 类型注解
- 函数参数和返回值必须有类型注解（`-> None` 除外）
- 复杂泛型使用 `TYPE_CHECKING` 块避免循环导入

### 错误处理
- 捕获异常必须记录日志（`logger.error/exceptions`）并附加上下文
- 禁止 bare `except:`
- 网络请求类必须设置 timeout（默认 10s）

### 数据库
- 写操作使用事务
- 批量操作必须分批（每批 ≤ 1000 条）
- 禁止在循环内执行数据库写操作

### 配置与密钥
- 禁止硬编码密钥、账号、Token
- 环境变量读取使用 `os.getenv` 或 `pydantic-settings`
- 配置项必须写入 `.env.example`

## TypeScript / React 前端

### 导入
- 相对导入优先于包导入
- 组件文件使用 PascalCase，工具函数使用 camelCase

### 状态管理
- 组件内部 state 用于 UI 状态
- 全局状态使用 store（Zustand）
- 禁止在组件内直接操作 DOM

### 类型
- 禁止使用 `any`，必须使用具体类型
- API 响应必须有对应 TypeScript 接口
- 可选字段使用 `?: T` 而非 `| undefined`

### Hooks
- 自定义 Hook 必须以 `use` 开头
- useEffect 必须包含依赖数组
- 异步操作优先使用 `useQuery` / `useMutation`（TanStack Query）

## 通用

### 注释
- 不写无意义的注释（如 `// increment i`）
- 复杂逻辑必须用注释解释 WHY，不解释 WHAT
- Docstring 使用中文，描述意图而非实现

### 日志
- 关键路径必须有日志
- 日志级别：`DEBUG`（调试）、`INFO`（正常）、`WARNING`（异常可恢复）、`ERROR`（需要关注）
- 日志内容包含上下文字段

### 性能
- 禁止 N+1 查询
- 大数据量处理必须分批
- 前端列表渲染必须虚拟化（超过 50 项）
