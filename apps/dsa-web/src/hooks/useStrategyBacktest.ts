import { useState, useCallback } from 'react';
import type { StrategyBacktestRequest, StrategyBacktestResult } from '../types/backtest';
import { backtestApi } from '../api/backtest';

export function useStrategyBacktest() {
  const [result, setResult] = useState<StrategyBacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (params: StrategyBacktestRequest) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await backtestApi.runStrategy(params);
      setResult(res);
      return res;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '策略回测失败';
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
    setLoading(false);
  }, []);

  return { result, loading, error, run, reset };
}
