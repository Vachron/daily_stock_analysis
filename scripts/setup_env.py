# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 一键环境安装与验证
===================================

在新电脑上快速搭建开发环境，自动检测并修复常见问题。

使用方法：
    python scripts/setup_env.py              # 完整安装（后端 + 前端）
    python scripts/setup_env.py --backend    # 仅安装后端
    python scripts/setup_env.py --frontend   # 仅安装前端
    python scripts/setup_env.py --check      # 仅检查当前环境
    python scripts/setup_env.py --fix        # 检查并尝试修复问题
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT
FRONTEND_DIR = PROJECT_ROOT / "apps" / "dsa-web"
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"


class SetupRunner:
    def __init__(self):
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.is_windows = platform.system() == "Windows"
        self.python_version = sys.version_info

    def _run(self, cmd: List[str], cwd: Optional[Path] = None, check: bool = True) -> Tuple[int, str]:
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=600,
                shell=self.is_windows,
            )
            output = result.stdout + result.stderr
            if check and result.returncode != 0:
                return result.returncode, output
            return result.returncode, output
        except FileNotFoundError:
            return -1, f"Command not found: {cmd[0]}"
        except subprocess.TimeoutExpired:
            return -2, f"Command timed out: {' '.join(cmd)}"
        except Exception as e:
            return -3, str(e)

    def _cmd_exists(self, name: str) -> bool:
        if self.is_windows:
            return shutil.which(f"{name}.cmd") is not None or shutil.which(name) is not None
        return shutil.which(name) is not None

    def print_header(self, title: str):
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}")

    def print_step(self, msg: str):
        print(f"  -> {msg}")

    def print_ok(self, msg: str):
        print(f"  ✅ {msg}")

    def print_warn(self, msg: str):
        print(f"  ⚠️  {msg}")
        self.warnings.append(msg)

    def print_fail(self, msg: str):
        print(f"  ❌ {msg}")
        self.issues.append(msg)

    def check_python_version(self) -> bool:
        self.print_header("检查 Python 版本")
        v = self.python_version
        print(f"  Python: {v.major}.{v.minor}.{v.micro}")
        if v.major < 3 or (v.major == 3 and v.minor < 10):
            self.print_fail(f"Python 3.10+ required, got {v.major}.{v.minor}")
            return False
        self.print_ok(f"Python {v.major}.{v.minor}.{v.micro} >= 3.10")
        return True

    def check_env_file(self) -> bool:
        self.print_header("检查 .env 配置文件")
        if ENV_FILE.exists():
            self.print_ok(f".env 文件已存在: {ENV_FILE}")
            return True
        if ENV_EXAMPLE.exists():
            shutil.copy2(ENV_EXAMPLE, ENV_FILE)
            self.print_warn(f"已从 .env.example 创建 .env，请编辑填入你的 API Key: {ENV_FILE}")
            return True
        self.print_fail(".env.example 不存在，无法自动创建 .env")
        return False

    def check_utf8_env(self) -> bool:
        self.print_header("检查 UTF-8 编码环境")
        if self.is_windows:
            utf8_mode = os.environ.get("PYTHONUTF8", "0")
            if utf8_mode == "1":
                self.print_ok("PYTHONUTF8=1 已设置")
                return True
            self.print_warn("PYTHONUTF8 未设置，Windows 下 pip install 可能遇到编码问题")
            print("     建议：设置系统环境变量 PYTHONUTF8=1，或在 PowerShell 中执行：")
            print("     $env:PYTHONUTF8 = '1'")
            return False
        self.print_ok("非 Windows 系统，UTF-8 默认支持")
        return True

    def check_powershell_policy(self) -> bool:
        if not self.is_windows:
            return True
        self.print_header("检查 PowerShell 执行策略")
        rc, output = self._run(
            ["powershell", "-Command", "Get-ExecutionPolicy -Scope CurrentUser"],
            check=False,
        )
        policy = output.strip() if rc == 0 else ""
        if policy in ("RemoteSigned", "Unrestricted", "Bypass"):
            self.print_ok(f"执行策略: {policy}")
            return True
        self.print_warn(f"当前执行策略: {policy}，可能阻止 npm 等工具运行")
        print("     修复命令（管理员 PowerShell）：")
        print("     Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force")
        return False

    def install_backend(self) -> bool:
        self.print_header("安装后端 Python 依赖")
        if not REQUIREMENTS.exists():
            self.print_fail(f"requirements.txt 不存在: {REQUIREMENTS}")
            return False

        if self.is_windows:
            os.environ.setdefault("PYTHONUTF8", "1")

        self.print_step("pip install -r requirements.txt ...")
        rc, output = self._run(
            [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)],
            check=False,
        )
        if rc == 0:
            self.print_ok("Python 依赖安装完成")
        else:
            self.print_fail("pip install 失败，尝试 --user 安装...")
            rc2, output2 = self._run(
                [sys.executable, "-m", "pip", "install", "--user", "-r", str(REQUIREMENTS)],
                check=False,
            )
            if rc2 == 0:
                self.print_ok("Python 依赖安装完成 (--user)")
            else:
                self.print_fail("pip install --user 也失败，请手动检查")
                print(output[-500:] if output else "")
                return False
        return True

    def verify_backend_deps(self) -> bool:
        self.print_header("验证后端关键依赖")
        deps = [
            ("fastapi", "fastapi"),
            ("uvicorn", "uvicorn"),
            ("pydantic", "pydantic"),
            ("pandas", "pandas"),
            ("numpy", "numpy"),
            ("litellm", "litellm"),
            ("efinance", "efinance"),
            ("akshare", "akshare"),
            ("yfinance", "yfinance"),
            ("baostock", "baostock"),
            ("tushare", "tushare"),
            ("pytdx", "pytdx"),
            ("jinja2", "jinja2"),
            ("tenacity", "tenacity"),
            ("schedule", "schedule"),
        ]
        all_ok = True
        missing = []
        for mod, pkg in deps:
            try:
                __import__(mod)
                self.print_ok(f"{pkg}")
            except ImportError:
                self.print_fail(f"{pkg} - 未安装")
                missing.append(pkg)
                all_ok = False
        if missing:
            self.print_warn(f"缺失包: {', '.join(missing)}")
            self.print_step(f"手动安装: pip install {' '.join(missing)}")
        return all_ok

    def check_node_npm(self) -> Tuple[bool, str, str]:
        self.print_header("检查 Node.js / npm")
        node_ver = ""
        npm_ver = ""
        rc1, out1 = self._run(["node", "--version"], check=False)
        if rc1 == 0:
            node_ver = out1.strip()
            self.print_ok(f"Node.js: {node_ver}")
        else:
            self.print_fail("Node.js 未安装，前端构建需要 Node.js 18+")
            print("     下载地址: https://nodejs.org/")
            return False, node_ver, npm_ver

        rc2, out2 = self._run(["npm", "--version"], check=False)
        if rc2 == 0:
            npm_ver = out2.strip()
            self.print_ok(f"npm: {npm_ver}")
        else:
            self.print_fail("npm 未安装")
            return False, node_ver, npm_ver

        major = int(node_ver.lstrip("v").split(".")[0]) if node_ver else 0
        if major < 18:
            self.print_fail(f"Node.js 版本过低 ({node_ver})，需要 18+")
            return False, node_ver, npm_ver

        return True, node_ver, npm_ver

    def install_frontend(self) -> bool:
        self.print_header("安装前端依赖并构建")
        if not FRONTEND_DIR.exists():
            self.print_fail(f"前端目录不存在: {FRONTEND_DIR}")
            return False

        lock_file = FRONTEND_DIR / "package-lock.json"
        if not lock_file.exists():
            self.print_warn("package-lock.json 不存在，将使用 npm install")

        node_modules = FRONTEND_DIR / "node_modules"
        if node_modules.exists():
            self.print_step("node_modules 已存在，跳过安装（如需重装请先删除 node_modules）")
        else:
            self.print_step("npm ci ...")
            rc, output = self._run(
                ["npm", "ci"],
                cwd=FRONTEND_DIR,
                check=False,
            )
            if rc != 0:
                self.print_warn("npm ci 失败，尝试 npm install ...")
                rc, output = self._run(
                    ["npm", "install"],
                    cwd=FRONTEND_DIR,
                    check=False,
                )
            if rc == 0:
                self.print_ok("前端依赖安装完成")
            else:
                self.print_fail("前端依赖安装失败")
                print(output[-500:] if output else "")
                return False

        self.print_step("npm run build ...")
        rc, output = self._run(
            ["npm", "run", "build"],
            cwd=FRONTEND_DIR,
            check=False,
        )
        if rc == 0:
            self.print_ok("前端构建成功")
        else:
            self.print_fail("前端构建失败")
            print(output[-800:] if output else "")
            return False

        static_index = PROJECT_ROOT / "static" / "index.html"
        if static_index.exists():
            self.print_ok(f"前端产物已输出: {static_index}")
        else:
            self.print_warn("未找到 static/index.html，构建可能未正确输出")

        return True

    def verify_config(self) -> bool:
        self.print_header("验证配置接入状态")
        os.environ.setdefault("WEBUI_AUTO_BUILD", "false")
        try:
            sys.path.insert(0, str(PROJECT_ROOT))
            from dotenv import load_dotenv
            load_dotenv(ENV_FILE)

            has_llm = False
            llm_keys = [
                "GEMINI_API_KEY", "GEMINI_API_KEYS",
                "DEEPSEEK_API_KEY", "AIHUBMIX_KEY",
                "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
            ]
            for k in llm_keys:
                if os.getenv(k, "").strip():
                    has_llm = True
                    break

            channels = os.getenv("LLM_CHANNELS", "").strip()
            if channels:
                has_llm = True

            if has_llm:
                model = os.getenv("LITELLM_MODEL", "").strip()
                self.print_ok(f"AI 模型已配置 (LITELLM_MODEL={model or '自动推断'})")
            else:
                self.print_warn("未配置 AI 模型 API Key，分析功能不可用")
                print("     请在 .env 中至少配置一个：GEMINI_API_KEY / AIHUBMIX_KEY / DEEPSEEK_API_KEY")

            has_search = bool(os.getenv("ANSPIRE_API_KEYS", "").strip() or
                              os.getenv("TAVILY_API_KEYS", "").strip() or
                              os.getenv("SERPAPI_API_KEYS", "").strip() or
                              os.getenv("BOCHA_API_KEYS", "").strip() or
                              os.getenv("BRAVE_API_KEYS", "").strip())
            if has_search:
                self.print_ok("搜索引擎已配置")
            else:
                self.print_warn("未配置搜索引擎，新闻舆情分析不可用")

            has_tushare = bool(os.getenv("TUSHARE_TOKEN", "").strip())
            if has_tushare:
                self.print_ok("Tushare Token 已配置")
            else:
                self.print_step("Tushare Token 未配置（可选，免费数据源仍可用）")

            return has_llm

        except Exception as e:
            self.print_fail(f"配置验证异常: {e}")
            return False

    def run_check(self):
        self.print_header("环境检查报告")
        print(f"  系统: {platform.system()} {platform.release()}")
        print(f"  Python: {sys.version}")
        print(f"  项目根目录: {PROJECT_ROOT}")
        print()

        self.check_python_version()
        self.check_utf8_env()
        self.check_powershell_policy()
        self.check_env_file()
        self.check_node_npm()
        self.verify_backend_deps()
        self.verify_config()

    def run_full_setup(self):
        self.print_header("A股自选股智能分析系统 - 环境安装")
        print(f"  系统: {platform.system()} {platform.release()}")
        print(f"  Python: {sys.version}")
        print(f"  项目根目录: {PROJECT_ROOT}")

        self.check_python_version()
        self.check_utf8_env()
        if self.is_windows:
            self.check_powershell_policy()
        self.check_env_file()

    def run_backend_setup(self):
        self.install_backend()
        self.verify_backend_deps()
        self.verify_config()

    def run_frontend_setup(self):
        self.check_node_npm()
        self.install_frontend()

    def print_summary(self):
        self.print_header("安装总结")
        if self.issues:
            print(f"  ❌ 问题 ({len(self.issues)}):")
            for i in self.issues:
                print(f"     - {i}")
        if self.warnings:
            print(f"  ⚠️  警告 ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"     - {w}")
        if not self.issues and not self.warnings:
            print("  🎉 所有检查通过，环境就绪！")
        print()
        if not self.issues:
            print("  启动命令:")
            print("    python main.py              # 完整模式")
            print("    python main.py --serve-only # 仅 Web 服务")
            print("    python test_env.py          # 验证配置")
        print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="A股自选股智能分析系统 - 环境安装与验证")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--backend", action="store_true", help="仅安装后端")
    group.add_argument("--frontend", action="store_true", help="仅安装前端")
    group.add_argument("--check", action="store_true", help="仅检查当前环境")
    group.add_argument("--fix", action="store_true", help="检查并尝试修复问题")
    args = parser.parse_args()

    runner = SetupRunner()

    if args.check:
        runner.run_check()
    elif args.fix:
        runner.run_full_setup()
        runner.run_backend_setup()
        runner.run_frontend_setup()
    elif args.backend:
        runner.run_full_setup()
        runner.run_backend_setup()
    elif args.frontend:
        runner.run_full_setup()
        runner.run_frontend_setup()
    else:
        runner.run_full_setup()
        runner.run_backend_setup()
        runner.run_frontend_setup()

    runner.print_summary()
    sys.exit(1 if runner.issues else 0)


if __name__ == "__main__":
    main()
