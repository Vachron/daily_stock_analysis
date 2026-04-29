"""追踪 broker 在 2026 数据上的确切行为"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pandas as pd, numpy as np
from src.backtest.engine import Backtest
from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
from src.backtest.lib import SMA
from src.backtest.strategy import BacktestStrategy
from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
from datetime import timedelta

repo = KlineRepo()
df = repo.get_history('000001')
df = df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'})
df['Date'] = pd.to_datetime(df['date'].apply(lambda d: ORIGIN_DATE + timedelta(days=int(d))))
df = df.set_index('Date')
df = df['2026-01-01':'2026-04-24']

# Manual trace strategy
class TraceStrategy(BacktestStrategy):
    def init(self):
        self.sma5 = self.I(SMA, 5, name='SMA5')
        self.sma20 = self.I(SMA, 20, name='SMA20')
        self._debug = []
    
    def next(self, i):
        if i < 20: return
        s5 = self.sma5[i]; s20 = self.sma20[i]
        s5p = self.sma5[i-1]; s20p = self.sma20[i-1]
        if np.isnan([s5,s20,s5p,s20p]).any(): return
        has_pos = any(not t._is_closed for t in self.trades)
        
        if s5 > s20 and s5p <= s20p and not has_pos:
            print(f"  BUY SIGNAL @ {i}: close={self.data.Close[i]:.2f} sma5={s5:.2f} sma20={s20:.2f}")
            print(f"    Before buy: cash={self._broker._cash:.1f}, trades={len(self._broker._trades)}, orders={len(self._broker._orders)}")
            self.buy(size=0.25, tag='trace')
            print(f"    After buy: cash={self._broker._cash:.1f}, trades={len(self._broker._trades)}, orders={len(self._broker._orders)}")
            has_pos2 = any(not t._is_closed for t in self.trades)
            print(f"    has_position after buy: {has_pos2}")

bt = Backtest(df, TraceStrategy, cash=100000)
result = bt.run()
all_trades = result.trades
print(f"\nResult: {len(all_trades)} trades, Return={float(result.stats.get('Return [%]',0)):.2f}%")
print(f"Equity first: {result.equity_curve.iloc[0].to_dict()}")
print(f"Equity last: {result.equity_curve.iloc[-1].to_dict()}")
print(f"\nAll closed_trades: {result._meta}")

# Also check broker directly
print(f"\nDirect broker state:")
print(f"  _cash = {result.stats}")
