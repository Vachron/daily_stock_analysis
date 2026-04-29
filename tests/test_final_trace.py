"""最终检查：all_trades + _build_trades_df"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pandas as pd, numpy as np
from src.backtest.engine import Backtest
from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
from src.backtest.strategy import BacktestStrategy
from src.backtest.lib import SMA
from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
from datetime import timedelta

repo = KlineRepo()
df = repo.get_history('000001')
df = df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'})
df['Date'] = pd.to_datetime(df['date'].apply(lambda d: ORIGIN_DATE + timedelta(days=int(d))))
df = df.set_index('Date')
df = df['2026-01-01':'2026-04-24']

# Monkey-patch engine.run to print all_trades after loop
from src.backtest import engine as eng_mod
orig_run = eng_mod.Backtest.run

def traced_run(self, **kwargs):
    # Run original
    result = orig_run(self, **kwargs)
    
    # Check trades_df
    print(f"\n[ENGINE TRACE]")
    print(f"  result.trades: {type(result.trades).__name__}, empty={result.trades.empty if isinstance(result.trades, pd.DataFrame) else True}")
    if not result.trades.empty:
        print(f"  Trades cols: {list(result.trades.columns)}")
        print(f"  Trades count: {len(result.trades)}")
        print(f"  First trade: {dict(result.trades.iloc[0])}")
    else:
        print(f"  NO TRADES in result")
    
    # Check to_json
    j = result.to_json()
    print(f"  to_json trades: {len(j.get('trades', []))}")
    print(f"  to_json equity: {len(j.get('equity_curve', []))}")
    return result

eng_mod.Backtest.run = traced_run

# Now test both TraceStrategy and adapter
print("=" * 60)
print("1. TraceStrategy (direct)")
print("=" * 60)

class DirectStrategy(BacktestStrategy):
    def init(self):
        self.sma5 = self.I(SMA, 5, name='SMA5')
        self.sma20 = self.I(SMA, 20, name='SMA20')
    def next(self, i):
        if i < 20: return
        s5 = self.sma5[i]; s20 = self.sma20[i]
        s5p = self.sma5[i-1]; s20p = self.sma20[i-1]
        if np.isnan([s5,s20,s5p,s20p]).any(): return
        has_pos = any(not t._is_closed for t in self.trades)
        if s5 > s20 and s5p <= s20p and not has_pos:
            self.buy(size=0.25, tag='direct')

bt1 = Backtest(df, DirectStrategy, cash=100000)
r1 = bt1.run()

print("\n" + "=" * 60)
print("2. YAML adapter (bull_trend)")
print("=" * 60)

cls2 = yaml_to_strategy_class('bull_trend')
bt2 = Backtest(df, cls2, cash=100000)
r2 = bt2.run()
