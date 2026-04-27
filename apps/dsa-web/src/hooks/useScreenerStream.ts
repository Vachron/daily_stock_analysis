import { useEffect, useRef, useState } from 'react';

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
  const onPoolProgressRef = useRef(onPoolProgress);
  const onScreenerProgressRef = useRef(onScreenerProgress);

  useEffect(() => {
    onPoolProgressRef.current = onPoolProgress;
  }, [onPoolProgress]);

  useEffect(() => {
    onScreenerProgressRef.current = onScreenerProgress;
  }, [onScreenerProgress]);

  useEffect(() => {
    mountedRef.current = true;
    if (!enabled) return;

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
          onPoolProgressRef.current?.(data);
        }
      } catch { /* ignore parse errors */ }
    });

    es.addEventListener('screener_progress', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as ScreenerProgress;
        if (mountedRef.current) {
          setScreenerProgress(data);
          onScreenerProgressRef.current?.(data);
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
          if (mountedRef.current && enabled) {
            const newEs = new EventSource(url);
            eventSourceRef.current = newEs;
            setupListeners(newEs);
          }
        }, 5000);
      }
    };

    function setupListeners(sse: EventSource) {
      sse.addEventListener('connected', () => {
        if (mountedRef.current) setIsConnected(true);
      });

      sse.addEventListener('pool_progress', (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data) as ScreenerProgress;
          if (mountedRef.current) {
            setPoolProgress(data);
            onPoolProgressRef.current?.(data);
          }
        } catch { /* ignore */ }
      });

      sse.addEventListener('screener_progress', (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data) as ScreenerProgress;
          if (mountedRef.current) {
            setScreenerProgress(data);
            onScreenerProgressRef.current?.(data);
          }
        } catch { /* ignore */ }
      });

      sse.addEventListener('heartbeat', () => {});

      sse.onerror = () => {
        if (mountedRef.current) setIsConnected(false);
        sse.close();
        eventSourceRef.current = null;
        if (mountedRef.current && enabled) {
          reconnectTimerRef.current = setTimeout(() => {
            if (mountedRef.current && enabled) {
              const retryEs = new EventSource(url);
              eventSourceRef.current = retryEs;
              setupListeners(retryEs);
            }
          }, 5000);
        }
      };
    }

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [enabled]);

  const reconnect = () => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    const url = `${API_BASE}/api/v1/screener/stream`;
    const es = new EventSource(url);
    eventSourceRef.current = es;
    setIsConnected(false);

    es.addEventListener('connected', () => {
      if (mountedRef.current) setIsConnected(true);
    });

    es.addEventListener('pool_progress', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as ScreenerProgress;
        if (mountedRef.current) {
          setPoolProgress(data);
          onPoolProgressRef.current?.(data);
        }
      } catch { /* ignore */ }
    });

    es.addEventListener('screener_progress', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as ScreenerProgress;
        if (mountedRef.current) {
          setScreenerProgress(data);
          onScreenerProgressRef.current?.(data);
        }
      } catch { /* ignore */ }
    });

    es.addEventListener('heartbeat', () => {});

    es.onerror = () => {
      if (mountedRef.current) setIsConnected(false);
      es.close();
      eventSourceRef.current = null;
    };
  };

  return { isConnected, poolProgress, screenerProgress, reconnect };
}
