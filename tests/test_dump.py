import urllib.request, json
data = json.dumps({
    'strategy':'momentum_reversal','codes':['600519'],
    'cash':100000,'start_date':'2023-01-01','end_date':'2024-12-31',
}).encode()
req = urllib.request.Request('http://localhost:8000/api/v1/backtest/strategy',
    data=data, headers={'Content-Type':'application/json'}, method='POST')
r = urllib.request.urlopen(req, timeout=120)
resp = json.loads(r.read())
print(json.dumps({k: type(v).__name__ if isinstance(v,(list,dict)) else v for k,v in resp.items()}, indent=2))
print('---')
if resp.get('stats'):
    print('stats keys:', list(resp['stats'].keys())[:15])
if resp.get('equity_curve'):
    print('equity_curve[0]:', resp['equity_curve'][0])
if resp.get('trades'):
    print('trades[0]:', json.dumps(resp['trades'][0], default=str)[:300])
