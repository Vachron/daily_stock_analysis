import { useEffect, useRef, useCallback, useState } from 'react';

export interface BacktestProgress {
  stage: 'checking' | 'analyzing' | 'evaluating';
  message: string;
  progressPct: number;
  code?: string;
  codeIndex?: number;
  codeTotal?: number;
  codes?: string[];
  current?: number;
  total?: number;
}

export interface BacktestCompleted {
  processed: number;
  saved: number;
  completed: number;
  insufficient: number;
  errors: number;
  analyzed: number;
}

export interface UseBacktestStreamOptions {
  onProgress?: (progress: BacktestProgress) => void;
  onCompleted?: (result: BacktestCompleted) => void;
  onError?: (message: string) => void;
  enabled?: boolean;
}

export interface UseBacktestStreamResult {
  isConnected: boolean;
  progress: BacktestProgress | null;
  result: BacktestCompleted | null;
  error: string | null;
  disconnect: () => void;
}

const API_BASE = import.meta.env.VITE_API_BASE || '';

function buildUrl(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    if (Array.isArray(v)) {
      sp.set(k, v.join(','));
    } else {
      sp.set(k, String(v));
    }
  }
  return `${API_BASE}/api/v1/backtest/run/stream?${sp.toString()}`;
}

export function useBacktestStream(
  params: Record<string, unknown> | null,
  options: UseBacktestStreamOptions = {},
): UseBacktestStreamResult {
  const { onProgress, onCompleted, onError, enabled = true } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [progress, setProgress] = useState<BacktestProgress | null>(null);
  const [result, setResult] = useState<BacktestCompleted | null>(null);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const mountedRef = useRef(true);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    if (!enabled || !params) {
      return;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    const url = buildUrl(params);
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.addEventListener('progress', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as BacktestProgress;
        if (mountedRef.current) {
          setProgress(data);
          setIsConnected(true);
          onProgress?.(data);
        }
      } catch { /* ignore */ }
    });

    es.addEventListener('completed', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as BacktestCompleted;
        if (mountedRef.current) {
          setResult(data);
          setIsConnected(false);
          onCompleted?.(data);
        }
      } catch { /* ignore */ }
    });

    es.addEventListener('error', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as { message: string };
        const msg = data.message || '回测执行失败';
        if (mountedRef.current) {
          setError(msg);
          onError?.(msg);
        }
      } catch {
        if (mountedRef.current && !result) {
          setError('回测连接失败');
          onError?.('回测连接失败');
        }
      }
      setIsConnected(false);
    });

    es.onerror = () => {
      setIsConnected(false);
    };

    return () => {
      mountedRef.current = false;
      es.close();
      eventSourceRef.current = null;
    };
  }, [enabled, params, onProgress, onCompleted, onError]);

  return { isConnected, progress, result, error, disconnect };
}
