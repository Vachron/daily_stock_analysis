# -*- coding: utf-8 -*-
"""
Data quality gate — look-ahead bias prevention and data integrity checks.

Ensures that factor calculation and backtesting use appropriate data
adjustment modes and that no future information leaks into historical
analysis.

Key rules:
1. Backtesting MUST use non-adjusted (raw) prices
2. Strategy signals SHOULD use backward-adjusted (hfq) prices
3. IC calculation MUST offset factor values and return windows
4. Fractal/pattern recognition MUST exclude unconfirmed bars
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AdjustMode(str, Enum):
    QFQ = "qfq"
    HFQ = "hfq"
    NONE = "none"


@dataclass
class LookAheadViolation:
    rule_id: str
    severity: str
    description: str
    file_path: str = ""
    line_number: int = 0
    suggestion: str = ""


@dataclass
class DataQualityReport:
    passed: bool = True
    violations: List[LookAheadViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_violation(self, v: LookAheadViolation) -> None:
        self.violations.append(v)
        if v.severity in ("high", "critical"):
            self.passed = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


ADJUST_MODE_FOR_PURPOSE = {
    "backtest": AdjustMode.NONE,
    "signal": AdjustMode.HFQ,
    "display": AdjustMode.QFQ,
    "ic_calculation": AdjustMode.HFQ,
}


def get_adjust_mode(purpose: str) -> AdjustMode:
    return ADJUST_MODE_FOR_PURPOSE.get(purpose, AdjustMode.QFQ)


def validate_adjust_for_purpose(purpose: str, actual_adjust: str) -> Optional[str]:
    expected = ADJUST_MODE_FOR_PURPOSE.get(purpose)
    if expected is None:
        return None
    if actual_adjust != expected.value:
        return (
            f"Adjust mode mismatch for purpose '{purpose}': "
            f"expected '{expected.value}', got '{actual_adjust}'"
        )
    return None


class LookAheadBiasScanner:
    """Scan strategy source code for look-ahead bias patterns."""

    PATTERNS = {
        "close_last1_in_indicator": {
            "regex": r"self\._calc_(sma|ema|rsi|bollinger|macd)\(close\b",
            "severity": "high",
            "description": "close[-1] may be included in indicator calculation; use close[:-1] for signal generation",
            "suggestion": "Pass close[:-1] to indicator functions, use close[-1] only for confirmation",
        },
        "fractal_unconfirmed_range": {
            "regex": r"range\(2,\s*len\(close\)\s*-\s*2\)",
            "severity": "medium",
            "description": "Fractal recognition includes unconfirmed bars at the end",
            "suggestion": "Use range(2, len(close) - CONFIRM_BARS) where CONFIRM_BARS >= 2",
        },
        "backtest_entry_same_day": {
            "regex": r"start_price\s*=\s*float\(start_daily\.close\)",
            "severity": "medium",
            "description": "Backtest entry price uses same-day close instead of next-day open",
            "suggestion": "Use next trading day's open price as entry, plus slippage",
        },
    }

    def scan_source(self, source: str, file_path: str = "") -> List[LookAheadViolation]:
        violations = []
        for rule_id, rule in self.PATTERNS.items():
            for match in re.finditer(rule["regex"], source):
                violations.append(LookAheadViolation(
                    rule_id=rule_id,
                    severity=rule["severity"],
                    description=rule["description"],
                    file_path=file_path,
                    line_number=source[:match.start()].count("\n") + 1,
                    suggestion=rule["suggestion"],
                ))
        return violations


def check_min_sample_size(bar_count: int, min_bars: int = 200) -> Optional[str]:
    if bar_count < min_bars:
        return f"Insufficient data: {bar_count} bars < minimum {min_bars}"
    return None


def check_survivorship_bias(has_delisted: bool, delisted_count: int = 0) -> Optional[str]:
    if not has_delisted:
        return (
            "Survivorship bias warning: delisted stocks may be missing from dataset. "
            "Results may be overstated."
        )
    return None


def gate_backtest_data(adjust_mode: str, bar_count: int = 0) -> DataQualityReport:
    report = DataQualityReport()

    mismatch = validate_adjust_for_purpose("backtest", adjust_mode)
    if mismatch:
        report.add_violation(LookAheadViolation(
            rule_id="backtest_adjust_mode",
            severity="high",
            description=mismatch,
            suggestion="Use adjust='none' for backtesting",
        ))

    if bar_count > 0:
        sample_issue = check_min_sample_size(bar_count)
        if sample_issue:
            report.add_warning(sample_issue)

    return report


def gate_ic_data(
    adjust_mode: str,
    bar_count: int = 0,
    factor_uses_t0_close: bool = False,
) -> DataQualityReport:
    report = DataQualityReport()

    mismatch = validate_adjust_for_purpose("ic_calculation", adjust_mode)
    if mismatch:
        report.add_violation(LookAheadViolation(
            rule_id="ic_adjust_mode",
            severity="high",
            description=mismatch,
            suggestion="Use adjust='hfq' for IC calculation",
        ))

    if factor_uses_t0_close:
        report.add_violation(LookAheadViolation(
            rule_id="ic_t0_overlap",
            severity="medium",
            description="Factor value uses T-0 close which overlaps with return window start",
            suggestion="Compute factor on close[:-1], compute returns from open[T:]",
        ))

    if bar_count > 0:
        sample_issue = check_min_sample_size(bar_count, min_bars=60)
        if sample_issue:
            report.add_warning(sample_issue)

    return report
