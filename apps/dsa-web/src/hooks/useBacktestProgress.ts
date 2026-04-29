import { useEffect, useRef, useState, useCallback } from 'react';

export interface BacktestProgressEvent {
  stage: string;
  date: string;
  day: number;
  totalDays: number;
  nav: number;
  message: string;
}

export interface BacktestCompletedEvent {
  runId: string;
  success: boolean;
  error: string | null;
  metrics: Record<string, number>;
  nav: Array<{ date: string; nav: number }>;
  trades: Array<Record<string, unknown>>;
  elapsedSeconds: number;
}

export interface UseBacktestProgressResult {
  isConnected: boolean;
  progress: BacktestProgressEvent | null;
  result: BacktestCompletedEvent | null;
  disconnect: () => void;
}

const API_BASE = import.meta.env.VITE_API_BASE || '';

export function useBacktestProgress(
  runId: string | null,
  enabled: boolean = true,
): UseBacktestProgressResult {
  const [isConnected, setIsConnected] = useState(false);
  const [progress, setProgress] = useState<BacktestProgressEvent | null>(null);
  const [result, setResult] = useState<BacktestCompletedEvent | null>(null);
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

    if (!enabled || !runId) {
      return;
    }

    const url = `${API_BASE}/api/v1/backtest/portfolio/stream?run_id=${encodeURIComponent(runId)}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.addEventListener('connected', () => {
      if (mountedRef.current) setIsConnected(true);
    });

    es.addEventListener('progress', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as BacktestProgressEvent;
        if (mountedRef.current) setProgress(data);
      } catch { /* ignore */ }
    });

    es.addEventListener('completed', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as BacktestCompletedEvent;
        if (mountedRef.current) {
          setResult(data);
          setIsConnected(false);
        }
      } catch { /* ignore */ }
    });

    es.addEventListener('error', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as { message: string };
        if (mountedRef.current) {
          setResult({
            runId: runId,
            success: false,
            error: data.message || '回测执行失败',
            metrics: {},
            nav: [],
            trades: [],
            elapsedSeconds: 0,
          });
        }
      } catch {
        if (mountedRef.current) {
          setResult({
            runId: runId,
            success: false,
            error: '回测执行失败',
            metrics: {},
            nav: [],
            trades: [],
            elapsedSeconds: 0,
          });
        }
      }
      setIsConnected(false);
    });

    es.onerror = () => {
      if (mountedRef.current) setIsConnected(false);
    };

    return () => {
      mountedRef.current = false;
      es.close();
      eventSourceRef.current = null;
    };
  }, [runId, enabled]);

  return { isConnected, progress, result, disconnect };
}
