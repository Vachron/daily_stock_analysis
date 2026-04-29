"""验证 3个策略产生不同结果 + trade reporting 已修复"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pandas as pd, numpy as np
from src.backtest.engine import Backtest
from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
from datetime import timedelta

repo = KlineRepo()
df = repo.get_history('000001')
df = df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'})
df['Date'] = pd.to_datetime(df['date'].apply(lambda d: ORIGIN_DATE + timedelta(days=int(d))))
df = df.set_index('Date')
df = df['2026-01-01':'2026-04-24']

strategies = ['bull_trend', 'box_oscillation', 'bottom_volume']
results = {}

for sname in strategies:
    cls = yaml_to_strategy_class(sname)
    bt = Backtest(df, cls, cash=100000)
    r = bt.run()
    n = int(r.stats.get('# Trades', 0))
    ret = float(r.stats.get('Return [%]', 0))
    sharpe = float(r.stats.get('Sharpe Ratio', 0))
    results[sname] = (n, ret, sharpe)
    print(f"{sname}: {n} trades, Return={ret:.2f}%, Sharpe={sharpe:.2f}")

# Check uniqueness
keys = ['trades','return','sharpe']
all_same = True
for k, idx in zip(keys, [0,1,2]):
    vals = [results[s][idx] for s in strategies]
    if len(set(vals)) > 1:
        print(f"  ✅ {k}: 不同 → {dict(zip(strategies, vals))}")
        all_same = False
    else:
        print(f"  ❌ {k}: 相同 → {vals[0]}")

if not all_same:
    print("\n✅ 策略结果已区分！")
else:
    print("\n❌ 所有策略结果仍相同")
