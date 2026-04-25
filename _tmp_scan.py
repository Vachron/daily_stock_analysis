import yaml, os
strats_dir = 'strategies'
for f in sorted(os.listdir(strats_dir)):
    if not f.endswith(('.yaml','.yml')):
        continue
    with open(os.path.join(strats_dir,f),'r',encoding='utf-8') as fh:
        d = yaml.safe_load(fh)
    if not d:
        continue
    name = d.get('name','?')
    cat = d.get('category','?')
    regimes = d.get('market_regimes',[])
    pri = d.get('default_priority',100)
    print(f'{name:30s} cat={cat:12s} regimes={regimes} pri={pri}')
