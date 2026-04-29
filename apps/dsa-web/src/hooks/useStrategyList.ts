import { useState, useEffect, useCallback } from 'react';
import type { StrategyInfo } from '../types/backtest';
import { backtestApi } from '../api/backtest';

export function useStrategyList() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await backtestApi.getStrategies();
      setStrategies(res.items);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '获取策略列表失败';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  return { strategies, loading, error, refetch: fetch };
}
