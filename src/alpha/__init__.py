# -*- coding: utf-8 -*-
"""Alpha Excess Return System — factor-based alpha prediction and portfolio simulation.

Modules:
- factor_model: factor definition, YAML loading, parameterized rendering
- alpha_scorer: cross-section alpha prediction from factor scores
- portfolio_simulator: daily portfolio simulation with transaction costs
- alpha_evaluator: excess return metrics (IR, tracking error, factor IC)
"""

from __future__ import annotations
