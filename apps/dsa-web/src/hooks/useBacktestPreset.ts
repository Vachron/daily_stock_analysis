import { useState, useEffect, useCallback } from 'react';
import type { PresetInfo } from '../types/backtest';
import { backtestApi } from '../api/backtest';

export function useBacktestPreset(stockCode?: string) {
  const [presets, setPresets] = useState<PresetInfo[]>([]);
  const [autoPreset, setAutoPreset] = useState<PresetInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await backtestApi.getPresets();
      setPresets(res.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '获取预设失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  useEffect(() => {
    if (!stockCode) return;
    backtestApi.getPresetForStock(stockCode).then(setAutoPreset).catch(() => setAutoPreset(null));
  }, [stockCode]);

  return { presets, autoPreset, loading, error, refetch: fetch };
}
