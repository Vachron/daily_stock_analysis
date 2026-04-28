# -*- coding: utf-8 -*-
"""Strategy generator — LLM-driven strategy creation and mutation.

Supports:
1. Create new strategy YAML from natural language description
2. Mutate existing strategy (modify instructions, add/remove factors)
3. Validate generated YAML before writing to disk

Uses existing LLM infrastructure from src/agent/llm_adapter.py.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.alpha.factor_model import FactorModel

logger = logging.getLogger(__name__)

STRATEGY_GENERATION_PROMPT = """你是一个量化策略设计师。根据用户的自然语言描述，生成一个参数化的量化策略 YAML 文件。

## YAML 格式要求

```yaml
name: strategy_name
display_name: 策略中文名
description: 一句话描述
category: trend|reversal|momentum|volume|framework
required_tools:
  - get_daily_history

instructions: |
  **策略名**

  详细指令...

factors:
  - id: factor_id
    display_name: 因子中文名
    type: float
    default: 默认值
    range: [最小值, 最大值]
    step: 步长
```

## 规则

1. `name` 必须英文 snake_case
2. `category` 选: trend, reversal, momentum, volume, framework
3. `instructions` 中能用 `{{factor_id}}` 占位符的地方尽量用，方便参数化
4. 每个策略至少 3 个、最多 8 个因子
5. 因子 `range` 要合理（如趋势得分 5-25，下跌阈值 0.05-0.40）
6. 输出纯 YAML，不要 Markdown 代码块包裹

## 用户需求

{user_request}

## 现有策略参考

{existing_strategies}
"""


class StrategyGenerator:
    def __init__(self, strategy_dir: str = "strategies", llm_adapter: Any = None):
        self.strategy_dir = Path(strategy_dir)
        self.llm_adapter = llm_adapter

    def _get_existing_strategies_summary(self) -> str:
        if not self.strategy_dir.exists():
            return "无现有策略"

        summaries = []
        for yaml_file in sorted(self.strategy_dir.glob("*.yaml")):
            try:
                tmpl = FactorModel.load_strategy(str(yaml_file))
                factor_info = [f.id for f in tmpl.factors] if tmpl.factors else ["无参数化因子"]
                summaries.append(
                    "- %s (%s/%s): %s — 因子: %s"
                    % (tmpl.name, tmpl.display_name, tmpl.category, tmpl.description, ", ".join(factor_info))
                )
            except Exception:
                summaries.append("- %s (无法解析)" % yaml_file.stem)

        return "\n".join(summaries[:15])

    def generate_from_prompt(self, user_request: str) -> Optional[str]:
        if self.llm_adapter is None:
            logger.warning("No LLM adapter configured, using template-based generation")
            return self._generate_template(user_request)

        prompt = STRATEGY_GENERATION_PROMPT.format(
            user_request=user_request,
            existing_strategies=self._get_existing_strategies_summary(),
        )

        try:
            raw_response = self.llm_adapter.complete(prompt)
            yaml_content = self._extract_yaml(raw_response)
            if self._validate_yaml(yaml_content):
                return yaml_content
            return None
        except Exception as e:
            logger.error("LLM strategy generation failed: %s", e)
            return None

    def _extract_yaml(self, text: str) -> str:
        text = text.strip()
        if "```yaml" in text:
            start = text.find("```yaml") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()
        return text

    def _validate_yaml(self, yaml_content: str) -> bool:
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            logger.warning("Invalid YAML: %s", e)
            return False

        if not isinstance(data, dict):
            logger.warning("Root must be a dict")
            return False

        required_fields = ["name", "category", "instructions"]
        for field in required_fields:
            if field not in data:
                logger.warning("Missing required field: %s", field)
                return False

        name = data.get("name", "")
        if not name or " " in name or not name.isascii():
            logger.warning("Invalid strategy name: '%s'", name)
            return False

        valid_categories = {"trend", "reversal", "momentum", "volume", "framework"}
        if data.get("category") not in valid_categories:
            logger.warning("Invalid category: %s", data.get("category"))
            return False

        return True

    def save_strategy(self, yaml_content: str, filename: Optional[str] = None) -> Optional[str]:
        if not self._validate_yaml(yaml_content):
            return None

        try:
            data = yaml.safe_load(yaml_content)
            name = data.get("name", "generated_strategy")
            if filename is None:
                filename = name + ".yaml"

            filepath = self.strategy_dir / filename

            if filepath.exists():
                base = name
                for i in range(1, 100):
                    filename = "%s_v%d.yaml" % (base, i)
                    filepath = self.strategy_dir / filename
                    if not filepath.exists():
                        break

            filepath.write_text(yaml_content, encoding="utf-8")
            logger.info("Strategy saved: %s", filepath)
            return str(filepath)
        except Exception as e:
            logger.error("Failed to save strategy: %s", e)
            return None

    def _generate_template(self, user_request: str) -> Optional[str]:
        name_slug = user_request[:20].replace(" ", "_").replace("，", "_").lower()
        name_slug = "".join(c for c in name_slug if c.isalnum() or c == "_").strip("_") or "custom"

        template = yaml.dump({
            "name": name_slug,
            "display_name": user_request[:30],
            "description": user_request[:100],
            "category": "framework",
            "required_tools": ["get_daily_history"],
            "instructions": "**%s**\n\n请根据以下描述实现策略逻辑:\n\n%s\n\n评分调整:\n- 条件满足: sentiment_score +10\n- 条件不满足: 不调整" % (user_request[:20], user_request),
            "factors": [
                {"id": "threshold_1", "display_name": "阈值1", "type": "float", "default": 10.0, "range": [1.0, 30.0], "step": 1.0},
                {"id": "threshold_2", "display_name": "阈值2", "type": "float", "default": 5.0, "range": [1.0, 20.0], "step": 1.0},
                {"id": "score_weight", "display_name": "得分权重", "type": "float", "default": 8.0, "range": [1.0, 20.0], "step": 1.0},
            ],
        }, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return template

    def mutate_strategy(self, strategy_name: str, mutation_desc: str) -> Optional[str]:
        filepath = self.strategy_dir / ("%s.yaml" % strategy_name)
        if not filepath.exists():
            logger.warning("Strategy not found: %s", strategy_name)
            return None

        try:
            tmpl = FactorModel.load_strategy(str(filepath))
            existing_yaml = filepath.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("Failed to load strategy: %s", e)
            return None

        if self.llm_adapter is None:
            return self._mutate_simple(filepath, strategy_name, mutation_desc)

        prompt = """你是一个量化策略设计师。修改以下现有策略。

## 现有策略 YAML

{yaml}

## 修改要求

{mutation}

## 规则

1. 保持 name 不变
2. 可以修改 instructions 中的条件描述
3. 可以增删因子（factors 段）
4. 输出纯 YAML，不要 Markdown 代码块
""".format(yaml=existing_yaml[:4000], mutation=mutation_desc)

        try:
            response = self.llm_adapter.complete(prompt)
            new_yaml = self._extract_yaml(response)
            if self._validate_yaml(new_yaml):
                backup_path = filepath.with_suffix(".yaml.bak")
                filepath.rename(backup_path)
                filepath.write_text(new_yaml, encoding="utf-8")
                logger.info("Strategy mutated: %s (backup: %s)", strategy_name, backup_path)
                return str(filepath)
        except Exception as e:
            logger.error("Mutation failed: %s", e)

        return None

    def _mutate_simple(self, filepath: Path, strategy_name: str, mutation_desc: str) -> Optional[str]:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            data = yaml.safe_load(content)
            data["_mutation_note"] = mutation_desc

            backup = filepath.with_suffix(".yaml.bak")
            backup.write_text(content, encoding="utf-8")

            with open(filepath, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

            logger.info("Simple mutation applied to %s (backup: %s)", strategy_name, backup)
            return str(filepath)
        except Exception as e:
            logger.error("Simple mutation failed: %s", e)
            return None
