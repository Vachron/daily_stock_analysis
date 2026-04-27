import { useEffect, useRef, useCallback, useState } from 'react';

export interface ScreenerStep {
  label: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  detail: string;
}

export interface ScreenerProgress {
  taskType: 'pool_init' | 'screener';
  status: 'idle' | 'running' | 'completed' | 'failed';
  progressPct: number;
  message: string;
  stage: string;
  steps: ScreenerStep[];
  extra: Record<string, unknown>;
  updatedAt: string;
}

export interface UseScreenerStreamOptions {
  onPoolProgress?: (progress: ScreenerProgress) => void;
  onScreenerProgress?: (progress: ScreenerProgress) => void;
  enabled?: boolean;
}

export interface UseScreenerStreamResult {
  isConnected: boolean;
  poolProgress: ScreenerProgress | null;
  screenerProgress: ScreenerProgress | null;
  reconnect: () => void;
}

const API_BASE = import.meta.env.VITE_API_BASE || '';

export function useScreenerStream(options: UseScreenerStreamOptions = {}): UseScreenerStreamResult {
  const { onPoolProgress, onScreenerProgress, enabled = true } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [poolProgress, setPoolProgress] = useState<ScreenerProgress | null>(null);
  const [screenerProgress, setScreenerProgress] = useState<ScreenerProgress | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!enabled || !mountedRef.current) return;

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = `${API_BASE}/api/v1/screener/stream`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.addEventListener('connected', () => {
      if (mountedRef.current) setIsConnected(true);
    });

    es.addEventListener('pool_progress', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as ScreenerProgress;
        if (mountedRef.current) {
          setPoolProgress(data);
          onPoolProgress?.(data);
        }
      } catch { /* ignore parse errors */ }
    });

    es.addEventListener('screener_progress', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as ScreenerProgress;
        if (mountedRef.current) {
          setScreenerProgress(data);
          onScreenerProgress?.(data);
        }
      } catch { /* ignore parse errors */ }
    });

    es.addEventListener('heartbeat', () => {
      // keep-alive
    });

    es.onerror = () => {
      if (mountedRef.current) setIsConnected(false);
      es.close();
      eventSourceRef.current = null;
      if (mountedRef.current && enabled) {
        reconnectTimerRef.current = setTimeout(() => {
          if (mountedRef.current && enabled) connect();
        }, 5000);
      }
    };
  }, [enabled, onPoolProgress, onScreenerProgress]);

  const reconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    connect();
  }, [connect]);

  useEffect(() => {
    mountedRef.current = true;
    if (enabled) connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [enabled, connect]);

  return { isConnected, poolProgress, screenerProgress, reconnect };
}
