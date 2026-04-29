import urllib.request, json, time

def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f'http://localhost:8000{path}', data=data,
        headers={'Content-Type': 'application/json'}, method='POST')
    r = urllib.request.urlopen(req, timeout=120)
    return r.status, json.loads(r.read())

# Test with momentum_reversal on 600519 for 2023-2024 (longer period for more trades)
print('🔧 POST /strategy (momentum_reversal, 600519, 2023-2024)')
t0 = time.time()
st, r = post('/api/v1/backtest/strategy', {
    'strategy': 'momentum_reversal',
    'codes': ['600519'],
    'cash': 100000,
    'start_date': '2023-01-01',
    'end_date': '2024-12-31',
})
print(f'   Status: {st} ({time.time()-t0:.1f}s)')
stats = r.get('stats', {})
print(f'   Stats type: {type(stats).__name__}, keys: {list(stats.keys())[:10]}...')
for k in ['return_pct','sharpe_ratio','trade_count','max_drawdown_pct','win_rate_pct']:
    if isinstance(stats, dict):
        v = stats.get(k)
        print(f'   {k}: {v}')
eq = r.get('equity_curve', [])
trades = r.get('trades', [])
print(f'   Equity: {len(eq)} pts, Trades: {len(trades)}')
if not isinstance(eq, list):
    print(f'   ⚠️ equity_curve is {type(eq).__name__}, not list!')
if eq and isinstance(eq[0], dict):
    print(f'   Equity keys: {sorted(eq[0].keys())}')
if trades and isinstance(trades[0], dict):
    print(f'   Trade keys: {sorted(trades[0].keys())}')
    t = trades[0]
    for fk in ['entryPrice','entry_price','EntryPrice','exitPrice','exit_price','ExitPrice','returnPct','return_pct','ReturnPct','exitReason','exit_reason','ExitReason']:
        if fk in t:
            print(f'   Trade.{fk} = {t[fk]}')
    print(f'   EntryPrice: {t.get("EntryPrice") or t.get("entry_price") or t.get("entryPrice", "MISSING")}')
    print(f'   ReturnPct: {t.get("ReturnPct") or t.get("ReturnPct") or t.get("return_pct") or t.get("returnPct", "MISSING")}')
