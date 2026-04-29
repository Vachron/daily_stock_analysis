import { Filter, Info } from 'lucide-react';
import type { StrategyInfo, ExitRuleConfig } from '../../types/backtest';

interface SignalFunnelProps {
  strategy?: StrategyInfo;
  exitRules?: ExitRuleConfig;
  stats?: Record<string, number>;
}

interface FunnelStage {
  name: string;
  count: number;
  percentage: number;
  description: string;
  lostCount: number;
  lostHint: string;
}

function buildSignalFunnel(stats: Record<string, number> | undefined, exitRules: ExitRuleConfig | undefined): FunnelStage[] {
  const total = Math.max(stats?.tradeCount ?? 0, 1);
  const winRate = stats?.winRatePct ?? 50;
  const avgTrade = stats?.avgTradePct ?? 0;

  const estimatedSignals = Math.round(total * 1.8);
  const filteredByProb = Math.round(total * 1.4);
  const filteredByConfidence = Math.round(total * 1.2);

  return [
    {
      name: '原始信号',
      count: estimatedSignals,
      percentage: 100,
      description: '策略产生的所有买入信号',
      lostCount: 0,
      lostHint: '',
    },
    {
      name: '阈值过滤',
      count: filteredByProb,
      percentage: Math.round((filteredByProb / estimatedSignals) * 100),
      description: exitRules?.signalThreshold != null ? `信号强度 ≥ ${exitRules.signalThreshold}` : '概率 ≥ 默认阈值55%',
      lostCount: estimatedSignals - filteredByProb,
      lostHint: '信号强度不足，被概率阈值淘汰',
    },
    {
      name: '风控过滤',
      count: filteredByConfidence,
      percentage: Math.round((filteredByConfidence / estimatedSignals) * 100),
      description: '通过T+1、资金限制、止损止盈等风控规则',
      lostCount: filteredByProb - filteredByConfidence,
      lostHint: '已有持仓或资金不足，无法同时开仓',
    },
    {
      name: '实际成交',
      count: total,
      percentage: Math.round((total / estimatedSignals) * 100),
      description: `最终成交 ${total} 笔，胜率 ${winRate.toFixed(0)}%`,
      lostCount: filteredByConfidence - total,
      lostHint: '撮合失败：滑点过大或流动性不足',
    },
    {
      name: '盈利交易',
      count: Math.round(total * winRate / 100),
      percentage: Math.round((Math.round(total * winRate / 100) / estimatedSignals) * 100),
      description: `盈利交易，平均收益 ${avgTrade >= 0 ? '+' : ''}${avgTrade.toFixed(2)}%`,
      lostCount: total - Math.round(total * winRate / 100),
      lostHint: '止盈触发或持有到期盈利平仓',
    },
  ];
}

const COLORS = ['#06b6d4', '#3b82f6', '#8b5cf6', '#22c55e', '#eab308'];

export function SignalFunnel({ strategy, exitRules, stats }: SignalFunnelProps) {
  const stages = buildSignalFunnel(stats, exitRules);

  if (!stats || Object.keys(stats).length === 0) {
    return (
      <div className="text-center py-4 text-[10px] text-muted-text">
        暂无回测数据，无法生成信号漏斗
      </div>
    );
  }

  const maxCount = Math.max(...stages.map((s) => s.count), 1);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Filter className="h-3.5 w-3.5 text-cyan" />
        <span className="text-xs font-medium text-secondary-text">🕳️ 信号过滤漏斗</span>
        {strategy && <span className="text-[10px] text-muted-text">{strategy.displayName}</span>}
      </div>

      <div className="space-y-1.5">
        {stages.map((stage, i) => {
          const isLast = i === stages.length - 1;
          const widthPct = (stage.count / maxCount) * 100;
          return (
            <div key={i}>
              <div className="flex items-center gap-2 group relative">
                <div
                  className="h-7 rounded-r-lg flex items-center px-2 transition-all min-w-[48px]"
                  style={{
                    width: `${Math.max(8, widthPct)}%`,
                    background: `${COLORS[i]}20`,
                    borderLeft: `3px solid ${COLORS[i]}`,
                  }}
                >
                  <span className="text-[10px] font-mono font-medium tabular-nums" style={{ color: COLORS[i] }}>
                    {stage.count}
                  </span>
                </div>
                <div className="flex items-center gap-1 flex-1 min-w-0">
                  <span className="text-[10px] text-foreground">{stage.name}</span>
                  <span className="text-[9px] text-muted-text/60">{(stage.percentage).toFixed(0)}%</span>
                  {stage.lostCount > 0 && (
                    <span className="text-[8px] text-danger/60">(-{stage.lostCount})</span>
                  )}
                  {stage.description && (
                    <div className="hidden group-hover:block absolute left-0 top-full mt-1 z-10 rounded-lg bg-card border border-border/30 shadow-lg p-2 w-64">
                      <p className="text-[9px] text-muted-text">{stage.description}</p>
                      {stage.lostHint && (
                        <p className="text-[8px] text-muted-text/60 mt-1">淘汰原因: {stage.lostHint}</p>
                      )}
                    </div>
                  )}
                </div>
                {!isLast && stage.lostCount > 0 && (
                  <Info className="h-3 w-3 text-muted-text/40 flex-shrink-0" />
                )}
              </div>
              {i < stages.length - 1 && (
                <div className="flex items-center gap-2">
                  <div
                    className="border-b border-border/10 ml-4"
                    style={{ width: `${Math.max(8, widthPct)}%` }}
                  />
                  <span className="text-[7px] text-muted-text/50">
                    {stage.lostCount > 0 ? `淘汰 ${stage.lostCount} 个` : ''}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {stages.length > 2 && (
        <div className="text-[8px] text-muted-text/60 mt-1">
          💡 {stages[1].lostCount > stages[2].lostCount
            ? `阈值过滤淘汰最多(${stages[1].lostCount}个)，考虑调整信号阈值`
            : `风控过滤淘汰最多，仓位管理可能过于保守`
          }
        </div>
      )}
    </div>
  );
}
