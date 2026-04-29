import { useState, useCallback } from 'react';
import type { OptimizeRequest, OptimizeResult } from '../types/backtest';
import { backtestApi } from '../api/backtest';

export function useBacktestOptimize() {
  const [result, setResult] = useState<OptimizeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (params: OptimizeRequest) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await backtestApi.runOptimize(params);
      setResult(res);
      return res;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '参数优化失败';
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
