import { useEffect, useRef, useCallback, useState } from 'react';

export interface AlphaProgress {
  status: 'idle' | 'running' | 'completed' | 'failed';
  progressPct: number;
  message: string;
  stage: string;
  metrics?: Record<string, number>;
}

export interface UseAlphaStreamOptions {
  onProgress?: (progress: AlphaProgress) => void;
  onCompleted?: (metrics: Record<string, number>) => void;
  onFailed?: (error: string) => void;
  enabled?: boolean;
}

export interface UseAlphaStreamResult {
  isConnected: boolean;
  progress: AlphaProgress | null;
  connect: () => void;
  disconnect: () => void;
}

const API_BASE = import.meta.env.VITE_API_BASE || '';

export function useAlphaStream(options: UseAlphaStreamOptions = {}): UseAlphaStreamResult {
  const { onProgress, onCompleted, onFailed, enabled = true } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [progress, setProgress] = useState<AlphaProgress | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const connectRef = useRef<() => void>(() => {});

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback(() => {
    if (!enabled || !mountedRef.current) return;

    disconnect();

    const url = `${API_BASE}/api/v1/alpha/stream`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.addEventListener('connected', () => {
      if (mountedRef.current) setIsConnected(true);
    });

    es.addEventListener('alpha_progress', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as AlphaProgress;
        if (mountedRef.current) {
          setProgress(data);
          onProgress?.(data);
          if (data.status === 'completed' && data.metrics) {
            onCompleted?.(data.metrics);
          }
          if (data.status === 'failed') {
            onFailed?.(data.message || 'Unknown error');
          }
        }
      } catch { /* ignore */ }
    });

    es.addEventListener('heartbeat', () => {});

    es.onerror = () => {
      if (mountedRef.current) setIsConnected(false);
      es.close();
      eventSourceRef.current = null;
      if (mountedRef.current && enabled) {
        reconnectTimerRef.current = setTimeout(() => {
          if (mountedRef.current && enabled) connectRef.current();
        }, 5000);
      }
    };
  }, [enabled, onProgress, onCompleted, onFailed, disconnect]);

  useEffect(() => {
    connectRef.current = connect;
  });

  useEffect(() => {
    mountedRef.current = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (enabled) connect();
    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [enabled, connect, disconnect]);

  return { isConnected, progress, connect, disconnect };
}
