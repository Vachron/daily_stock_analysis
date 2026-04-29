import urllib.request, json, time
data = json.dumps({
    'strategy':'bollinger_reversion',
    'codes':['600519'],
    'cash':100000,
    'start_date':'2024-01-01',
    'end_date':'2024-12-31'
}).encode()
req = urllib.request.Request('http://localhost:8000/api/v1/backtest/strategy',
    data=data, headers={'Content-Type': 'application/json'}, method='POST')
try:
    t0 = time.time()
    r = urllib.request.urlopen(req, timeout=120)
    result = json.loads(r.read())
    elapsed = time.time() - t0
    print(f'✅ Status {r.status} in {elapsed:.1f}s')
    stats = result.get('stats', {})
    for k in ['Return [%]','Sharpe Ratio','# Trades','Max Drawdown [%]','Win Rate [%]']:
        print(f'   {k}: {stats.get(k, "?")}')
    eq = result.get('equity_curve', [])
    trades = result.get('trades', [])
    print(f'   Equity points: {len(eq)}, Trades: {len(trades)}')
    if eq:
        e0 = eq[0]
        print(f'   Equity sample keys: {sorted(e0.keys()) if isinstance(e0, dict) else type(e0)}')
    if trades:
        t0 = trades[0]
        print(f'   Trade sample keys: {sorted(t0.keys()) if isinstance(t0, dict) else type(t0)}')
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f'❌ HTTP {e.code}: {body[:500]}')
