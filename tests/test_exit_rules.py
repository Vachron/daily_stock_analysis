import urllib.request, json
d = json.dumps({
    'strategy':'bollinger_reversion',
    'codes':['600519'],
    'cash':100000,
    'start_date':'2024-01-01',
    'end_date':'2024-12-31',
    'exit_rules':{
        'trailing_stop_pct':5,
        'take_profit_pct':10,
        'stop_loss_pct':8,
        'max_hold_days':30,
        'partial_exit_enabled': True,
        'partial_exit_pct': 0.5,
    },
}).encode()
r = urllib.request.Request('http://localhost:8000/api/v1/backtest/strategy',
    data=d, headers={'Content-Type':'application/json'}, method='POST')
resp = urllib.request.urlopen(r, timeout=30)
data = json.loads(resp.read())
print(f'OK {resp.status}')
s = data.get('stats', {})
print(f'return={s.get("return_pct")} sharpe={s.get("sharpe_ratio")} trades={s.get("trade_count")}')
trades = data.get('trades', [])
print(f'eq={len(data.get("equity_curve", []))} trades={len(trades)}')
if trades:
    t = trades[0]
    print(f'Trade keys: {sorted(t.keys())}')
