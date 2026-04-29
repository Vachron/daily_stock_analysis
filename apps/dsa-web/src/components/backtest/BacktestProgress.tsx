import type { BacktestProgressEvent } from '../../hooks/useBacktestProgress';

interface BacktestProgressProps {
  progress: BacktestProgressEvent | null;
  isConnected: boolean;
}

export function BacktestProgress({ progress, isConnected }: BacktestProgressProps) {
  if (!isConnected && !progress) return null;

  const pct = progress && progress.totalDays > 0
    ? Math.round((progress.day / progress.totalDays) * 100)
    : 0;

  return (
    <div className="flex flex-col items-center gap-4 py-8 animate-fade-in">
      {isConnected && !progress && (
        <div className="flex flex-col items-center gap-2">
          <div className="backtest-spinner lg" />
          <p className="text-sm text-secondary-text">正在初始化回测引擎...</p>
        </div>
      )}

      {progress && (
        <>
          <div className="w-full max-w-md space-y-2">
            <div className="flex justify-between text-[10px] text-muted-text">
              <span>{progress.stage === 'scoring' ? '策略打分' : '组合模拟'}</span>
              <span>{pct}%</span>
            </div>
            <div className="w-full h-2 rounded-full bg-border/20 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-cyan to-cyan-dim transition-all duration-500 ease-out"
                style={{ width: `${Math.max(pct, 2)}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px]">
              <span className="text-secondary-text">
                正在回测 <span className="font-mono text-foreground">{progress.date}</span>
              </span>
              <span className="text-muted-text">
                {progress.day} / {progress.totalDays} 天
              </span>
            </div>
            {progress.nav > 0 && (
              <div className="text-center text-xs text-secondary-text">
                当前净值 <span className="font-mono text-cyan font-medium">¥{progress.nav.toLocaleString()}</span>
              </div>
            )}
          </div>
          <p className="text-[10px] text-muted-text">{progress.message}</p>
        </>
      )}
    </div>
  );
}
