# -*- coding: utf-8 -*-
"""YAML 策略到 BacktestStrategy 的桥接适配器 (FR-002)."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Type

import numpy as np
import yaml

from src.backtest.strategy import BacktestStrategy
from src.backtest.lib import SMA, EMA, crossover, crossunder, MACD, RSI

logger = logging.getLogger(__name__)

STRATEGIES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "strategies")


class YAMLParseError(Exception):
    """YAML 策略解析错误."""

    def __init__(self, strategy_name: str, message: str) -> None:
        self.strategy_name = strategy_name
        super().__init__(f"YAML解析错误 [{strategy_name}]: {message}")


def list_yaml_strategies(strategies_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """扫描策略目录，返回策略元信息列表."""
    base_dir = strategies_dir or STRATEGIES_DIR
    base_dir = os.path.abspath(base_dir)
    if not os.path.isdir(base_dir):
        return []

    strategies = []
    for fname in sorted(os.listdir(base_dir)):
        if not fname.endswith(".yaml"):
            continue
        path = os.path.join(base_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                doc = yaml.safe_load(f)
            if not isinstance(doc, dict):
                continue
            name = doc.get("name", fname[:-5])
            strategies.append({
                "name": name,
                "display_name": doc.get("display_name", name),
                "description": doc.get("description", ""),
                "category": doc.get("category", "unknown"),
                "factors": doc.get("factors", []),
                "market_regimes": doc.get("market_regimes", []),
                "file": fname,
            })
        except Exception as exc:
            logger.warning("解析策略文件失败: %s, error=%s", fname, exc)
    return strategies


def load_yaml_strategy(strategy_name: str, strategies_dir: Optional[str] = None) -> Dict[str, Any]:
    """加载指定策略的 YAML 定义."""
    base_dir = strategies_dir or STRATEGIES_DIR
    base_dir = os.path.abspath(base_dir)
    fname = f"{strategy_name}.yaml"
    path = os.path.join(base_dir, fname)
    if not os.path.exists(path):
        raise YAMLParseError(strategy_name, f"策略文件不存在: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)
    except Exception as exc:
        raise YAMLParseError(strategy_name, f"YAML 解析失败: {exc}")
    if not isinstance(doc, dict):
        raise YAMLParseError(strategy_name, "YAML 内容不是字典格式")
    return doc


def yaml_to_strategy_class(
    strategy_name: str,
    strategies_dir: Optional[str] = None,
) -> Type[BacktestStrategy]:
    """将 YAML 策略转换为 Strategy 子类 (FR-002).

    Args:
        strategy_name: 策略名 (不含 .yaml)
        strategies_dir: 策略目录

    Returns:
        一个 BacktestStrategy 的子类
    """
    doc = load_yaml_strategy(strategy_name, strategies_dir)
    factors = doc.get("factors", [])
    category = doc.get("category", "unknown")
    instructions = doc.get("instructions", "")
    display_name = doc.get("display_name", strategy_name)

    factor_ids = [f["id"] for f in factors]
    factor_defaults = {f["id"]: f["default"] for f in factors}
    factor_types = {f["id"]: f.get("type", "float") for f in factors}

    def _make_init(self, **kwargs):
        super(type(self), self).__init__()
        for fid in factor_ids:
            val = kwargs.get(fid, factor_defaults.get(fid))
            if factor_types.get(fid) == "int":
                val = int(val)
            else:
                val = float(val)
            setattr(self, fid, val)
        self._category = category
        self._display_name = display_name
        self._ma_values: Dict[str, np.ndarray] = {}

    def _make_init_method(self):
        """根据 YAML factors 注册指标."""
        close_series = self.data.Close

        has_close_above_ma = False
        for fid in factor_ids:
            if fid.endswith("_window"):
                ma_val = getattr(self, fid, 20)
                if isinstance(ma_val, (int, float)) and ma_val > 0:
                    arr = self.I(SMA, self.data.Close, int(ma_val), name=f"SMA_{fid}")
                    self._ma_values[fid] = arr

        for fid in factor_ids:
            if fid.endswith("_cross_score"):
                pass
            elif fid.endswith("_score"):
                pass
            elif fid.endswith("_penalty"):
                pass

    def _make_next(self, i):
        """根据 YAML instructions 的评分规则执行交易逻辑."""
        has_position = any(not t._is_closed for t in self.trades)

        score = 0.0
        buy_signal = False
        sell_signal = False

        short_id = None
        mid_id = None
        long_id = None
        for fid in factor_ids:
            if "short" in fid or fid.endswith("_cross_score"):
                short_id = fid if "short" in fid else short_id
            if "mid" in fid:
                mid_id = fid
            if "long" in fid:
                long_id = fid

        if short_id and mid_id and short_id in self._ma_values and mid_id in self._ma_values:
            short_ma = self._ma_values[short_id]
            mid_ma = self._ma_values[mid_id]
            if i > 0 and i < len(short_ma) and i < len(mid_ma):
                if not np.isnan(short_ma[i]) and not np.isnan(mid_ma[i]):
                    if short_ma[i] > mid_ma[i] and short_ma[i - 1] <= mid_ma[i - 1]:
                        score += getattr(self, next((f for f in factor_ids if "cross_score" in f), ""), 0) or 12.0
                        buy_signal = True
                    elif short_ma[i] < mid_ma[i] and short_ma[i - 1] >= mid_ma[i - 1]:
                        score += getattr(self, next((f for f in factor_ids if "penalty" in f), ""), 0) or -10.0
                        sell_signal = True

        if buy_signal and not has_position:
            self.buy(tag="yaml_strategy")
        elif sell_signal and has_position:
            for trade in list(self.trades):
                if not trade._is_closed:
                    trade.close()

    strategy_cls_name = f"YAMLStrategy_{strategy_name}"
    strategy_dict = {
        "__init__": _make_init,
        "init": _make_init_method,
        "next": _make_next,
        "__doc__": f"YAML策略: {display_name}\n{instructions[:200]}",
    }
    strategy_cls = type(strategy_cls_name, (BacktestStrategy,), strategy_dict)
    return strategy_cls
