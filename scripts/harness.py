#!/usr/bin/env python3
"""
Harness Coordinator v2 — 7 Agent 流水线协调器

基于 Harness Engineering 理念的完整实现：
- Humans steer. Agents execute.
- 7 阶段状态机 + 回退路由 + 3 次回退升级
- 项目看板跨会话记忆
- 验证基线管理

用法：
    python scripts/harness.py init <task_name>
    python scripts/harness.py status <task_name>
    python scripts/harness.py board
    python scripts/harness.py validate
    python scripts/harness.py baseline --save
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).parent.parent.resolve()
AGENTS_DIR = REPO_ROOT / ".agents"
BOARD_FILE = AGENTS_DIR / "board" / "PROJECT_BOARD.md"
BASELINE_FILE = AGENTS_DIR / "baseline.json"
FEATURES_DIR = REPO_ROOT / "docs" / "features"
HARNESS_STATE_FILE = AGENTS_DIR / "harness_state.json"


class Stage(Enum):
    INIT = "init"
    REQ_ANALYSIS = "req_analysis"
    SOLUTION_DESIGN = "solution_design"
    GATE_REVIEW = "gate_review"
    DEVELOPMENT = "development"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    DELIVERY = "delivery"


class Agent(Enum):
    PM = "pm_orchestrator"
    REQ_ANALYST = "requirement_analyst"
    SOL_ARCHITECT = "solution_architect"
    GATE_REVIEWER = "gate_reviewer"
    DEVELOPER = "developer"
    CODE_REVIEWER = "code_reviewer"
    QA_TESTER = "qa_tester"
    REPORTER = "reporter"


STAGE_TO_AGENT: Dict[Stage, Agent] = {
    Stage.REQ_ANALYSIS: Agent.REQ_ANALYST,
    Stage.SOLUTION_DESIGN: Agent.SOL_ARCHITECT,
    Stage.GATE_REVIEW: Agent.GATE_REVIEWER,
    Stage.DEVELOPMENT: Agent.DEVELOPER,
    Stage.CODE_REVIEW: Agent.CODE_REVIEWER,
    Stage.TESTING: Agent.QA_TESTER,
    Stage.DELIVERY: Agent.REPORTER,
}

STAGE_DOCS: Dict[Stage, str] = {
    Stage.REQ_ANALYSIS: "01_REQUIREMENT_ANALYSIS.md",
    Stage.SOLUTION_DESIGN: "02_SOLUTION_DESIGN.md",
    Stage.GATE_REVIEW: "03_GATE_REVIEW.md",
    Stage.DEVELOPMENT: "04_DEVELOPMENT.md",
    Stage.CODE_REVIEW: "05_CODE_REVIEW.md",
    Stage.TESTING: "06_TEST_REPORT.md",
    Stage.DELIVERY: "07_DELIVERY_REPORT.md",
}

STAGE_ORDER: List[Stage] = [
    Stage.INIT,
    Stage.REQ_ANALYSIS,
    Stage.SOLUTION_DESIGN,
    Stage.GATE_REVIEW,
    Stage.DEVELOPMENT,
    Stage.CODE_REVIEW,
    Stage.TESTING,
    Stage.DELIVERY,
]

ROLLBACK_ROUTES: Dict[str, Dict[str, Stage]] = {
    Stage.GATE_REVIEW.value: {
        "req_issue": Stage.REQ_ANALYSIS,
        "sol_issue": Stage.SOLUTION_DESIGN,
    },
    Stage.CODE_REVIEW.value: {
        "code_issue": Stage.DEVELOPMENT,
        "design_drift": Stage.SOLUTION_DESIGN,
    },
    Stage.TESTING.value: {
        "code_defect": Stage.DEVELOPMENT,
        "req_missed": Stage.REQ_ANALYSIS,
    },
}

STAGE_RULES = {
    Stage.GATE_REVIEW.value: "Gate Reviewer 不能自己改需求或方案",
    Stage.CODE_REVIEW.value: "Code Reviewer 不能自己改代码",
    Stage.TESTING.value: "QA Tester 不能自己修 bug",
}


@dataclass
class TaskState:
    task_name: str
    task_dir: str
    current_stage: Stage = Stage.INIT
    current_agent: Optional[Agent] = None
    stage_history: List[Dict[str, Any]] = field(default_factory=list)
    rollback_count: Dict[str, int] = field(default_factory=lambda: {
        Stage.REQ_ANALYSIS.value: 0,
        Stage.SOLUTION_DESIGN.value: 0,
        Stage.GATE_REVIEW.value: 0,
        Stage.DEVELOPMENT.value: 0,
        Stage.CODE_REVIEW.value: 0,
        Stage.TESTING.value: 0,
    })
    consecutive_rollbacks: int = 0
    created_at: str = ""
    updated_at: str = ""


class HarnessCoordinatorV2:
    def __init__(self) -> None:
        self._ensure_dirs()
        self.state: Optional[TaskState] = None
        self._load_state()

    def _ensure_dirs(self) -> None:
        AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        (AGENTS_DIR / "board").mkdir(parents=True, exist_ok=True)
        FEATURES_DIR.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> None:
        if HARNESS_STATE_FILE.exists():
            data = json.loads(HARNESS_STATE_FILE.read_text(encoding="utf-8"))
            self.state = TaskState(
                task_name=data["task_name"],
                task_dir=data["task_dir"],
                current_stage=Stage(data["current_stage"]),
                current_agent=Agent(data["current_agent"]) if data.get("current_agent") else None,
                stage_history=data.get("stage_history", []),
                rollback_count=data.get("rollback_count", {}),
                consecutive_rollbacks=data.get("consecutive_rollbacks", 0),
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
            )

    def _save_state(self) -> None:
        if self.state:
            self.state.updated_at = datetime.now().isoformat()
            data = {
                "task_name": self.state.task_name,
                "task_dir": self.state.task_dir,
                "current_stage": self.state.current_stage.value,
                "current_agent": self.state.current_agent.value if self.state.current_agent else None,
                "stage_history": self.state.stage_history,
                "rollback_count": self.state.rollback_count,
                "consecutive_rollbacks": self.state.consecutive_rollbacks,
                "created_at": self.state.created_at,
                "updated_at": self.state.updated_at,
            }
            HARNESS_STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- Task Initialization ---

    def init_task(self, task_name: str) -> TaskState:
        task_dir_name = task_name.replace(" ", "_").replace("/", "-")
        task_dir = FEATURES_DIR / task_dir_name
        task_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now().isoformat()
        self.state = TaskState(
            task_name=task_name,
            task_dir=str(task_dir),
            current_stage=Stage.INIT,
            created_at=now,
            updated_at=now,
        )
        self._save_state()
        return self.state

    # --- Stage Management ---

    def advance_stage(self) -> Optional[Stage]:
        if not self.state:
            return None
        current_idx = STAGE_ORDER.index(self.state.current_stage)
        if current_idx >= len(STAGE_ORDER) - 1:
            return None
        next_stage = STAGE_ORDER[current_idx + 1]
        self.state.current_stage = next_stage
        self.state.current_agent = STAGE_TO_AGENT.get(next_stage)
        self._save_state()
        return next_stage

    def rollback(self, reason: str, target_key: Optional[str] = None) -> Optional[Stage]:
        if not self.state:
            return None

        current_stage_value = self.state.current_stage.value
        routes = ROLLBACK_ROUTES.get(current_stage_value, {})
        if not routes:
            print(f"[WARN] Stage {current_stage_value} 没有定义回退路由")
            return None

        print(f"\n[ROLLBACK] 回退原因: {reason}")
        print(f"  可选回退目标:")
        for key, stage in routes.items():
            print(f"    [{key}] → {stage.value}")

        if target_key and target_key in routes:
            chosen_key = target_key
        elif target_key and target_key not in routes:
            valid_keys = ", ".join(routes.keys())
            print(f"\n[ERROR] 无效的回退目标 '{target_key}'，可选值: {valid_keys}")
            return None
        elif len(routes) == 1:
            chosen_key = list(routes.keys())[0]
        else:
            prompt = "  请输入回退目标 ("
            prompt += "/".join(routes.keys())
            prompt += ") [默认: %s]: " % list(routes.keys())[0]
            chosen_key = input(prompt).strip()
            if not chosen_key:
                chosen_key = list(routes.keys())[0]
            elif chosen_key not in routes:
                print(f"\n[ERROR] 无效选择 '{chosen_key}'，使用默认值")
                chosen_key = list(routes.keys())[0]

        target_stage = routes[chosen_key]
        self.state.rollback_count[current_stage_value] = self.state.rollback_count.get(current_stage_value, 0) + 1
        self.state.consecutive_rollbacks += 1

        if self.state.consecutive_rollbacks >= 3:
            print(f"\n[ESCALATE] 同一阶段连续回退 {self.state.consecutive_rollbacks} 次")
            print("  → 暂停流程，建议重审需求或方案")

        self.state.current_stage = target_stage
        self.state.current_agent = STAGE_TO_AGENT.get(target_stage)
        self._save_state()
        print(f"  回退到: {target_stage.value} (Agent: {self.state.current_agent.value if self.state.current_agent else 'N/A'})")
        print(f"  规则: {STAGE_RULES.get(current_stage_value, '无')}")
        return target_stage

    def resolve_rollback(self) -> None:
        if self.state:
            self.state.consecutive_rollbacks = 0
            self._save_state()

    # --- Operations ---

    def show_board(self) -> None:
        if not BOARD_FILE.exists():
            print("[INFO] 项目看板尚未创建")
            return
        content = BOARD_FILE.read_text(encoding="utf-8")
        print("\n" + "=" * 60)
        print("  项目任务看板")
        print("=" * 60)
        print(content)

    def show_status(self) -> None:
        if not self.state:
            print("[INFO] 没有活跃任务。运行 `harness.py init <task_name>` 创建任务")
            return

        s = self.state
        print("\n" + "=" * 60)
        print(f"  任务: {s.task_name}")
        print(f"  目录: {s.task_dir}")
        print(f"  创建: {s.created_at}")
        print(f"  更新: {s.updated_at}")
        print("-" * 60)
        print(f"  当前阶段: {s.current_stage.value}")
        print(f"  当前 Agent: {s.current_agent.value if s.current_agent else 'N/A'}")

        if s.consecutive_rollbacks > 0:
            print(f"  ⚠ 连续回退: {s.consecutive_rollbacks}/3")

        print("\n  阶段历史:")
        for h in s.stage_history:
            entry_str = f"    [{h['time']}] {h['stage']}"
            if h.get("verdict"):
                entry_str += f" → {h['verdict']}"
            print(entry_str)

        print("\n  回退计数:")
        for stage_name, count in s.rollback_count.items():
            if count > 0:
                print(f"    {stage_name}: {count} 次")

        self._show_docs_status()

    def _show_docs_status(self) -> None:
        if not self.state:
            return
        task_dir = Path(self.state.task_dir)
        print("\n  文档状态:")
        for stage, doc_name in STAGE_DOCS.items():
            doc_path = task_dir / doc_name
            status = "✅" if doc_path.exists() else "⏳"
            stage_order = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else -1
            current_order = STAGE_ORDER.index(self.state.current_stage) if self.state.current_stage in STAGE_ORDER else -1
            if stage_order < current_order and not doc_path.exists():
                status = "❌ 缺失"
            print(f"    {status} S{stage_order}: {doc_name}")

    def run_verify(self, stage: str = "development") -> bool:
        print(f"\n[VERIFY] 运行自动化验证 (stage={stage})...")
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_all.py"), "--stage", stage, "--output", "json"],
            capture_output=True, text=True, timeout=60, cwd=str(REPO_ROOT),
        )
        if result.returncode == 0:
            print("  ✅ 全部通过")
            return True
        else:
            print(f"  ❌ 验证失败")
            try:
                data = json.loads(result.stdout)
                for c in data.get("checks", []):
                    if c["result"] == "FAIL":
                        print(f"    [{c['id']}] {c['name']} — {c.get('details', '')[:80]}")
            except Exception:
                pass
            return False

    def check_baseline(self) -> Dict[str, Any]:
        print("\n[BASELINE] 检查基线...")
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_all.py"), "--check-baseline"],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT),
        )
        try:
            return json.loads(result.stdout)
        except Exception:
            return {"status": "error", "message": result.stdout}

    def record_stage_history(self, verdict: str) -> None:
        if not self.state:
            return
        self.state.stage_history.append({
            "stage": self.state.current_stage.value,
            "agent": self.state.current_agent.value if self.state.current_agent else "N/A",
            "verdict": verdict,
            "time": datetime.now().isoformat(),
        })
        self._save_state()

    def show_pipeline_guide(self) -> None:
        print("\n" + "=" * 60)
        print("  Harness Engineering — 7 Agent 流水线")
        print("=" * 60)

        pipeline = [
            ("S1", "需求分析", "Requirement Analyst", "消歧义 → 验收标准 → 边界场景"),
            ("S2", "方案设计", "Solution Architect", "模块划分 → 接口定义 → 风险评估"),
            ("S3", "闸门评估", "Gate Reviewer", "8 维度审查 → 文件验证（开发前最后一关）"),
            ("S4", "开发实现", "Developer", "按方案落地 → 编译自检 → 验证脚本"),
            ("S5", "代码评审", "Code Reviewer", "6 维度审查 → 需求逐条对照"),
            ("S6", "测试验证", "QA Tester", "测试用例 → 残留检查 → 基线比对"),
            ("S7", "交付", "Reporter", "汇总报告 → 归档看板"),
        ]

        for stage_id, stage_name, agent_name, desc in pipeline:
            print(f"  [{stage_id}] {stage_name:8s} | {agent_name:20s} | {desc}")

        print("\n  Rules/Skills/Scripts 三层分离:")
        print("    Rules  → 流程规则（always-apply，15-25 行精要）")
        print("    Skills → 封装操作（告诉 Agent 怎么执行）")
        print("    Scripts→ 机器执行（verify_all.py，Agent 看结果即可）")
        print()

    def show_agents(self) -> None:
        print("\n" + "=" * 60)
        print("  7 Agent 角色 + 模型策略")
        print("=" * 60)

        agents_info = [
            ("PM Orchestrator", "流程总控", "轻量", "调度不需写代码"),
            ("Requirement Analyst", "需求分析", "轻量", "纯文本分析"),
            ("Solution Architect", "方案设计", "轻量", "偏文档输出"),
            ("Gate Reviewer", "闸门评估", "轻量", "审查模板化"),
            ("Developer", "写代码", "顶级", "唯一需要写代码的角色"),
            ("Code Reviewer", "代码评审", "中级", "需深度理解但不写"),
            ("QA Tester", "测试验证", "轻量", "测试用例偏文档"),
            ("Reporter", "交付报告", "轻量", "文档汇总"),
        ]

        for name, role, model, reason in agents_info:
            print(f"  {name:22s} | {role:10s} | {model:6s} | {reason}")

        print(f"\n  成本优化: 6/8 用轻量模型，只有 Developer 用顶级模型\n")

    def show_rules(self) -> None:
        print("\n" + "=" * 60)
        print("  规则优先级")
        print("=" * 60)

        rules = [
            ("P0", "safety.md", "安全护栏（最高优先级）"),
            ("P1", "workflow.md", "工作流规则（Always Apply）"),
            ("P1", "git.md", "Git 工作流规范"),
            ("P2", "coding.md", "编码约束（精简版，关键规则）"),
            ("P2", "model_selection.md", "模型选择策略"),
            ("P2", "validation.md", "自动化验证标准"),
        ]

        for priority, name, desc in rules:
            print(f"  [{priority}] {name:25s} — {desc}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Harness Coordinator v2 — 7 Agent 流水线协调器")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    subparsers.add_parser("pipeline", help="显示 7 Agent 流水线总览")
    subparsers.add_parser("agents", help="显示 Agent 角色和模型策略")
    subparsers.add_parser("rules", help="显示规则优先级")
    subparsers.add_parser("board", help="显示项目任务看板")
    subparsers.add_parser("status", help="显示当前任务状态")
    subparsers.add_parser("verify", help="运行自动化验证 (--stage development)")

    init_parser = subparsers.add_parser("init", help="初始化新任务")
    init_parser.add_argument("task_name", help="任务名称")

    advance_parser = subparsers.add_parser("advance", help="推进到下一阶段")
    rollback_parser = subparsers.add_parser("rollback", help="回退到上一阶段")
    rollback_parser.add_argument("--reason", default="未指定原因", help="回退原因")
    rollback_parser.add_argument("--target", default=None, help="回退目标（如 code_issue / design_drift / code_defect / req_missed）")

    resolve_parser = subparsers.add_parser("resolve", help="重置连续回退计数")

    history_parser = subparsers.add_parser("record", help="记录阶段判定")
    history_parser.add_argument("--verdict", required=True, help="判定结论")

    baseline_parser = subparsers.add_parser("baseline", help="基线管理")
    baseline_parser.add_argument("--save", action="store_true", help="保存当前验证结果为基线")
    baseline_parser.add_argument("--check", action="store_true", help="检查基线退化")

    args = parser.parse_args()
    coordinator = HarnessCoordinatorV2()

    if args.command == "pipeline":
        coordinator.show_pipeline_guide()
        return 0

    if args.command == "agents":
        coordinator.show_agents()
        return 0

    if args.command == "rules":
        coordinator.show_rules()
        return 0

    if args.command == "board":
        coordinator.show_board()
        return 0

    if args.command == "status":
        coordinator.show_status()
        return 0

    if args.command == "verify":
        coordinator.run_verify(args.stage if hasattr(args, 'stage') else "development")
        baseline_result = coordinator.check_baseline()
        if baseline_result.get("status") == "degraded":
            print("\n⚠️  基线退化！")
            for d in baseline_result.get("degradations", []):
                print(f"  - {d['id']}: {d['from']} → {d['to']}")
        return 0

    if args.command == "init":
        state = coordinator.init_task(args.task_name)
        print(f"[OK] 任务已初始化: {state.task_name}")
        print(f"  目录: {state.task_dir}")
        coordinator.show_pipeline_guide()
        return 0

    if args.command == "advance":
        if not coordinator.state:
            print("[ERROR] 没有活跃任务。先运行 `init`")
            return 1
        if coordinator.state.consecutive_rollbacks >= 3:
            print("[ESCALATE] 连续回退已达 3 次上限，建议重审需求")
            print("  运行 `harness.py resolve` 重置计数后继续")
            return 1
        next_stage = coordinator.advance_stage()
        if next_stage:
            print(f"[OK] 推进到: {next_stage.value}")
            print(f"  当前 Agent: {STAGE_TO_AGENT.get(next_stage, Agent.PM).value}")
            doc_name = STAGE_DOCS.get(next_stage)
            if doc_name:
                print(f"  需产出: {doc_name}")
        else:
            print("[INFO] 已是最后阶段（交付）")
        return 0

    if args.command == "rollback":
        if not coordinator.state:
            print("[ERROR] 没有活跃任务")
            return 1
        coordinator.rollback(args.reason, args.target)
        return 0

    if args.command == "resolve":
        if not coordinator.state:
            print("[ERROR] 没有活跃任务")
            return 1
        coordinator.resolve_rollback()
        print("[OK] 连续回退计数已重置")
        return 0

    if args.command == "record":
        if not coordinator.state:
            print("[ERROR] 没有活跃任务")
            return 1
        coordinator.record_stage_history(args.verdict)
        print(f"[OK] 已记录: {coordinator.state.current_stage.value} → {args.verdict}")
        return 0

    if args.command == "baseline":
        if args.save:
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "verify_all.py"), "--stage", "development", "--save-baseline"],
                timeout=60, cwd=str(REPO_ROOT),
            )
            return result.returncode
        if args.check:
            result = coordinator.check_baseline()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        print("Usage: harness.py baseline [--save | --check]")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
