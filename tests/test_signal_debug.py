import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pandas as pd, numpy as np
from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
from src.backtest.engine import Backtest
from src.backtest.exit_rules import ExitRule
from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
from datetime import timedelta

repo = KlineRepo()
df = repo.get_history('000001')
df = df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'})
df['Date'] = pd.to_datetime(df['date'].apply(lambda d: ORIGIN_DATE + timedelta(days=int(d))))
df = df.set_index('Date')
df = df['2023-01-01':'2024-12-31']

# Test 1: no exit rule
print("Test 1: NO exit rule")
cls = yaml_to_strategy_class('bull_trend')
bt = Backtest(df, cls, cash=100000, exit_rule=None)
result = bt.run()
print(f"  trades: {int(result.stats.get('# Trades',0))}, return: {float(result.stats.get('Return [%]',0)):.2f}%")

# Test 2: with exit rule (take_profit=10%)
print("\nTest 2: WITH exit rule (take_profit=10%)")
exit_rule = ExitRule(take_profit_pct=10.0)
bt2 = Backtest(df, cls, cash=100000, exit_rule=exit_rule)
result2 = bt2.run()
print(f"  trades: {int(result2.stats.get('# Trades',0))}, return: {float(result2.stats.get('Return [%]',0)):.2f}%")

# Test 3: verify signal generation
print("\nTest 3: Signal generation check")
from src.backtest.lib import SMA
close = df.Close.values
sma5 = SMA(close, 5)
sma20 = SMA(close, 20)
cross_ups = []
for i in range(20, len(close)):
    if np.isnan(sma5[i]) or np.isnan(sma20[i]): continue
    if sma5[i] > sma20[i] and sma5[i-1] <= sma20[i-1]:
        cross_ups.append((i, df.index[i], close[i], sma5[i], sma20[i]))
print(f"  SMA5×SMA20 crossover UP signals: {len(cross_ups)}")
for bar, dt, price, s5, s20 in cross_ups[:3]:
    print(f"    bar={bar} date={dt} close={price:.2f} sma5={s5:.2f} sma20={s20:.2f}")
