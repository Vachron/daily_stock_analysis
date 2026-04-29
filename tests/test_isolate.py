import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import numpy as np, pandas as pd
from src.backtest.engine import Backtest
from src.backtest.strategy import BacktestStrategy
from src.backtest.lib import SMA
from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
from datetime import timedelta

repo = KlineRepo()
df = repo.get_history('000001')
df = df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'})
df['Date'] = pd.to_datetime(df['date'].apply(lambda d: ORIGIN_DATE + timedelta(days=int(d))))
df = df.set_index('Date')
df = df['2023-01-01':'2024-12-31']

class SimpleSmaCross(BacktestStrategy):
    def init(self):
        self.sma5 = self.I(SMA, 5, name='SMA5')
        self.sma20 = self.I(SMA, 20, name='SMA20')
        print(f'init: sma5 type={type(self.sma5)}, len={len(self.sma5)}')
        print(f'init: sma20 type={type(self.sma20)}, len={len(self.sma20)}')
    def next(self, i):
        if i == 0:
            print(f'next(0): sma5 type={type(self.sma5)}, len={len(self.sma5)}')
            print(f'next(0): sma20 type={type(self.sma20)}, len={len(self.sma20)}')
        if i == 21:
            print(f'next(21): sma5[20]={self.sma5[20]:.2f}, sma20[20]={self.sma20[20]:.2f}')
        if i < 20: return
        s5 = self.sma5[i]; s20 = self.sma20[i]
        s5p = self.sma5[i-1]; s20p = self.sma20[i-1]
        if np.isnan([s5,s20,s5p,s20p]).any(): return
        has_pos = any(not t._is_closed for t in self.trades)
        if s5 > s20 and s5p <= s20p and not has_pos:
            self.buy(tag='gc')

bt = Backtest(df, SimpleSmaCross, cash=100000)
result = bt.run()
print(f'\nTrades: {int(result.stats.get("# Trades",0))}')
print(f'Return: {float(result.stats.get("Return [%]",0)):.2f}%')
