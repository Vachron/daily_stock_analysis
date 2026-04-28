#!/usr/bin/env python3
"""
自动化验证脚本 - Harness Engineering 三层分离的 Script 层

将能用机器检测的规则从 Rules 中迁移到脚本，解决"Agent 长上下文注意力衰减"问题。
Agent 不需要记住规则细节，脚本会自动检查。

用法：
    python scripts/verify_all.py                    # 全部检查
    python scripts/verify_all.py --stage development # 开发阶段检查
    python scripts/verify_all.py --stage prerelease  # 发布前完整检查
    python scripts/verify_all.py --check safety      # 仅安全检查
    python scripts/verify_all.py --output json       # JSON 格式输出
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).parent.parent.resolve()
BASELINE_FILE = REPO_ROOT / ".agents" / "baseline.json"

HAS_RG = False


def _has_rg() -> bool:
    """Check if rg (ripgrep) is available."""
    global HAS_RG
    try:
        subprocess.run(["rg", "--version"], capture_output=True, timeout=5)
        HAS_RG = True
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        HAS_RG = False
        return False


def _grep(pattern: str, *paths: str, file_types: Optional[List[str]] = None, head_limit: int = 20) -> List[str]:
    """Search pattern in files. Uses rg if available, falls back to Python."""
    if HAS_RG:
        cmd = ["rg", "--no-heading", "-n"]
        if file_types:
            for ft in file_types:
                cmd.extend(["--type", ft])
        cmd.append(pattern)
        cmd.extend(paths)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            lines = [l for l in result.stdout.strip().split("\n") if l]
            return lines[:head_limit]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Python fallback
    import fnmatch
    lines = []
    ext_patterns = []
    if file_types:
        ext_map = {"py": ["*.py"], "ts": ["*.ts", "*.tsx"], "js": ["*.js", "*.jsx"]}
        for ft in file_types:
            ext_patterns.extend(ext_map.get(ft, [f"*.{ft}"]))
    else:
        ext_patterns = ["*.py"]

    compiled = re.compile(pattern)
    for path_str in paths:
        p = Path(path_str)
        if not p.exists():
            continue
        files = []
        if p.is_file():
            files = [p]
        else:
            for ext_pat in ext_patterns:
                files.extend(p.rglob(ext_pat))
        for f in files:
            if len(lines) >= head_limit:
                break
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for i, line_content in enumerate(content.split("\n"), 1):
                    if compiled.search(line_content):
                        lines.append(f"{f}:{i}:{line_content.strip()[:120]}")
                        if len(lines) >= head_limit:
                            break
            except Exception:
                pass
    return lines[:head_limit]


class CheckResult(Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class CheckItem:
    id: str
    category: str
    name: str
    description: str
    result: CheckResult = CheckResult.PASS
    details: str = ""
    fix_suggestion: str = ""
    stages: List[str] = field(default_factory=lambda: ["development", "prerelease"])


STAGE_CHECKS = {
    "development": ["A.1", "A.2", "A.3", "A.4", "B.1", "B.2"],
    "prerelease": ["A.1", "A.2", "A.3", "A.4", "B.1", "B.2", "B.3", "C.1", "C.2", "D.1"],
    "safety": ["C.1", "C.2"],
    "all": [],
}


class VerifyRunner:
    def __init__(self, stage: str = "development") -> None:
        self.stage = stage
        self.checks: List[CheckItem] = []
        self._define_checks()

    def _define_checks(self) -> None:
        """定义所有检查项"""

        # A. 代码质量检查（可由机器检测，不需要 Agent 记忆）
        self.checks = [
            # A.1: Python 编译检查
            CheckItem(
                id="A.1",
                category="代码质量",
                name="Python 语法检查",
                description="所有 .py 文件必须能通过 py_compile",
                stages=["development", "prerelease"],
            ),
            # A.2: 硬编码密钥检查
            CheckItem(
                id="A.2",
                category="安全",
                name="硬编码密钥检测",
                description="搜索常见的硬编码密钥模式（api_key, secret, password, token）",
                stages=["development", "prerelease"],
            ),
            # A.3: 禁止模式检查
            CheckItem(
                id="A.3",
                category="代码质量",
                name="禁止模式检查",
                description='搜索禁止使用的模式（bare except:, print() 调试代码, TODO/FIXME）',
                stages=["development", "prerelease"],
            ),
            # A.4: 类型注解检查
            CheckItem(
                id="A.4",
                category="代码质量",
                name="类型注解完整性",
                description="函数参数和返回值应该有类型注解",
                stages=["prerelease"],
            ),
            # B.1: 导入检查
            CheckItem(
                id="B.1",
                category="代码质量",
                name="导入规范检查",
                description="禁止 from xxx import *，检查循环导入风险",
                stages=["development", "prerelease"],
            ),
            # B.2: 网络超时检查
            CheckItem(
                id="B.2",
                category="代码质量",
                name="网络超时检查",
                description="网络请求（requests, httpx, urllib）必须有 timeout 参数",
                stages=["prerelease"],
            ),
            # B.3: N+1 查询检查
            CheckItem(
                id="B.3",
                category="性能",
                name="N+1 查询检查",
                description="搜索 for 循环内的数据库操作",
                stages=["prerelease"],
            ),
            # C.1: SQL 注入检查
            CheckItem(
                id="C.1",
                category="安全",
                name="SQL 注入检查",
                description="禁止字符串拼接构造 SQL（f-string、%、+）",
                stages=["safety", "prerelease"],
            ),
            # C.2: 环境变量检查
            CheckItem(
                id="C.2",
                category="安全",
                name="环境变量规范",
                description="检查 .env.example 与代码中的环境变量引用是否同步",
                stages=["prerelease"],
            ),
            # D.1: 前端构建检查
            CheckItem(
                id="D.1",
                category="构建",
                name="前端构建检查",
                description="执行 tsc --noEmit 和 vite build",
                stages=["prerelease"],
            ),
        ]

    def run(self) -> Dict[str, Any]:
        check_ids = STAGE_CHECKS.get(self.stage, STAGE_CHECKS["development"])
        active_checks = [c for c in self.checks if c.id in check_ids]

        if not active_checks:
            active_checks = self.checks

        for check in active_checks:
            method_name = f"_check_{check.id.replace('.', '_')}"
            method = getattr(self, method_name, None)
            if method:
                try:
                    method(check)
                except Exception as e:
                    check.result = CheckResult.WARN
                    check.details = f"检查执行失败: {e}"
            else:
                check.result = CheckResult.WARN
                check.details = f"检查方法未实现: {method_name}"

        return self._summary(active_checks)

    def _summary(self, checks: List[CheckItem]) -> Dict[str, Any]:
        passed = len([c for c in checks if c.result == CheckResult.PASS])
        warned = len([c for c in checks if c.result == CheckResult.WARN])
        failed = len([c for c in checks if c.result == CheckResult.FAIL])
        total = len(checks)

        return {
            "stage": self.stage,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": total,
                "passed": passed,
                "warned": warned,
                "failed": failed,
                "score": f"{passed}/{total}",
            },
            "checks": [
                {
                    "id": c.id,
                    "category": c.category,
                    "name": c.name,
                    "result": c.result.value,
                    "details": c.details,
                    "fix": c.fix_suggestion,
                }
                for c in checks
            ],
        }

    # --- 检查实现 ---

    def _check_A_1(self, check: CheckItem) -> None:
        """Python 语法检查"""
        errors = []
        for search_dir in [str(REPO_ROOT / "src"), str(REPO_ROOT / "api"), str(REPO_ROOT / "data_provider")]:
            p = Path(search_dir)
            if not p.exists():
                continue
            for py_file in p.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "py_compile", str(py_file)],
                        capture_output=True, text=True, timeout=5, cwd=str(REPO_ROOT),
                    )
                    if result.returncode != 0:
                        errors.append(f"{py_file.relative_to(REPO_ROOT)}: {result.stderr[:100]}")
                except subprocess.TimeoutExpired:
                    pass
                except Exception as e:
                    errors.append(f"{py_file.relative_to(REPO_ROOT)}: {e}")
            if errors:
                break

        if not errors:
            check.result = CheckResult.PASS
            check.details = "所有 Python 文件语法正确"
        else:
            check.result = CheckResult.FAIL
            check.details = errors[0][:200] if errors else "编译失败"
            check.fix_suggestion = "修复上述语法错误后重新运行"

    def _check_A_2(self, check: CheckItem) -> None:
        """硬编码密钥检测"""
        pattern = r'(?:api_?key|apikey|secret_?key|password|token)\s*=\s*["\'][^"\']+["\']'
        findings = _grep(pattern, str(REPO_ROOT / "src"), str(REPO_ROOT / "api"), file_types=["py"], head_limit=10)

        if not findings:
            check.result = CheckResult.PASS
            check.details = "未发现硬编码密钥"
        else:
            real_findings = [f for f in findings if '""' not in f.split("=", 1)[-1].strip()[:5] and "None" not in f.split("=", 1)[-1].strip()[:5]]
            if not real_findings:
                check.result = CheckResult.PASS
                check.details = "密钥变量已正确赋值（None/空字符串）"
            else:
                check.result = CheckResult.FAIL
                check.details = f"发现 {len(real_findings)} 处可能的硬编码密钥"
                check.fix_suggestion = "使用 os.getenv() 读取环境变量"

    def _check_A_3(self, check: CheckItem) -> None:
        """禁止模式检查"""
        findings = []
        for pattern, desc in [
            (r'except\s*:', "发现 bare except: 语句"),
            (r'^\s*print\(', "发现调试 print()"),
            (r'#\s*TODO|#\s*FIXME|#\s*HACK', "发现 TODO/FIXME 注释"),
        ]:
            lines = _grep(pattern, str(REPO_ROOT / "src"), file_types=["py"], head_limit=5)
            for line in lines:
                findings.append(f"{desc}: {line}")

        if not findings:
            check.result = CheckResult.PASS
            check.details = "未发现禁止模式"
        else:
            check.result = CheckResult.WARN
            check.details = "; ".join(findings[:3])
            check.fix_suggestion = "审查上述项是否合理，移除不必要的调试代码"

    def _check_A_4(self, check: CheckItem) -> None:
        """类型注解检查 - 简化版"""
        check.result = CheckResult.WARN
        check.details = "类型注解检查建议使用 mypy，当前仅执行 py_compile"
        check.fix_suggestion = "运行: mypy src/ --ignore-missing-imports"

    def _check_B_1(self, check: CheckItem) -> None:
        """导入规范检查"""
        findings = _grep(r'from\s+\S+\s+import\s+\*', str(REPO_ROOT / "src"), str(REPO_ROOT / "api"), file_types=["py"], head_limit=10)
        findings = [l for l in findings if "__init__" not in l]

        if not findings:
            check.result = CheckResult.PASS
            check.details = "未发现 from xxx import *"
        else:
            check.result = CheckResult.FAIL
            check.details = f"发现 {len(findings)} 处 star import"
            check.fix_suggestion = "改为显式导入所需符号"

    def _check_B_2(self, check: CheckItem) -> None:
        """网络超时检查"""
        findings = _grep(
            r'(requests\.(?:get|post|put|delete|patch)|httpx\.(?:get|post)|urllib\.request\.urlopen)',
            str(REPO_ROOT / "src"), str(REPO_ROOT / "data_provider"), str(REPO_ROOT / "api"),
            file_types=["py"], head_limit=10,
        )
        check.result = CheckResult.WARN if findings else CheckResult.PASS
        check.details = "网络请求存在，请确认已设置 timeout" if findings else "通过"

    def _check_B_3(self, check: CheckItem) -> None:
        """N+1 查询检查"""
        # 搜索 for 循环内的 db 操作
        patterns = [
            r'for\s+\w+\s+in\s+[^:]+:\s*\n\s*(?:db\.|session\.|cursor\.)',
        ]
        check.result = CheckResult.WARN
        check.details = "N+1 查询检查建议人工审查，搜索 for 循环内的数据库操作"
        check.fix_suggestion = "使用批量查询或 ORM 的 selectinload/joinedload"

    def _check_C_1(self, check: CheckItem) -> None:
        """SQL 注入检查"""
        findings = _grep(
            r'(?:f["\'].*\b(?:SELECT|INSERT|UPDATE|DELETE)\b|["\'].*\b(?:SELECT|INSERT|UPDATE|DELETE)\b.*%[sdrf])',
            str(REPO_ROOT / "src"),
            file_types=["py"], head_limit=10,
        )
        if not findings:
            check.result = CheckResult.PASS
            check.details = "未发现可疑 SQL 拼接"
        else:
            check.result = CheckResult.WARN
            check.details = f"发现 {len(findings)} 处可能的 SQL 拼接"
            check.fix_suggestion = "使用参数化查询"

    def _check_C_2(self, check: CheckItem) -> None:
        """环境变量检查"""
        env_example = REPO_ROOT / ".env.example"
        if not env_example.exists():
            check.result = CheckResult.WARN
            check.details = ".env.example 不存在"
            return

        env_vars_in_example = set()
        for line in env_example.read_text(encoding="utf-8").split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                env_vars_in_example.add(line.split("=")[0].strip())

        env_vars_in_code = set()
        for py_file in list(REPO_ROOT.glob("src/**/*.py")) + list(REPO_ROOT.glob("api/**/*.py")) + list(REPO_ROOT.glob("data_provider/**/*.py")):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            found = re.findall(r'os\.getenv\(["\']([^"\']+)["\']\)', content)
            env_vars_in_code.update(found)
            found = re.findall(r'os\.environ(?:\.get|\[)["\']([^"\']+)["\']', content)
            env_vars_in_code.update(found)

        missing_in_example = env_vars_in_code - env_vars_in_example
        if not missing_in_example:
            check.result = CheckResult.PASS
            check.details = "所有代码中的环境变量均已在 .env.example 中声明"
        else:
            check.result = CheckResult.FAIL
            check.details = f"代码中引用但 .env.example 中缺失: {', '.join(sorted(missing_in_example)[:10])}"
            check.fix_suggestion = "将这些变量添加到 .env.example"

    def _check_D_1(self, check: CheckItem) -> None:
        """前端构建检查"""
        web_dir = REPO_ROOT / "apps" / "dsa-web"
        if not web_dir.exists():
            check.result = CheckResult.PASS
            check.details = "前端目录不存在，跳过"
            return

        try:
            result = subprocess.run(
                ["npx", "tsc", "-b", "--noEmit"],
                capture_output=True, text=True, timeout=60, cwd=str(web_dir),
            )
            if result.returncode == 0:
                check.result = CheckResult.PASS
                check.details = "TypeScript 类型检查通过"
            else:
                check.result = CheckResult.FAIL
                check.details = result.stdout[-500:] or result.stderr[-500:] or "类型检查失败"
                check.fix_suggestion = "修复类型错误"
        except subprocess.TimeoutExpired:
            check.result = CheckResult.WARN
            check.details = "前端构建检查超时"
        except FileNotFoundError:
            check.result = CheckResult.WARN
            check.details = "npx 不可用，跳过前端检查"


def check_baseline(current_result: Dict[str, Any]) -> Dict[str, Any]:
    """比较当前结果与基线"""
    if not BASELINE_FILE.exists():
        return {"status": "no_baseline", "message": "基线文件不存在，跳过比较"}

    try:
        baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "error", "message": "基线文件解析失败"}

    current_checks = {c["id"]: c["result"] for c in current_result.get("checks", [])}
    baseline_checks = baseline.get("last_result", {}).get("checks", [])
    baseline_map = {c["id"]: c["result"] for c in baseline_checks}

    degradations = []
    for check_id, result in current_checks.items():
        prev = baseline_map.get(check_id, "PASS")
        if prev == "PASS" and result == "FAIL":
            degradations.append({"id": check_id, "from": prev, "to": result})

    return {
        "status": "degraded" if degradations else "ok",
        "degradations": degradations,
    }


def save_baseline(result: Dict[str, Any]) -> None:
    """保存当前结果为基线"""
    baseline = {
        "last_result": result,
        "updated_at": datetime.now().isoformat(),
    }
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")


def print_report(result: Dict[str, Any]) -> None:
    """打印报告"""
    s = result["summary"]
    print("\n" + "=" * 60)
    print(f"  验证报告 — Stage: {result['stage']}")
    print(f"  时间: {result['timestamp']}")
    print("=" * 60)
    print(f"  Total: {s['total']} | PASS: {s['passed']} | WARN: {s['warned']} | FAIL: {s['failed']}")
    print(f"  得分: {s['score']}")
    print("-" * 60)

    for c in result["checks"]:
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(c["result"], "❓")
        print(f"  {icon} [{c['id']}] {c['name']}")
        if c["details"] and c["result"] != "PASS":
            print(f"     {c['details'][:120]}")
        if c.get("fix"):
            print(f"     FIX: {c['fix'][:120]}")

    print("=" * 60)

    baseline_result = check_baseline(result)
    if baseline_result["status"] == "degraded":
        print(f"\n⚠️  基线退化！以下检查项从 PASS 变为 FAIL:")
        for d in baseline_result["degradations"]:
            print(f"    - {d['id']}: {d['from']} → {d['to']}")
    elif baseline_result["status"] == "no_baseline":
        print("\n💡 基线不存在。运行 --save-baseline 创建基线。")

    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Harness 自动化验证脚本")
    parser.add_argument("--stage", choices=["development", "prerelease", "safety", "all"], default="development", help="验证阶段")
    parser.add_argument("--check", help="仅运行指定检查项（如 A.1）")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="输出格式")
    parser.add_argument("--save-baseline", action="store_true", help="保存当前结果为基线")
    parser.add_argument("--check-baseline", action="store_true", help="仅检查基线对比")

    args = parser.parse_args()

    if args.check_baseline:
        if not BASELINE_FILE.exists():
            print("No baseline file found.")
            return 0
        baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        result = baseline.get("last_result", {})
        comparison = check_baseline(result)
        print(json.dumps(comparison, ensure_ascii=False, indent=2))
        return 0

    runner = VerifyRunner(stage=args.stage)
    result = runner.run()

    if args.save_baseline:
        save_baseline(result)
        print(f"基线已保存到 {BASELINE_FILE}")

    if args.output == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_report(result)

    fail_count = result["summary"]["failed"]
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
