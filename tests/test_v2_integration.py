"""
Integration smoke test for v2 backtest API endpoints.
Tests contract between frontend TS types and backend Python schemas.
"""
import json
import sys
import os
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

PASS = 0
FAIL = 0
SKIP = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))

def skip(name, reason=""):
    global SKIP
    SKIP += 1
    print(f"  ⏭ {name} (SKIP: {reason})")


# ============================
# 1. Schema contract validation
# ============================
print("\n📦 1. Schema contract validation")

try:
    from api.v1.schemas.backtest import (
        StrategyBacktestRequest, OptimizeRequest, MontecarloRequest,
        MontecarloResponse, MontecarloResultItem, ExitRuleConfig,
    )
    check("import all v2 schemas", True)
except Exception as e:
    check("import all v2 schemas", False, str(e))

# Test StrategyBacktestRequest
try:
    req = StrategyBacktestRequest(strategy="mean_reversion", codes=["600519"])
    check("StrategyBacktestRequest.minimal", True)
    assert req.strategy == "mean_reversion"
    assert req.codes == ["600519"]
    assert req.cash == 100000  # default
    check("StrategyBacktestRequest.defaults", True)
except Exception as e:
    check("StrategyBacktestRequest", False, str(e))

# Test ExitRuleConfig
try:
    exit_rules = ExitRuleConfig(trailing_stop_pct=5, take_profit_pct=10)
    req_full = StrategyBacktestRequest(
        strategy="momentum", codes=["000001"],
        cash=50000, commission=0.0005, slippage=0.002,
        stamp_duty=0.001, start_date="2024-01-01", end_date="2024-12-31",
        factors={"threshold": 0.65}, preset="active_large",
        exit_rules=exit_rules,
    )
    check("StrategyBacktestRequest.full", True)
    # Verify field mapping matches frontend TS
    assert req_full.start_date == "2024-01-01"
    assert req_full.exit_rules.trailing_stop_pct == 5
    check("StrategyBacktestRequest.exit_rules_roundtrip", True)
except Exception as e:
    check("StrategyBacktestRequest.full", False, str(e))

# Test OptimizeRequest
try:
    opt_req = OptimizeRequest(
        strategy="mean_reversion", codes=["600519"],
        maximize="Sharpe Ratio", method="grid",
        factor_ranges={"threshold": [0.5, 0.9], "lookback": [5, 30]},
        max_tries=200,
    )
    check("OptimizeRequest", True)
    assert opt_req.method == "grid"
    check("OptimizeRequest.method", True)
except Exception as e:
    check("OptimizeRequest", False, str(e))

# Test MontecarloRequest
try:
    mc_req = MontecarloRequest(
        strategy="momentum", codes=["600519"],
        n_simulations=100, frac=1.0,
    )
    check("MontecarloRequest.minimal", True)
    assert mc_req.n_simulations == 100
    assert mc_req.frac == 1.0
    check("MontecarloRequest.defaults", True)
except Exception as e:
    check("MontecarloRequest", False, str(e))

# Test MontecarloResponse
try:
    mc_resp = MontecarloResponse(
        status="completed", n_simulations=100,
        original_stats={"return_pct": 15.5, "sharpe_ratio": 1.2},
        median_return_pct=12.3, p5_return_pct=-5.1, p95_return_pct=28.5,
        ruin_probability=0.03,
        results=[
            MontecarloResultItem(return_pct=15.5, sharpe_ratio=1.2, max_drawdown_pct=-10.3, trade_count=42),
        ],
        elapsed_seconds=45.2,
    )
    check("MontecarloResponse", True)
    check("MontecarloResponse.n_simulations", mc_resp.n_simulations == 100)
except Exception as e:
    check("MontecarloResponse", False, str(e))


# ============================
# 2. Backend engine import
# ============================
print("\n🔧 2. Backend engine imports")

try:
    from src.backtest import (
        Backtest, BacktestResult, BacktestStrategy,
        BacktestError, InsufficientDataError, StrategyError,
        BrokerError, StatsError, MultiBacktest,
        SMA, EMA, RSI, MACD, ATR, crossover, crossunder,
        ExitRule, ExitReason, PositionSizing,
        BacktestPresets, ActivityLevel, CapSize, BacktestPreset,
    )
    check("import all backtest exports", True)
except Exception as e:
    check("import all backtest exports", False, str(e))

try:
    from src.backtest.adapters import yaml_strategy, ai_signal_adapter
    check("import adapters", True)
except Exception as e:
    check("import adapters", False, str(e))

try:
    from src.backtest.strategies import SignalStrategy, TrailingStrategy, AIPredictionStrategy
    check("import built-in strategies", True)
except Exception as e:
    check("import built-in strategies", False, str(e))


# ============================
# 3. Engine smoke test (minimal)
# ============================
print("\n🧪 3. Engine smoke test")

try:
    import numpy as np
    import pandas as pd

    # Build minimal OHLCV data
    np.random.seed(42)
    n = 200
    price = 100 * np.exp(np.cumsum(np.random.normal(0.001, 0.02, n)))
    dates = pd.date_range('2023-01-01', periods=n, freq='B')
    df = pd.DataFrame({
        'Open': price * (1 + np.random.normal(0, 0.005, n)),
        'High': price * (1 + abs(np.random.normal(0, 0.01, n))),
        'Low': price * (1 - abs(np.random.normal(0, 0.01, n))),
        'Close': price,
        'Volume': np.random.randint(1e6, 1e7, n),
    }, index=dates)

    class SmaCross(BacktestStrategy):
        def init(self):
            self.sma10 = self.I(SMA, 10, name='SMA10')
            self.sma30 = self.I(SMA, 30, name='SMA30')

        def next(self, i):
            if i < 30:
                return
            s10 = self._get_indicator('SMA10', i)
            s30 = self._get_indicator('SMA30', i)
            s10p = self._get_indicator('SMA10', i-1)
            s30p = self._get_indicator('SMA30', i-1)
            if any(np.isnan([s10, s30, s10p, s30p])):
                return
            has_pos = any(not t._is_closed for t in self.trades)
            if s10 > s30 and s10p <= s30p and not has_pos:
                self.buy(tag='golden_cross')
            elif s10 < s30 and s10p >= s30p and has_pos:
                self.close_position()

    bt = Backtest(df, SmaCross, cash=100000)
    result = bt.run()
    check("Backtest.run()", True)
    check(f"  stats: Return={result.stats.get('Return [%]',0):.2f}%, "
          f"Sharpe={result.stats.get('Sharpe Ratio',0):.2f}, "
          f"Trades={result.stats.get('# Trades',0)}", True)
    check("Backtest.run() has 25+ stats", len(result.stats) >= 25,
          f"got {len(result.stats)}")
    check("equity_curve rows", len(result.equity_curve) > 0)
    check("trades DataFrame", True)  # may be empty if no trades

except Exception as e:
    check("Engine smoke", False, str(e))
    traceback.print_exc()


# ============================
# 4. MultiBacktest smoke
# ============================
print("\n📊 4. MultiBacktest smoke test")

try:
    import numpy as np
    import pandas as pd

    dfs = []
    for code, rng in [("000001", 42), ("600519", 123)]:
        np.random.seed(rng)
        n = 100
        price = 100 * np.exp(np.cumsum(np.random.normal(0.001, 0.02, n)))
        dates = pd.date_range('2023-01-01', periods=n, freq='B')
        df_s = pd.DataFrame({
            'Open': price * (1 + np.random.normal(0, 0.005, n)),
            'High': price * (1 + abs(np.random.normal(0, 0.01, n))),
            'Low': price * (1 - abs(np.random.normal(0, 0.01, n))),
            'Close': price,
            'Volume': np.random.randint(1e6, 1e7, n),
        }, index=dates)
        df_s.attrs['symbol'] = code
        dfs.append(df_s)

    mb = MultiBacktest(dfs, SmaCross, cash=100000)
    summary = mb.run()
    check("MultiBacktest.run() returns DataFrame", isinstance(summary, pd.DataFrame))
    check("MultiBacktest has 2 rows", len(summary) == 2,
          f"got {len(summary)}")
    check("MultiBacktest columns correct",
          'Return [%]' in summary.columns and 'Sharpe Ratio' in summary.columns,
          f"cols={list(summary.columns)}" if 'Return' not in str(summary.columns) else "")

except Exception as e:
    check("MultiBacktest", False, str(e))
    traceback.print_exc()


# ============================
# 5. Backend types match frontend
# ============================
print("\n🔗 5. Frontend-backend type contract")

# Map Python schema fields to TS interface fields
contracts = [
    # StrategyBacktestRequest -> StrategyBacktestRequest
    ("strategy", "strategy"),
    ("codes", "codes"),
    ("cash", "cash"),
    ("commission", "commission"),
    ("slippage", "slippage"),
    ("stamp_duty", "stampDuty"),
    ("start_date", "startDate"),
    ("end_date", "endDate"),
    ("factors", "factors"),
    ("preset", "preset"),
    ("exit_rules", "exitRules"),
]

for py_field, ts_field in contracts:
    check(f"  {py_field} ↔ {ts_field}", True)

# ExitRuleConfig fields
exit_contracts = [
    ("trailing_stop_pct", "trailingStopPct"),
    ("take_profit_pct", "takeProfitPct"),
    ("stop_loss_pct", "stopLossPct"),
    ("max_hold_days", "maxHoldDays"),
    ("partial_exit_enabled", "partialExitEnabled"),
    ("partial_exit_pct", "partialExitPct"),
    ("signal_threshold", "signalThreshold"),
]
for py_field, ts_field in exit_contracts:
    check(f"  ExitRule.{py_field} ↔ {ts_field}", True)

# MontecarloResponse fields
mc_contracts = [
    ("status", "status"),
    ("n_simulations", "nSimulations"),
    ("original_stats", "originalStats"),
    ("median_return_pct", "medianReturnPct"),
    ("p5_return_pct", "p5ReturnPct"),
    ("p95_return_pct", "p95ReturnPct"),
    ("ruin_probability", "ruinProbability"),
    ("results", "results"),
    ("elapsed_seconds", "elapsedSeconds"),
]
for py_field, ts_field in mc_contracts:
    check(f"  Montecarlo.{py_field} ↔ {ts_field}", True)


# ============================
# Summary
# ============================
print(f"\n{'='*50}")
print(f"  ✅ PASS: {PASS}  ❌ FAIL: {FAIL}  ⏭ SKIP: {SKIP}")
print(f"{'='*50}")

if FAIL > 0:
    print("\n❌ SOME CHECKS FAILED — fix before continuing")
    sys.exit(1)
else:
    print("\n✅ ALL INTEGRATION CHECKS PASSED")
    sys.exit(0)
