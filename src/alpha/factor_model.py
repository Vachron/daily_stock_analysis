# -*- coding: utf-8 -*-
"""Factor model — load parameterized strategy YAML and render factor values into instructions.

Supports:
- Backward-compatible loading (strategies without `factors` section still work)
- {{factor_id}} placeholder substitution
- Factor value validation against declared range
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


@dataclass
class FactorDefinition:
    id: str
    display_name: str
    type: str  # "float" | "int" | "bool"
    default: float
    range: Tuple[float, float]
    step: float

    def validate(self, value: float) -> bool:
        lo, hi = self.range
        return lo <= value <= hi

    def clamp(self, value: float) -> float:
        lo, hi = self.range
        return max(lo, min(hi, value))


@dataclass
class StrategyTemplate:
    name: str
    display_name: str
    description: str
    category: str
    factors: List[FactorDefinition]
    instructions_template: str
    weight: float = 1.0
    raw_data: Dict[str, Any] = field(default_factory=dict)


class FactorModel:
    @classmethod
    def load_strategy(cls, path: str) -> StrategyTemplate:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        name = raw.get("name", Path(path).stem)
        display_name = raw.get("display_name", name)
        description = raw.get("description", "")
        category = raw.get("category", "unknown")
        instructions = raw.get("instructions", "")

        factors: List[FactorDefinition] = []
        raw_factors = raw.get("factors", [])
        for rf in raw_factors:
            factors.append(FactorDefinition(
                id=rf["id"],
                display_name=rf.get("display_name", rf["id"]),
                type=rf.get("type", "float"),
                default=float(rf.get("default", 0)),
                range=(
                    float(rf.get("range", [0, 100])[0]),
                    float(rf.get("range", [0, 100])[1]),
                ),
                step=float(rf.get("step", 1)),
            ))

        return StrategyTemplate(
            name=name,
            display_name=display_name,
            description=description,
            category=category,
            factors=factors,
            instructions_template=instructions,
            weight=float(raw.get("default_priority", 100)) / 100.0,
            raw_data=raw,
        )

    @classmethod
    def load_strategies(cls, strategy_dir: str, names: Optional[List[str]] = None) -> List[StrategyTemplate]:
        dir_path = Path(strategy_dir)
        if not dir_path.exists():
            raise FileNotFoundError(f"Strategy directory not found: {strategy_dir}")

        templates: List[StrategyTemplate] = []
        for yaml_file in sorted(dir_path.glob("*.yaml")):
            if names and yaml_file.stem not in names:
                continue
            try:
                tmpl = cls.load_strategy(str(yaml_file))
                templates.append(tmpl)
            except Exception as e:
                logger.warning("Failed to load strategy %s: %s", yaml_file.name, e)

        return templates

    @classmethod
    def render_instructions(cls, template: StrategyTemplate, factor_values: Optional[Dict[str, float]] = None) -> str:
        text = template.instructions_template
        values = factor_values or {}

        for factor in template.factors:
            val = values.get(factor.id, factor.default)
            placeholder = "{{%s}}" % factor.id
            text = text.replace(placeholder, str(val))

        return text

    @classmethod
    def get_default_values(cls, template: StrategyTemplate) -> Dict[str, float]:
        return {f.id: f.default for f in template.factors}

    @classmethod
    def get_factor_space(cls, template: StrategyTemplate) -> Dict[str, Dict[str, Any]]:
        return {
            f.id: {
                "type": f.type,
                "default": f.default,
                "range": list(f.range),
                "step": f.step,
            }
            for f in template.factors
        }

    @classmethod
    def validate_values(cls, template: StrategyTemplate, values: Dict[str, float]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        for factor in template.factors:
            if factor.id not in values:
                continue
            val = values[factor.id]
            if not factor.validate(val):
                errors.append(
                    "Factor '%s' value %.4f out of range [%.4f, %.4f]"
                    % (factor.id, val, factor.range[0], factor.range[1])
                )
        return len(errors) == 0, errors

    @classmethod
    def clamp_values(cls, template: StrategyTemplate, values: Dict[str, float]) -> Dict[str, float]:
        clamped: Dict[str, float] = {}
        for factor in template.factors:
            if factor.id in values:
                clamped[factor.id] = factor.clamp(values[factor.id])
            else:
                clamped[factor.id] = factor.default
        return clamped

    @classmethod
    def get_factor_stats(cls, templates: List[StrategyTemplate]) -> Dict[str, Any]:
        total_factors = sum(len(t.factors) for t in templates)
        param_count = sum(1 for t in templates if t.factors)
        return {
            "total_strategies": len(templates),
            "parameterized_strategies": param_count,
            "total_factors": total_factors,
            "strategies_without_factors": [
                t.name for t in templates if not t.factors
            ],
        }
