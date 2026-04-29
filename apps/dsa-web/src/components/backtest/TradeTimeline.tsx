import { TrendingUp, TrendingDown, AlertCircle, DollarSign, Clock, Target } from 'lucide-react';
import { useState } from 'react';

export interface DecisionStep {
  step: number;
  timestamp: string;
  type: 'signal' | 'filter' | 'risk_check' | 'order' | 'sl_adjust' | 'exit';
  description: string;
  detail: string;
  passed?: boolean;
  actualValue?: number;
  threshold?: number;
  result?: string;
  icon?: 'signal' | 'buy' | 'sell' | 'adjust' | 'pnl' | 'clock' | 'target' | 'warn';
}

interface TradeTimelineProps {
  trades: Array<{
    size?: number;
    entryBar?: number | string;
    exitBar?: number | string;
    entryPrice?: number;
    exitPrice?: number;
    sl?: number;
    tp?: number;
    pnl?: number;
    returnPct?: number;
    entryTime?: string;
    exitTime?: string;
    duration?: string;
    tag?: string;
    exitReason?: string;
  }>;
  maxItems?: number;
}

function buildDecisionSteps(trade: TradeTimelineProps['trades'][number], idx: number): DecisionStep[] {
  const steps: DecisionStep[] = [];
  const entryTime = (trade.entryTime || String(trade.entryBar || '')).slice(0, 10);
  const exitTime = (trade.exitTime || String(trade.exitBar || '')).slice(0, 10);

  steps.push({
    step: 1, timestamp: entryTime, type: 'signal',
    description: '入场信号触发',
    detail: trade.tag ? `${trade.tag}` : `策略买入信号 #${idx + 1}`,
    passed: true, icon: 'signal',
  });

  steps.push({
    step: 2, timestamp: entryTime, type: 'order',
    description: '下单成交',
    detail: `${(trade.size ?? 0) > 0 ? '买入' : '卖出'} @ ¥${(trade.entryPrice ?? 0).toFixed(2)}`,
    passed: true, icon: 'buy',
  });

  if (trade.sl != null || trade.tp != null) {
    steps.push({
      step: 3, timestamp: entryTime, type: 'risk_check',
      description: '风控挂单',
      detail: `${trade.sl != null ? `止损 ¥${trade.sl.toFixed(2)}` : ''}${trade.tp != null ? ` 止盈 ¥${trade.tp.toFixed(2)}` : ''}`,
      passed: true, icon: 'target',
    });
  }

  if (trade.exitReason || trade.exitBar) {
    steps.push({
      step: 4, timestamp: exitTime || '?', type: 'exit',
      description: '平仓触发',
      detail: `@ ¥${(trade.exitPrice ?? 0).toFixed(2)} · ${EXIT_LABEL[trade.exitReason || ''] || trade.exitReason || '手动'}`,
      passed: true, icon: 'sell',
    });
  }

  steps.push({
    step: 5, timestamp: exitTime || '?', type: 'pnl' as never,
    description: '交易盈亏',
    detail: `${(trade.returnPct ?? 0) >= 0 ? '盈利' : '亏损'} ${(trade.returnPct ?? 0) >= 0 ? '+' : ''}${(trade.returnPct ?? 0).toFixed(2)}%`,
    passed: (trade.returnPct ?? 0) >= 0,
    actualValue: trade.returnPct,
    icon: 'pnl',
  });

  return steps;
}

const ICON_MAP: Record<string, React.ReactNode> = {
  signal: <AlertCircle className="h-3.5 w-3.5 text-cyan" />,
  buy: <TrendingUp className="h-3.5 w-3.5 text-success" />,
  sell: <TrendingDown className="h-3.5 w-3.5 text-danger" />,
  adjust: <Target className="h-3.5 w-3.5 text-warning" />,
  pnl: <DollarSign className="h-3.5 w-3.5 text-foreground" />,
  clock: <Clock className="h-3.5 w-3.5 text-muted-text" />,
  target: <Target className="h-3.5 w-3.5 text-cyan" />,
  warn: <AlertCircle className="h-3.5 w-3.5 text-danger" />,
};

const EXIT_LABEL: Record<string, string> = {
  take_profit: '止盈', trailing_stop: '移动止损', stop_loss: '固定止损',
  signal_lost: '信号消失', fixed_days: '固定天数', max_hold_days: '最大持仓',
  force_close: '强制平仓', manual: '手动平仓',
};

export function TradeTimeline({ trades, maxItems = 5 }: TradeTimelineProps) {
  const [selectedIdx, setSelectedIdx] = useState(0);
  const visible = trades.slice(0, maxItems);

  if (visible.length === 0) {
    return (
      <div className="text-center py-4 text-[10px] text-muted-text">
        暂无交易记录，无法生成决策时间线
      </div>
    );
  }

  const trade = visible[selectedIdx];
  const steps = buildDecisionSteps(trade, selectedIdx);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-secondary-text">📋 交易决策日志</span>
        <div className="flex items-center gap-1">
          {visible.map((_t, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setSelectedIdx(i)}
              className={`px-2 py-0.5 rounded text-[9px] font-mono transition-all ${
                i === selectedIdx ? 'bg-cyan/10 text-cyan border border-cyan/20' : 'text-muted-text hover:text-foreground border border-border/10'
              }`}
            >
              #{i + 1}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-xl bg-card/30 border border-border/20 overflow-hidden">
        <div className="px-3 py-2 border-b border-border/20 flex items-center justify-between bg-border/5">
          <span className="text-[10px] font-medium text-foreground">
            交易 #{selectedIdx + 1}
            {(trade.size ?? 0) > 0 ? ' 做多' : ' 做空'}
          </span>
          <span className="text-[9px] text-muted-text">
            {EXIT_LABEL[trade.exitReason || ''] || trade.exitReason || '手动'} · {(trade.returnPct ?? 0) >= 0 ? '+' : ''}{(trade.returnPct ?? 0).toFixed(2)}%
          </span>
        </div>

        <div className="p-3">
          <div className="relative">
            {steps.map((step, i) => (
              <div key={i} className="flex gap-3 pb-3 last:pb-0">
                <div className="flex flex-col items-center">
                  <div className={`rounded-full p-1 ${
                    step.passed === false ? 'bg-danger/10' :
                    step.icon === 'sell' ? 'bg-danger/10' :
                    step.icon === 'pnl' && (step.actualValue ?? 0) < 0 ? 'bg-danger/10' :
                    'bg-cyan/10'
                  }`}>
                    {ICON_MAP[step.icon || 'signal'] || ICON_MAP.signal}
                  </div>
                  {i < steps.length - 1 && (
                    <div className={`w-px flex-1 min-h-[16px] ${i < 2 ? 'bg-cyan/30' : 'bg-border/20'}`} />
                  )}
                </div>
                <div className="flex-1 min-w-0 pb-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-medium ${
                      step.passed === false ? 'text-danger' : 'text-foreground'
                    }`}>
                      {step.description}
                    </span>
                    {step.passed != null && (
                      <span className={`text-[8px] ${step.passed ? 'text-success' : 'text-danger'}`}>
                        {step.passed ? '✅' : '❌'}
                      </span>
                    )}
                  </div>
                  <p className="text-[9px] text-muted-text mt-0.5">{step.detail}</p>
                  {step.actualValue != null && step.threshold != null && (
                    <div className="flex items-center gap-1 mt-0.5">
                      <span className="text-[8px] text-muted-text/60">
                        实际 {step.actualValue} / 阈值 {step.threshold}
                      </span>
                      <span className={`text-[8px] font-medium ${step.passed ? 'text-success' : 'text-danger'}`}>
                        {step.passed ? '通过' : '未通过'}
                      </span>
                    </div>
                  )}
                </div>
                <span className="text-[8px] text-muted-text/40 flex-shrink-0 mt-0.5 font-mono">
                  {step.timestamp}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <p className="text-[8px] text-muted-text/60 text-center">
        展开每笔交易可查看完整入场→持仓→出场决策链
      </p>
    </div>
  );
}
