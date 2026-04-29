import { useState, useCallback } from 'react';
import type { MontecarloRequest, MontecarloResult } from '../types/backtest';
import { backtestApi } from '../api/backtest';

export function useMonteCarlo() {
  const [result, setResult] = useState<MontecarloResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (params: MontecarloRequest) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await backtestApi.runMontecarlo(params);
      setResult(res);
      return res;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '蒙特卡洛模拟失败';
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
