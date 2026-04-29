import { Check, Loader2, Circle } from 'lucide-react';

interface PipelineStage {
  key: string;
  label: string;
  status: 'done' | 'running' | 'waiting' | 'error';
  detail?: string;
  duration_ms?: number;
  error?: string;
}

interface BacktestPipelineProps {
  stages: PipelineStage[];
  currentStage?: string;
  progressPct?: number;
  etaSeconds?: number | null;
  totalBars?: number;
  processedBars?: number;
}

const STAGE_ICONS: Record<PipelineStage['status'], React.ReactNode> = {
  done: <Check className="h-3.5 w-3.5 text-success" />,
  running: <Loader2 className="h-3.5 w-3.5 text-cyan animate-spin" />,
  waiting: <Circle className="h-3.5 w-3.5 text-muted-text/30" />,
  error: <span className="text-danger text-xs">✗</span>,
};

const STAGE_DETAILS: Record<string, string> = {
  data_loading: '加载K线数据',
  strategy_parsing: '解析YAML策略',
  signal_gen: '生成交易信号',
  order_exec: '模拟撮合执行',
  stats_compute: '计算绩效指标',
};

export function BacktestPipeline({ stages, currentStage, progressPct, etaSeconds, totalBars, processedBars }: BacktestPipelineProps) {
  if (stages.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-secondary-text">📊 回测数据管线</span>
        {currentStage && (
          <span className="text-[10px] text-cyan animate-pulse">
            {STAGE_DETAILS[currentStage] || currentStage}
          </span>
        )}
      </div>

      <div className="flex items-center gap-1 overflow-x-auto">
        {stages.map((stage, i) => (
          <div key={stage.key} className="flex items-center gap-1 min-w-0">
            {i > 0 && (
              <div className={`h-px w-4 flex-shrink-0 ${
                stage.status === 'done' || (i > 0 && stages[i - 1].status === 'done')
                  ? 'bg-cyan/40'
                  : 'bg-border/20'
              }`} />
            )}
            <div
              className={`flex flex-col items-center gap-1 px-2 py-1.5 rounded-lg min-w-[64px] transition-all ${
                stage.status === 'running' ? 'bg-cyan/10 border border-cyan/20' :
                stage.status === 'done' ? 'bg-success/5 border border-success/10' :
                stage.status === 'error' ? 'bg-danger/5 border border-danger/20' :
                'border border-border/10'
              }`}
              title={stage.detail || STAGE_DETAILS[stage.key] || stage.label}
            >
              <div className="flex items-center gap-1">
                {STAGE_ICONS[stage.status]}
                <span className={`text-[9px] font-medium ${
                  stage.status === 'running' ? 'text-cyan' :
                  stage.status === 'done' ? 'text-success' :
                  stage.status === 'error' ? 'text-danger' :
                  'text-muted-text'
                }`}>
                  {stage.label}
                </span>
              </div>
              {stage.duration_ms != null && stage.status === 'done' && (
                <span className="text-[8px] text-muted-text/60">{(stage.duration_ms / 1000).toFixed(1)}s</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {(progressPct != null || etaSeconds != null || processedBars != null) && (
        <div className="space-y-1">
          {progressPct != null && (
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1.5 rounded-full bg-border/10 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-cyan to-cyan/60 transition-all duration-500"
                  style={{ width: `${Math.max(2, Math.min(100, progressPct))}%` }}
                />
              </div>
              <span className="text-[9px] text-muted-text tabular-nums w-8 text-right">{progressPct.toFixed(0)}%</span>
            </div>
          )}
          <div className="flex justify-between text-[8px] text-muted-text/60">
            {processedBars != null && totalBars != null && (
              <span>已处理 {processedBars}/{totalBars} 根K线</span>
            )}
            {etaSeconds != null && etaSeconds > 0 && (
              <span>预计剩余 {etaSeconds > 60 ? `${(etaSeconds / 60).toFixed(1)}min` : `${etaSeconds.toFixed(0)}s`}</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
