"""Simple compare: adapter vs direct — hack into engine run to print all_trades"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pandas as pd, numpy as np
from src.backtest.engine import Backtest
from src.backtest.strategy import BacktestStrategy
from src.backtest.lib import SMA
from src.backtest.adapters.yaml_strategy import yaml_to_strategy_class
from data_provider.kline_repo import KlineRepo, ORIGIN_DATE
from datetime import timedelta

repo = KlineRepo()
df = repo.get_history('000001')
df = df.rename(columns={'open':'Open','high':'High','low':'Low','close':'Close','volume':'Volume'})
df['Date'] = pd.to_datetime(df['date'].apply(lambda d: ORIGIN_DATE + timedelta(days=int(d))))
df = df.set_index('Date')
df = df['2026-01-01':'2026-04-24']

# Hack: inject trace into engine run method
import types
orig_run = Backtest.run

def instrumented_run(self, **kwargs):
    # Copy the original run logic but add prints
    from src.backtest.engine import _Broker, _OHLCVData, BacktestResult, compute_stats, StrategyError, InsufficientDataError
    from datetime import datetime
    
    data = _OHLCVData(self._data_df)
    broker = _Broker(
        cash=self._cash, data=data, commission=self._commission,
        slippage=self._slippage, stamp_duty=self._stamp_duty,
        min_commission=self._min_commission, margin=self._margin,
        trade_on_close=self._trade_on_close, hedging=self._hedging,
        exclusive_orders=self._exclusive_orders,
        exit_rule=self._exit_rule,
    )
    
    strategy = self._strategy_cls(**kwargs) if kwargs else self._strategy_cls()
    strategy._broker = broker
    strategy._data = data
    strategy.init()
    strategy._compute_indicators(data)
    
    equity_curve = []
    total_bars = len(data)
    result_meta = {"error_bars": 0, "skipped_bars": 0, "total_bars": total_bars}
    
    for i in range(total_bars):
        broker._current_bar = i
        broker._process_orders(i)
        broker._check_sl_tp(i)
        strategy.next(i)
        equity = broker._equity
        equity_curve.append(equity)
        if broker._check_ruin():
            break
    
    broker._finalize(total_bars - 1)
    equity_curve.append(broker._equity)
    
    all_trades = broker._closed_trades + [t for t in broker._trades if not t._is_closed]
    
    print(f"[INSTRUMENTED] all_trades: {len(all_trades)}")
    print(f"  _closed_trades: {len(broker._closed_trades)}")
    print(f"  _trades (open): {len([t for t in broker._trades if not t._is_closed])}")
    print(f"  _trades (total): {len(broker._trades)}")
    if broker._closed_trades:
        for t in broker._closed_trades:
            print(f"  closed: tag={t.tag}, closed={t._is_closed}, size={t.size}")
    if broker._trades:
        for t in broker._trades:
            print(f"  trades: tag={t.tag}, closed={t._is_closed}, size={t.size}")
    
    trade_df = self._build_trades_df(all_trades)
    stats = compute_stats(all_trades, np.array(equity_curve), data_df=data.df, cash=self._cash)
    eq_df = self._build_equity_df(equity_curve, data)
    
    return BacktestResult(
        strategy_name=getattr(strategy, '_display_name', self._strategy_cls.__name__),
        symbol=getattr(data.df, 'attrs', {}).get('symbol', ''),
        start_date=data.index[0], end_date=data.index[-1],
        initial_cash=self._cash, commission=self._commission,
        slippage=self._slippage, stamp_duty=self._stamp_duty,
        stats=stats, equity_curve=eq_df, trades=trade_df,
        engine_version="v2", created_at=datetime.now(), _meta=result_meta,
    )

Backtest.run = instrumented_run

# Test adapter
print("=== Adapter bulls_trend ===")
cls = yaml_to_strategy_class('bull_trend')
bt = Backtest(df, cls, cash=100000)
r = bt.run()

# Test direct
print("\n=== Direct Strategy ===")
class Direct(BacktestStrategy):
    def init(self):
        self.sma5 = self.I(SMA, 5, name='SMA5')
        self.sma20 = self.I(SMA, 20, name='SMA20')
    def next(self, i):
        if i < 20: return
        s5 = self.sma5[i]; s20 = self.sma20[i]
        s5p = self.sma5[i-1]; s20p = self.sma20[i-1]
        if np.isnan([s5,s20,s5p,s20p]).any(): return
        has_pos = any(not t._is_closed for t in self.trades)
        if s5 > s20 and s5p <= s20p and not has_pos:
            self.buy(size=0.25, tag='direct')

bt2 = Backtest(df, Direct, cash=100000)
r2 = bt2.run()
