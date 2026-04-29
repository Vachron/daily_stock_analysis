import type { ReactNode } from 'react';
import { Loader2 } from 'lucide-react';

interface ProgressOverlayProps {
  visible: boolean;
  stage?: string;
  message?: string;
  progressPct?: number;
  etaSeconds?: number | null;
  children: ReactNode;
  totalBars?: number;
  processedBars?: number;
  cancelLabel?: string;
  onCancel?: () => void;
}

const STAGE_LABELS: Record<string, string> = {
  checking: '正在检查数据...',
  fetching: '正在获取K线数据...',
  parsing: '正在解析策略...',
  evaluating: '正在执行回测...',
  computing: '正在计算指标...',
  done: '回测完成',
};

export function ProgressOverlay({
  visible, stage, message, progressPct, etaSeconds,
  children, totalBars, processedBars, cancelLabel, onCancel,
}: ProgressOverlayProps) {
  if (!visible) return <>{children}</>;

  const stageLabel = stage ? (STAGE_LABELS[stage] || stage) : (message || '处理中...');
  const pct = Math.max(1, Math.min(100, progressPct ?? 0));

  return (
    <div className="relative">
      {children}
      <div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-30 rounded-xl animate-fade-in">
        <div className="flex flex-col items-center gap-4 p-6 max-w-sm w-full">
          <Loader2 className="h-8 w-8 text-cyan animate-spin" />

          <div className="text-center space-y-1">
            <p className="text-sm font-medium text-foreground">{stageLabel}</p>
            {message && message !== stageLabel && (
              <p className="text-[10px] text-muted-text">{message}</p>
            )}
          </div>

          <div className="w-full space-y-1.5">
            <div className="w-full h-2 rounded-full bg-border/10 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-cyan via-cyan/80 to-cyan/50 transition-all duration-500 ease-out"
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="flex justify-between text-[9px] text-muted-text">
              <span>{pct.toFixed(0)}%</span>
              {totalBars != null && processedBars != null
                ? <span>{processedBars} / {totalBars} 根K线</span>
                : (etaSeconds != null && etaSeconds > 0)
                  ? <span>预计剩余 {etaSeconds > 60 ? `${(etaSeconds / 60).toFixed(1)}min` : `${etaSeconds.toFixed(0)}s`}</span>
                  : <span>请耐心等待...</span>
              }
            </div>
          </div>

          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="text-[10px] text-muted-text hover:text-danger transition-colors underline"
            >
              {cancelLabel || '取消'}
            </button>
          )}

          <p className="text-[8px] text-muted-text/50 text-center max-w-64">
            系统正在处理您的请求。无论计算多久, 您都能看到完整的进度信息——这就是本系统的透明度承诺。
          </p>
        </div>
      </div>
    </div>
  );
}
