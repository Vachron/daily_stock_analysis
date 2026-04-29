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
  submitted_for_analysis?: number;
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
  const onProgressRef = useRef(onProgress);
  const onCompletedRef = useRef(onCompleted);
  const onErrorRef = useRef(onError);
  const hasReceivedDataRef = useRef(false);

  useEffect(() => {
    onProgressRef.current = onProgress;
    onCompletedRef.current = onCompleted;
    onErrorRef.current = onError;
  });

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    hasReceivedDataRef.current = false;

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
        hasReceivedDataRef.current = true;
        if (mountedRef.current) {
          setProgress(data);
          setIsConnected(true);
          onProgressRef.current?.(data);
        }
      } catch { /* ignore */ }
    });

    es.addEventListener('heartbeat', () => {
      hasReceivedDataRef.current = true;
    });

    es.addEventListener('completed', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as BacktestCompleted;
        if (mountedRef.current) {
          setResult(data);
          setIsConnected(false);
          onCompletedRef.current?.(data);
        }
      } catch { /* ignore */ }
    });

    es.addEventListener('error', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as { message: string };
        if (data.message && mountedRef.current) {
          setError(data.message);
          onErrorRef.current?.(data.message);
        }
      } catch {
        // Server-initiated error event without parseable JSON — ignore, let onerror handle
      }
      setIsConnected(false);
    });

    es.onerror = () => {
      // EventSource onerror fires on ANY connection close — including clean close
      // after a completed event. Only treat as error if we never received data.
      if (!hasReceivedDataRef.current && mountedRef.current) {
        setError('回测连接失败');
        onErrorRef.current?.('回测连接失败');
      }
      setIsConnected(false);
    };

    return () => {
      mountedRef.current = false;
      es.close();
      eventSourceRef.current = null;
    };
  }, [enabled, params]);

  return { isConnected, progress, result, error, disconnect };
}
