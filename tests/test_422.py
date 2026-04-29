import urllib.request, json
data = json.dumps({'strategy':'momentum','codes':['600519'],'cash':100000}).encode()
req = urllib.request.Request('http://localhost:8000/api/v1/backtest/strategy',
    data=data, headers={'Content-Type': 'application/json'}, method='POST')
try:
    r = urllib.request.urlopen(req, timeout=30)
    print('OK:', json.dumps(json.loads(r.read()), indent=2, ensure_ascii=False)[:500])
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}')
    body = e.read().decode()
    print(body[:800])
