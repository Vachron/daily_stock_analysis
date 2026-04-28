# 工作流规则

**Always Apply** | 定义 Agent 必须遵守的流程纪律，保证不因上下文衰减而跳过关键步骤。

## 强制流程触发点

以下流程点 Agent 不得跳过，每次改动后自动执行：

### 代码改动后必跑（Developer Agent）

```bash
# 编译检查
python -m py_compile <changed_files>

# 前端（如有改动）
cd apps/dsa-web && npx tsc -b --noEmit && npm run lint && npm run build
```

**编译不过 = 不合格。不准带着编译错误进评审。**

### 改动完成后必跑（Developer Agent）

```bash
python scripts/verify_all.py --stage development
```

详见 `.agents/skills/run-verify.md`

### PR 前必跑（Developer + Code Reviewer）

```bash
./scripts/ci_gate.sh
cd apps/dsa-web && npm ci && npm run lint && npm run build
python scripts/verify_all.py --stage prerelease
```

详见 `.agents/skills/run-ci.md`

## 阶段闸门纪律

| 闸门 | 触发时机 | 不通过时 |
|------|---------|---------|
| 需求消歧义 | 需求分析阶段末 | 等用户确认消歧义项 |
| 方案完整性 | 方案设计阶段末 | Gate Reviewer 审查 |
| 闸门评估 | 开发开工前 | PM 拍板回退 |
| 编译自检 | 开发完成后 | 修复编译错误 |
| 代码评审 | 编译通过后 | PM 拍板回退 |
| 测试验证 | 评审通过后 | PM 拍板回退 |

## 绝对禁止项（违反即阻塞）

- ❌ 带编译错误的代码进入评审
- ❌ Gate Reviewer 自己修改需求/方案
- ❌ Code Reviewer 自己修改代码
- ❌ QA Tester 自己修改代码/需求
- ❌ 跳过验证脚本执行
- ❌ 不带需求文档就评审
- ❌ 不带闸门通过就开工

## 回退上限

- 同一阶段连续回退 ≥ 3 次 → PM 暂停流程，向用户汇报
- 理由：可能不是实现问题，而是需求或方案根因
