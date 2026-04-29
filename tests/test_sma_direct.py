import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd, numpy as np
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
print(f'Data: {len(df)} bars, Close: {df.Close.iloc[0]:.2f}-{df.Close.iloc[-1]:.2f}')

# Manual test: SMA5 vs SMA20 crossover on 000001
from src.backtest.lib import SMA
close = df.Close.values
sma5 = SMA(close, 5)
sma20 = SMA(close, 20)

cross_up = 0
cross_down = 0
for i in range(1, len(close)):
    if np.isnan(sma5[i]) or np.isnan(sma20[i]) or np.isnan(sma5[i-1]) or np.isnan(sma20[i-1]):
        continue
    if sma5[i] > sma20[i] and sma5[i-1] <= sma20[i-1]:
        cross_up += 1
    if sma5[i] < sma20[i] and sma5[i-1] >= sma20[i-1]:
        cross_down += 1

print(f'SMA5 vs SMA20 crossover: UP={cross_up}, DOWN={cross_down}')
print(f'Sample: sma5[0:5]={sma5[5:10]}, sma20[0:5]={sma20[20:25]}')

# Now test with a simple strategy to verify the engine works
class SimpleSmaCross(BacktestStrategy):
    def init(self):
        self.sma5 = self.I(SMA, self.data.Close, 5, name='SMA5')
        self.sma20 = self.I(SMA, self.data.Close, 20, name='SMA20')
    def next(self, i):
        if i < 20:
            return
        s5 = self.sma5[i]
        s20 = self.sma20[i]
        s5p = self.sma5[i-1]
        s20p = self.sma20[i-1]
        if np.isnan([s5, s20, s5p, s20p]).any():
            return
        has_pos = any(not t._is_closed for t in self.trades)
        if s5 > s20 and s5p <= s20p and not has_pos:
            self.buy(tag='golden_cross')
        elif s5 < s20 and s5p >= s20p and has_pos:
            self.close_position()

bt = Backtest(df, SimpleSmaCross, cash=100000)
result = bt.run()
print(f'\nSimpleSmaCross: {int(result.stats.get("# Trades", 0))} trades, Return={float(result.stats.get("Return [%]", 0)):.2f}%')
print(f'Sharpe={float(result.stats.get("Sharpe Ratio", 0)):.2f}, WR={float(result.stats.get("Win Rate [%]", 0)):.1f}%')
