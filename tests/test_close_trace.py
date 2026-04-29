"""完整追踪 adapter trade 在 loop 后的命运"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pandas as pd, numpy as np
from src.backtest import engine as eng_mod
from src.backtest.engine import Backtest
from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
from src.backtest.broker import _Broker
from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
from datetime import timedelta

repo = KlineRepo()
df = repo.get_history('000001')
df = df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'})
df['Date'] = pd.to_datetime(df['date'].apply(lambda d: ORIGIN_DATE + timedelta(days=int(d))))
df = df.set_index('Date')
df = df['2026-01-01':'2026-04-24']

# Patch __close_trade
orig_close_trade = _Broker._close_trade
def traced_close_trade(self, trade, price, bar, exit_reason=None, portion=1.0):
    print(f"[CLOSE_TRADE @ bar {bar}] trade tag={trade.tag}, reason={exit_reason}, "
          f"is_closed_before={trade._is_closed}, portion={portion}")
    result = orig_close_trade(self, trade, price, bar, exit_reason, portion)
    print(f"  After: _closed_trades={len(self._closed_trades)}, _trades={len(self._trades)}, "
          f"trade._is_closed={trade._is_closed}")
    return result

_Broker._close_trade = traced_close_trade

# Patch run to show all_trades
orig_run = eng_mod.Backtest.run
def traced_run(self, **kwargs):
    # Get the actual run result via the original
    # We need to instrument the internal loop
    import types
    original_run_code = orig_run.__code__
    
    # Just run normally and check result
    result = orig_run(self, **kwargs)
    
    # Check what all_trades would be (we can't access broker directly, so check result)
    print(f"\n[FINAL] trades df rows: {len(result.trades)}")
    print(f"[FINAL] to_json trades: {len(result.to_json().get('trades', []))}")
    print(f"[FINAL] equity rows: {len(result.equity_curve)}")
    print(f"[FINAL] equity last: {dict(result.equity_curve.iloc[-1])}")
    return result

eng_mod.Backtest.run = traced_run

cls = yaml_to_strategy_class('bull_trend')
bt = Backtest(df, cls, cash=100000)
r = bt.run()
