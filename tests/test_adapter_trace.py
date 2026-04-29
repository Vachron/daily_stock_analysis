"""诊断 YAML adapter 是否真正产生 buy 信号"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pandas as pd, numpy as np
from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
from src.backtest.engine import Backtest
from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
from datetime import timedelta

repo = KlineRepo()
df = repo.get_history('000001')
df = df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'})
df['Date'] = pd.to_datetime(df['date'].apply(lambda d: ORIGIN_DATE + timedelta(days=int(d))))
df = df.set_index('Date')
df = df['2026-01-01':'2026-04-24']

cls = yaml_to_strategy_class('bull_trend')

# Monkey-patch to trace
orig_init = cls.init
orig_next = cls.next

def debug_init(self):
    orig_init(self)
    print(f"[INIT] _indicators: {[(ind.name, type(ind).__name__) for ind in self._indicators]}")
    print(f"[INIT] has short_window: {hasattr(self, 'short_window')}, mid_window: {hasattr(self, 'mid_window')}")

def debug_next(self, i):
    if i == 26:  # CROSS UP bar
        print(f"\n[DEBUG bar {i}]")
        for ind in self._indicators:
            name = ind.name
            val = self._get_indicator(name, i)
            val1 = self._get_indicator(name, i-1)
            print(f"  {name}[{i}]={val:.4f}, [{i-1}]={val1:.4f}")
    
    orig_next(self, i)
    
    if i == 26:
        has_pos = any(not t._is_closed for t in self.trades)
        print(f"  After next({i}): has_position={has_pos}, trades={len(list(self.trades))}")
        print(f"  Orders in broker: {len(self._broker._orders)}")
        for o in self._broker._orders:
            print(f"    Order: type={o._type}, size={o.size}, status={'active' if not o._cancelled else 'cancelled'}")

cls.init = debug_init
cls.next = debug_next

bt = Backtest(df, cls, cash=100000)
result = bt.run()
print(f"\nFinal: trades={int(result.stats.get('# Trades',0))}, Return={float(result.stats.get('Return [%]',0)):.2f}%")
print(f"Equity last: {result.equity_curve.iloc[-1].to_dict()}")
