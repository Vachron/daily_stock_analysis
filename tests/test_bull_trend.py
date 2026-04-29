import urllib.request, json, time

print("=" * 60)
print("🔍 Debugging bull_trend 0 trades issue")
print("=" * 60)

def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f'http://localhost:8000{path}', data=data,
        headers={'Content-Type': 'application/json'}, method='POST')
    r = urllib.request.urlopen(req, timeout=120)
    return r.status, json.loads(r.read())

# Test 1: Basic bull_trend without exit rules
print("\n📋 Test 1: bull_trend, 000001, basic params (no exit rules)")
t0 = time.time()
st, r = post('/api/v1/backtest/strategy', {
    'strategy': 'bull_trend',
    'codes': ['000001'],
    'cash': 100000,
    'start_date': '2023-01-01',
    'end_date': '2024-12-31',
})
print(f"  Status: {st} ({time.time()-t0:.1f}s)")
stats = r.get('stats', {})
print(f"  Stats keys: {sorted(stats.keys())}")
for k in ['return_pct','sharpe_ratio','trade_count','win_rate_pct','max_drawdown_pct']:
    print(f"  {k}: {stats.get(k)}")
trades = r.get('trades', [])
eq = r.get('equity_curve', [])
print(f"  Equity points: {len(eq)}, Trades: {len(trades)}")

# Test 2: With user's exact params (take profit 10%)
print("\n📋 Test 2: bull_trend, 000001, take_profit=10%")
t0 = time.time()
st, r = post('/api/v1/backtest/strategy', {
    'strategy': 'bull_trend',
    'codes': ['000001'],
    'cash': 100000,
    'start_date': '2023-01-01',
    'end_date': '2024-12-31',
    'exit_rules': {
        'take_profit_pct': 10,
    },
})
print(f"  Status: {st} ({time.time()-t0:.1f}s)")
stats = r.get('stats', {})
print(f"  trade_count: {stats.get('trade_count')}")
print(f"  return_pct: {stats.get('return_pct')}")
trades = r.get('trades', [])
eq = r.get('equity_curve', [])
print(f"  Equity points: {len(eq)}, Trades: {len(trades)}")

# Test 3: With wider date range + all exit rules
print("\n📋 Test 3: bull_trend, 000001, full exit rules, 2020-2024")
t0 = time.time()
st, r = post('/api/v1/backtest/strategy', {
    'strategy': 'bull_trend',
    'codes': ['000001'],
    'cash': 100000,
    'start_date': '2020-01-01',
    'end_date': '2024-12-31',
    'exit_rules': {
        'trailing_stop_pct': 5,
        'take_profit_pct': 10,
        'stop_loss_pct': 8,
        'max_hold_days': 30,
    },
})
print(f"  Status: {st} ({time.time()-t0:.1f}s)")
stats = r.get('stats', {})
print(f"  trade_count: {stats.get('trade_count')}")
print(f"  return_pct: {stats.get('return_pct')}")
trades = r.get('trades', [])
print(f"  Equity points: {len(eq)}, Trades: {len(trades)}")

# Test 4: Try with a different stock
print("\n📋 Test 4: bull_trend, 600519, full exit, 2023-2024")
t0 = time.time()
st, r = post('/api/v1/backtest/strategy', {
    'strategy': 'bull_trend',
    'codes': ['600519'],
    'cash': 100000,
    'start_date': '2023-01-01',
    'end_date': '2024-12-31',
    'exit_rules': {
        'trailing_stop_pct': 5,
        'take_profit_pct': 10,
        'stop_loss_pct': 8,
        'max_hold_days': 30,
    },
})
print(f"  Status: {st} ({time.time()-t0:.1f}s)")
stats = r.get('stats', {})
print(f"  trade_count: {stats.get('trade_count')}")
print(f"  return_pct: {stats.get('return_pct')}")
trades = r.get('trades', [])
print(f"  Trades: {len(trades)}")
if trades:
    t = trades[0]
    print(f"  First trade keys: {sorted(t.keys())}")
    print(f"  entryPrice={t.get('entryPrice')} exitPrice={t.get('exitPrice')} returnPct={t.get('returnPct')} exitReason={t.get('exitReason')}")
