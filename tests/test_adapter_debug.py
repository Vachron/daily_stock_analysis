import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
import pandas as pd, numpy as np
from src.backtest.engine import Backtest
from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
from datetime import timedelta

repo = KlineRepo()

# Get data
df = repo.get_history('000001')
df = df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'})
df['Date'] = pd.to_datetime(df['date'].apply(lambda d: ORIGIN_DATE + timedelta(days=int(d))))
df = df.set_index('Date')
df = df['2023-01-01':'2024-12-31']
print(f'Data: {len(df)} bars, Close range: {df.Close.min():.2f}-{df.Close.max():.2f}')

# Create strategy class via adapter
cls = yaml_to_strategy_class('bull_trend')
print(f'Class: {cls.__name__}')

# Inject debug into the strategy
original_init = cls.init
original_next = cls.next

bt = Backtest(df, cls, cash=100000)

# Quick check: does the engine's strategy have the MAs registered?
print('\n=== After init: checking MAs ===')
strat = next(iter(vars(bt).values()))  # Can't easily access the strategy from outside
# Let's run with a small debug patch
class DebugStrategy(cls):
    def init(self):
        super().init()
        print(f'  _ma_values keys: {list(self._ma_values.keys())}')
        for k, v in self._ma_values.items():
            arr = v
            valid = np.sum(~np.isnan(arr))
            print(f'    {k}: {len(arr)} bars, {valid} valid, last={arr[-1]:.2f}')
    
    def next(self, i):
        super().next(i)
        if i % 100 == 0:
            has_pos = any(not t._is_closed for t in self.trades)
            print(f'  next({i}): has_position={has_pos}, trades={len(self.trades)}')

bt2 = Backtest(df, DebugStrategy, cash=100000)
result = bt2.run()
n_trades = int(result.stats.get('# Trades', 0))
print(f'\n  Result: {n_trades} trades, Return={result.stats.get("Return [%]", 0):.2f}%')
