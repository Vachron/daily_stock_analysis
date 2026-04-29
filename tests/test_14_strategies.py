import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pandas as pd, numpy as np
from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
from src.backtest.engine import Backtest
from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
from datetime import timedelta

repo = KlineRepo()
codes = ['000001', '600519', '000002', '300750']
strategies = ['bull_trend', 'ma_golden_cross', 'momentum_reversal', 'bollinger_reversion',
              'turtle_trading', 'volume_breakout', 'macd_divergence', 'rsi_reversal',
              'shrink_pullback', 'w_bottom', 'morning_star', 'dragon_head',
              'box_oscillation', 'wave_theory']

ok = fail = 0
for sname in strategies:
    for code in ['000001']:
        try:
            cls = yaml_to_strategy_class(sname)
            df = repo.get_history(code)
            if df is None or df.empty: continue
            df = df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'})
            df['Date'] = pd.to_datetime(df['date'].apply(lambda d: ORIGIN_DATE + timedelta(days=int(d))))
            df = df.set_index('Date')
            df = df['2023-01-01':'2024-12-31']
            bt = Backtest(df, cls, cash=100000)
            result = bt.run()
            n = int(result.stats.get('# Trades', 0))
            ret = float(result.stats.get('Return [%]', 0))
            if n > 0:
                ok += 1; print(f'  ✅ {sname}: {n} trades, ret={ret:+.2f}%')
            else:
                fail += 1; print(f'  ❌ {sname}: {n} trades')
        except Exception as e:
            fail += 1; print(f'  💥 {sname}: {e}')

print(f'\n  PASS: {ok}/{ok+fail}')
