import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
import pandas as pd, numpy as np
from src.backtest.engine import Backtest
from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
from datetime import timedelta

repo = KlineRepo()

# Test bull_trend on 3 different stocks
strategies_to_test = ['bull_trend', 'momentum_reversal', 'bollinger_reversion', 'rs_i_reversal', 'turtle_trading']
codes = ['000001', '600519', '000002']

for sname in strategies_to_test:
    for code in codes[:1]:
        try:
            cls = yaml_to_strategy_class(sname)
            df = repo.get_history(code)
            if df is None or df.empty:
                print(f'{sname} on {code}: no data')
                continue
            df = df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'})
            df['Date'] = pd.to_datetime(df['date'].apply(lambda d: ORIGIN_DATE + timedelta(days=int(d))))
            df = df.set_index('Date')
            df = df['2023-01-01':'2024-12-31']
            bt = Backtest(df, cls, cash=100000)
            result = bt.run()
            n_trades = int(result.stats.get('# Trades', 0))
            ret = float(result.stats.get('Return [%]', 0))
            sf = f'{sname}/{code}: {n_trades} trades, ret={ret:.2f}%'
            if n_trades > 0:
                print(f'  ✅ {sf}')
            else:
                print(f'  ❌ {sf}')
        except Exception as e:
            print(f'  💥 {sname}/{code}: {e}')
