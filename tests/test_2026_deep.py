"""深挖 2026年 000001 0 trades 但 return=-57.72% 的根因"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import urllib.request, json

BASE = 'http://localhost:8000'

def post(body):
    d = json.dumps(body).encode()
    req = urllib.request.Request(f'{BASE}/api/v1/backtest/strategy',
        data=d, headers={'Content-Type': 'application/json'}, method='POST')
    r = urllib.request.urlopen(req, timeout=120)
    return json.loads(r.read())

r = post({
    'strategy': 'bull_trend',
    'codes': ['000001'],
    'cash': 100000,
    'start_date': '2026-01-01',
    'end_date': '2026-04-24',
})

eq = r.get('equity_curve', [])
print(f"Equity curve: {len(eq)} points")
for i, e in enumerate(eq[:5]):
    print(f"  [{i}] {e}")
if len(eq) > 5:
    print(f"  ...")
    for i in range(len(eq)-3, len(eq)):
        print(f"  [{i}] {eq[i]}")

print(f"\nEquity values:")
values = [e.get('Equity', e if isinstance(e, (int,float)) else 0) for e in eq]
print(f"  Min: {min(values):.2f}, Max: {max(values):.2f}")

stats = r.get('stats', {})
print(f"\nStats:")
for k in ['equity_final','equity_peak','return_pct','max_drawdown_pct','trade_count']:
    print(f"  {k}: {stats.get(k)}")

trades = r.get('trades', [])
print(f"\nTrades: {len(trades)}")

# Also check via direct engine
print(f"\n{'='*60}")
print("Direct engine debug")
print(f"{'='*60}")
import pandas as pd, numpy as np
from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
from src.backtest.engine import Backtest
from src.backtest.lib import SMA
from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
from datetime import timedelta

repo = KlineRepo()
df = repo.get_history('000001')
df = df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'})
df['Date'] = pd.to_datetime(df['date'].apply(lambda d: ORIGIN_DATE + timedelta(days=int(d))))
df = df.set_index('Date')
df = df['2026-01-01':'2026-04-24']

close = df.Close.values
sma5 = SMA(close, 5)
sma20 = SMA(close, 20)

print(f"Bars: {len(df)}")
print(f"Close: {close[0]:.2f}→{close[-1]:.2f}")
print(f"SMA5 last 5: {[round(x,4) for x in sma5[-5:]]}")
print(f"SMA20 last 5: {[round(x,4) for x in sma20[-5:]]}")

# Count crossovers
cross_ups = cross_downs = 0
for i in range(20, len(close)):
    if np.isnan(sma5[i]) or np.isnan(sma20[i]): continue
    if sma5[i] > sma20[i] and sma5[i-1] <= sma20[i-1]:
        cross_ups += 1
        print(f"  CROSS UP @ bar {i}: {df.index[i]} close={close[i]:.2f} sma5={sma5[i]:.2f} sma20={sma20[i]:.2f}")
    if sma5[i] < sma20[i] and sma5[i-1] >= sma20[i-1]:
        cross_downs += 1

print(f"Crossovers: UP={cross_ups}, DOWN={cross_downs}")

# Run the engine directly  
cls = yaml_to_strategy_class('bull_trend')
bt = Backtest(df, cls, cash=100000)
result = bt.run()
print(f"\nDirect engine: trades={int(result.stats.get('# Trades',0))}, "
      f"Return={float(result.stats.get('Return [%]',0)):.2f}%")
print(f"Equity points: {result.equity_curve}")
print(f"Equity sample (first): {result.equity_curve.iloc[0].to_dict() if len(result.equity_curve)>0 else 'EMPTY'}")
print(f"Equity sample (last): {result.equity_curve.iloc[-1].to_dict() if len(result.equity_curve)>0 else 'EMPTY'}")
