"""精确复现用户场景：3个策略 + 000001 + 2026-01-01~2026-04-24 + take_profit=10%"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import urllib.request, json, time

BASE = 'http://localhost:8000'

def post(body):
    d = json.dumps(body).encode()
    req = urllib.request.Request(f'{BASE}/api/v1/backtest/strategy',
        data=d, headers={'Content-Type': 'application/json'}, method='POST')
    r = urllib.request.urlopen(req, timeout=120)
    return json.loads(r.read())

strategies = ['bull_trend', 'box_oscillation', 'bottom_volume']
results = {}

for sname in strategies:
    print(f"\n{'='*60}")
    print(f"策略: {sname}, 000001, 2026-01-01~2026-04-24, take_profit=10%")
    print(f"{'='*60}")
    t0 = time.time()
    try:
        r = post({
            'strategy': sname,
            'codes': ['000001'],
            'cash': 100000,
            'start_date': '2026-01-01',
            'end_date': '2026-04-24',
            'exit_rules': {'take_profit_pct': 10},
        })
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  ❌ HTTP {e.code}: {body[:300]}")
        continue

    stats = r.get('stats', {})
    trades = r.get('trades', [])
    eq = r.get('equity_curve', [])

    key = ['trade_count','return_pct','sharpe_ratio','max_drawdown_pct','win_rate_pct']
    vals = {k: stats.get(k) for k in key}
    print(f"  Stats: {vals}")
    print(f"  Trades: {len(trades)}, Equity points: {len(eq)}")
    if trades:
        for i, t in enumerate(trades[:3]):
            print(f"  Trade[{i}]: entry={t.get('entryPrice','?')}, exit={t.get('exitPrice','?')}, "
                  f"ret={t.get('returnPct','?')}%, reason={t.get('exitReason','?')}, "
                  f"entryTime={t.get('entryTime','?')}, exitTime={t.get('exitTime','?')}")
    results[sname] = vals

# Diff check
print(f"\n{'='*60}")
print("一致性检查：3个策略的结果是否相同？")
print(f"{'='*60}")
keys = ['trade_count','return_pct','sharpe_ratio','max_drawdown_pct']
all_same = True
for k in keys:
    vals = [results.get(s, {}).get(k) for s in strategies]
    unique = set(str(v) for v in vals)
    if len(unique) > 1:
        print(f"  ❌ {k}: 不同 → {dict(zip(strategies, vals))}")
        all_same = False
    else:
        print(f"  ⚠️ {k}: 全部相同 → {vals[0]}")
if all_same:
    print("\n  🚨 所有策略的结果完全相同 — 这是Bug！")

# Also check data directly
print(f"\n{'='*60}")
print("数据完整性检查：2026年在K线数据中")
print(f"{'='*60}")
import pandas as pd, numpy as np
from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
from datetime import timedelta

repo = KlineRepo()
df = repo.get_history('000001')
if df is not None:
    df['Date'] = pd.to_datetime(df['date'].apply(lambda d: ORIGIN_DATE + timedelta(days=int(d))))
    df = df.set_index('Date')
    df_2026 = df['2026-01-01':'2026-04-24']
    print(f"  2026 bars: {len(df_2026)}, range: {df_2026.index[0]} ~ {df_2026.index[-1]}")
    if len(df_2026) > 0:
        print(f"  Close: {df_2026['close'].iloc[0]:.2f} ~ {df_2026['close'].iloc[-1]:.2f}")
        print(f"  High range: {df_2026['high'].min():.2f} ~ {df_2026['high'].max():.2f}")
