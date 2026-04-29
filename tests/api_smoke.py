import urllib.request, json, sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

BASE = 'http://localhost:8000'

def get(path):
    r = urllib.request.urlopen(f'{BASE}{path}', timeout=10)
    return r.status, json.loads(r.read())

def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f'{BASE}{path}', data=data,
        headers={'Content-Type': 'application/json'}, method='POST')
    r = urllib.request.urlopen(req, timeout=120)
    return r.status, json.loads(r.read())

ok = fail = 0
def check(name, condition, detail=''):
    global ok, fail
    if condition:
        ok += 1; print(f'  ✅ {name}')
    else:
        fail += 1; print(f'  ❌ {name} — {detail}')

# ===== 1. Strategy list =====
print('\n📋 1. GET /api/v1/backtest/strategies')
try:
    st, data = get('/api/v1/backtest/strategies')
    check('status 200', st == 200, str(st))
    total = data.get('total', 0)
    items = data.get('items', data if isinstance(data, list) else [])
    check('has strategies', total > 0 or len(items) > 0, f'total={total}')
    if isinstance(items, list) and items:
        s = items[0]
        print(f'     First: {s.get("name","?")} ({s.get("display_name","")}) [{s.get("category","")}] {len(s.get("factors",[]))} factors')
        check('strategy has name', bool(s.get('name')))
        check('strategy has factors', len(s.get('factors', [])) > 0)
except Exception as e:
    check('strategy list', False, str(e))

# ===== 2. Strategy backtest run =====
print('\n🔧 2. POST /api/v1/backtest/strategy (momentum on 600519)')
try:
    t0 = time.time()
    st, result = post('/api/v1/backtest/strategy', {
        'strategy': 'momentum',
        'codes': ['600519'],
        'cash': 100000,
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
    })
    elapsed = time.time() - t0
    check('status 200', st == 200, str(st))
    check('strategy_name', result.get('strategy_name') == '动量策略' or 'momentum' in str(result.get('strategy_name','')), str(result.get('strategy_name')))
    check('has stats', 'stats' in result, f'keys={list(result.keys())[:10]}')
    stats = result.get('stats', {})
    check('stats has Return', 'Return [%]' in stats or 'ReturnPct' in stats, f'keys={list(stats.keys())[:10]}')
    print(f'     Return: {stats.get("Return [%]", stats.get("ReturnPct", "?"))}%')
    print(f'     Sharpe: {stats.get("Sharpe Ratio", "?")}')
    print(f'     Trades: {stats.get("# Trades", "?")}')

    trades = result.get('trades', [])
    eq = result.get('equity_curve', [])
    print(f'     Equity points: {len(eq)}, Trades: {len(trades)}')
    check('has equity_curve', len(eq) > 0)
    check('has trades or 0 trades is valid', isinstance(trades, list))
    check(f'elapsed: {elapsed:.1f}s', True)

    if trades:
        t = trades[0]
        print(f'     Trade fields: {sorted(t.keys())[:10]}')
        check('trade has entryPrice', 'entryPrice' in t or 'EntryPrice' in t or 'entry_price' in t, f'{sorted(t.keys())[:6]}')

    # ===== 3. Check equity curve format =====
    if eq:
        e0 = eq[0]
        print(f'     Equity fields: {sorted(e0.keys()) if isinstance(e0, dict) else type(e0).__name__}')
        check('equity has Equity or equity', isinstance(e0, dict) and ('Equity' in e0 or 'equity' in e0), str(e0.keys() if isinstance(e0, dict) else e0))
        check('equity has DrawdownPct or drawdown', isinstance(e0, dict) and ('DrawdownPct' in e0 or 'drawdown' in e0), str(list(e0.keys())[:6] if isinstance(e0, dict) else ''))

except Exception as e:
    import traceback
    check('strategy run', False, str(e))
    traceback.print_exc()

# ===== 4. Run with exit rules =====
print('\n📐 4. POST /strategy with exit rules')
try:
    st, result2 = post('/api/v1/backtest/strategy', {
        'strategy': 'mean_reversion',
        'codes': ['000001'],
        'cash': 50000,
        'start_date': '2024-06-01',
        'end_date': '2024-12-31',
        'exit_rules': {
            'trailing_stop_pct': 5.0,
            'take_profit_pct': 10.0,
            'stop_loss_pct': 8.0,
            'max_hold_days': 30,
        },
    })
    check('status 200', st == 200, str(st))
    stats2 = result2.get('stats', {})
    print(f'     Return: {stats2.get("Return [%]", "?")}%, Sharpe: {stats2.get("Sharpe Ratio", "?")}, Trades: {stats2.get("# Trades", "?")}')
    check('has strategy_name', bool(result2.get('strategy_name')))
except Exception as e:
    check('exit rules run', False, str(e))

# ===== 5. Presets list =====
print('\n🎯 5. GET /api/v1/backtest/presets')
try:
    st, data = get('/api/v1/backtest/presets')
    check('status 200', st == 200, str(st))
    items = data.get('items', data if isinstance(data, list) else [])
    check('has presets', len(items) > 0, f'count={len(items)}')
    print(f'     Presets: {len(items)} available')
except Exception as e:
    check('presets', False, str(e))

# ===== Summary =====
print(f'\n{"="*50}')
print(f'  ✅ {ok} passed  ❌ {fail} failed')
print(f'{"="*50}')
sys.exit(1 if fail > 0 else 0)
