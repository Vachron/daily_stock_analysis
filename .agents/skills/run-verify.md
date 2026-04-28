# Skill: Run Verify

执行自动化验证脚本。封装了机器可检测的质量检查。

## 执行条件
- Python 3.10+
- rg (ripgrep) 已安装

## 快速执行

```bash
python scripts/verify_all.py
```

## 阶段选择

```bash
# 开发完成后
python scripts/verify_all.py --stage development

# PR 提交前（完整检查）
python scripts/verify_all.py --stage prerelease

# 仅安全检查
python scripts/verify_all.py --check safety

# 保存当前结果为基线
python scripts/verify_all.py --stage prerelease --save-baseline
```

## 检查项说明

| 编号 | 类别 | 检查内容 | 方法 |
|------|------|---------|------|
| A.1 | 代码质量 | Python 语法检查 | py_compile |
| A.2 | 安全 | 硬编码密钥检测 | rg 正则 |
| A.3 | 代码质量 | 禁止模式（bare except, print, TODO） | rg 正则 |
| A.4 | 代码质量 | 类型注解完整性 | 建议 mypy |
| B.1 | 代码质量 | from xxx import * 检查 | rg 正则 |
| B.2 | 代码质量 | 网络超时检查 | rg 正则 |
| B.3 | 性能 | N+1 查询检查 | 人工审查 |
| C.1 | 安全 | SQL 注入检查 | rg 正则 |
| C.2 | 安全 | 环境变量 .env.example 同步 | 代码分析 |
| D.1 | 构建 | 前端类型检查和构建 | tsc + vite |

## 验收标准

- development 阶段：A.1, A.3, B.1 必须 PASS
- prerelease 阶段：所有检查项不能有 FAIL
- 基线对比：不能有从 PASS 退化为 FAIL 的检查项

## 集成到 Agent 工作流

- Developer Agent 每完成一轮代码修改后执行 `--stage development`
- Code Reviewer 在评审前确认 `--stage development` 已通过
- QA Tester 在测试前执行 `--stage prerelease --save-baseline`
