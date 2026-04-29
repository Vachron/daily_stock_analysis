import urllib.request, json, time

def post(body):
    d = json.dumps(body).encode()
    req = urllib.request.Request('http://localhost:8000/api/v1/backtest/strategy',
        data=d, headers={'Content-Type': 'application/json'}, method='POST')
    r = urllib.request.urlopen(req, timeout=120)
    return json.loads(r.read())

# EXACT user scenario
print("=" * 60)
print("用户场景: bull_trend, 000001, take_profit=10%, 默认参数")
print("=" * 60)

r = post({
    'strategy': 'bull_trend',
    'codes': ['000001'],
    'cash': 100000,
    'start_date': '2023-01-01',
    'end_date': '2024-12-31',
    'exit_rules': {
        'take_profit_pct': 10,
    },
})

stats = r.get('stats', {})
print(f"trade_count       = {stats.get('trade_count')}")
print(f"return_pct        = {stats.get('return_pct')}")
print(f"sharpe_ratio      = {stats.get('sharpe_ratio')}")
print(f"max_drawdown_pct  = {stats.get('max_drawdown_pct')}")
print(f"win_rate_pct      = {stats.get('win_rate_pct')}")
print(f"profit_factor     = {stats.get('profit_factor')}")
print(f"equity_final      = {stats.get('equity_final')}")
print(f"equity_peak       = {stats.get('equity_peak')}")
print(f"trade_count (raw) = {stats.get('# Trades', 'N/A')}")

trades = r.get('trades', [])
eq = r.get('equity_curve', [])
print(f"\nTrades list length: {len(trades)}")
print(f"Equity curve points: {len(eq)}")
if eq:
    first_eq = eq[0]
    last_eq = eq[-1]
    print(f"First equity: {first_eq.get('Equity', first_eq)}")
    print(f"Last equity:  {last_eq.get('Equity', last_eq)}")
    if len(eq) < 100:
        print(f"⚠️ Only {len(eq)} equity points — backtest stopped early!")

if trades:
    t = trades[0]
    print(f"\nFirst trade:")
    print(f"  entryPrice={t.get('entryPrice')}, exitPrice={t.get('exitPrice')}")
    print(f"  returnPct={t.get('returnPct')}%, exitReason={t.get('exitReason')}")
    print(f"  entryTime={t.get('entryTime')}, exitTime={t.get('exitTime')}")
    print(f"  size={t.get('size')}")

# Also print ALL stats keys and values
print(f"\nALL stats ({len(stats)} keys):")
for k in sorted(stats.keys()):
    v = stats[k]
    print(f"  {k}: {v}")
