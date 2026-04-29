"""在 bar 27 追踪 _process_orders 的执行"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pandas as pd, numpy as np
from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
from src.backtest.engine import Backtest
from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
from datetime import timedelta

repo = KlineRepo()
df = repo.get_history('000001')
df = df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'})
df['Date'] = pd.to_datetime(df['date'].apply(lambda d: ORIGIN_DATE + timedelta(days=int(d))))
df = df.set_index('Date')
df = df['2026-01-01':'2026-04-24']

cls = yaml_to_strategy_class('bull_trend')
orig_init = cls.init
orig_next = cls.next

traced = set()

def debug_init(self):
    orig_init(self)
    # Patch broker._process_orders
    orig_po = self._broker._process_orders
    orig_eo = self._broker._execute_order
    self._broker_traced = False
    
    def traced_po(i):
        if not hasattr(self._broker, '_traced_count'):
            self._broker._traced_count = 0
        self._broker._traced_count += 1
        
        if self._broker._traced_count == 28:  # bar 27 (0-indexed)
            print(f"\n[PROCESS_ORDERS @ bar {i}]")
            print(f"  Orders: {len(self._broker._orders)}")
            for o in self._broker._orders:
                print(f"    Order: type={o._type}, size={o.size}, tag={o.tag}")
            print(f"  Open={self._broker._data.Open[i]:.4f}, High={self._broker._data.High[i]:.4f}, Low={self._broker._data.Low[i]:.4f}, Close={self._broker._data.Close[i]:.4f}")
        
        orig_po(i)
        
        if self._broker._traced_count == 28:
            print(f"  After process_orders: orders={len(self._broker._orders)}, trades={len(self._broker._trades)}, cash={self._broker._cash:.1f}")
            for t in self._broker._trades:
                print(f"    Trade: size={t.size}, entryPrice={t.entry_price:.2f}, closed={t._is_closed}")
    
    self._broker._process_orders = traced_po

cls.init = debug_init

bt = Backtest(df, cls, cash=100000)
result = bt.run()
print(f"\nFINAL: traded={int(result.stats.get('# Trades',0))}, Return={float(result.stats.get('Return [%]',0)):.2f}%")
