import { Sparkles, Brain, TrendingUp, Shield, Target, BarChart3 } from 'lucide-react';

interface AISummaryCardProps {
  stats: Record<string, number>;
  strategyName?: string;
  symbol?: string;
}

function nlDescription(stats: Record<string, number>, strategyName?: string): string {
  const ret = stats.returnPct ?? 0;
  const sharpe = stats.sharpeRatio ?? 0;
  const winRate = stats.winRatePct ?? 0;
  const maxDD = stats.maxDrawdownPct ?? 0;
  const trades = stats.tradeCount ?? 0;

  const parts: string[] = [];

  if (strategyName) {
    parts.push(`策略「${strategyName}」`);
  } else {
    parts.push('该策略');
  }

  if (trades > 0) {
    parts.push(`在回测期间共执行了 ${trades} 笔交易`);
  } else {
    parts.push('在回测期间未产生任何交易');
    return parts.join('，') + '。请检查策略参数是否过于严格。';
  }

  parts.push(`累计收益 ${ret >= 0 ? '+' : ''}${ret.toFixed(2)}%`);

  if (sharpe >= 2) {
    parts.push('夏普比率表现优异');
  } else if (sharpe >= 1) {
    parts.push('夏普比率表现良好');
  } else if (sharpe >= 0.5) {
    parts.push('夏普比率一般');
  } else if (trades > 0) {
    parts.push(`夏普比率偏低（${sharpe.toFixed(2)}），风险调整收益不理想`);
  }

  if (winRate >= 60) {
    parts.push(`胜率 ${winRate.toFixed(0)}% 较高`);
  } else if (winRate >= 40) {
    parts.push(`胜率 ${winRate.toFixed(0)}% 处于合理范围`);
  } else if (trades > 0) {
    parts.push(`胜率偏低（${winRate.toFixed(0)}%），需要优化入场信号`);
  }

  if (maxDD < -20) {
    parts.push(`最大回撤 ${maxDD.toFixed(1)}% 偏大，建议收紧止损或降低仓位`);
  } else if (maxDD < -10) {
    parts.push(`最大回撤 ${maxDD.toFixed(1)}%，风险可控`);
  } else if (trades > 0) {
    parts.push(`最大回撤仅 ${Math.abs(maxDD).toFixed(1)}%，风险控制良好`);
  }

  return parts.join('，') + '。';
}

function overallVerdict(stats: Record<string, number>): { verdict: string; tone: string; icon: React.ReactNode } {
  const sharpe = stats.sharpeRatio ?? 0;
  const ret = stats.returnPct ?? 0;
  const winRate = stats.winRatePct ?? 0;
  const maxDD = Math.abs(stats.maxDrawdownPct ?? 0);
  const trades = stats.tradeCount ?? 0;

  if (trades === 0) {
    return { verdict: '无交易', tone: 'text-muted-text', icon: <Target className="h-4 w-4" /> };
  }
  if (sharpe >= 1.5 && ret > 0 && winRate >= 55 && maxDD < 15) {
    return { verdict: '优秀', tone: 'text-success', icon: <Sparkles className="h-4 w-4 text-success" /> };
  }
  if (sharpe >= 1 && ret > 0 && winRate >= 45) {
    return { verdict: '良好', tone: 'text-cyan', icon: <TrendingUp className="h-4 w-4 text-cyan" /> };
  }
  if (sharpe >= 0.5 && winRate >= 40) {
    return { verdict: '一般', tone: 'text-warning', icon: <BarChart3 className="h-4 w-4 text-warning" /> };
  }
  if (ret < -20 || maxDD > 30) {
    return { verdict: '高风险', tone: 'text-danger', icon: <Shield className="h-4 w-4 text-danger" /> };
  }
  return { verdict: '待优化', tone: 'text-muted-text', icon: <Brain className="h-4 w-4 text-muted-text" /> };
}

export function AISummaryCard({ stats, strategyName, symbol }: AISummaryCardProps) {
  if (!stats || Object.keys(stats).length === 0) {
    return (
      <div className="text-center py-4 text-[10px] text-muted-text">
        暂无回测数据
      </div>
    );
  }

  const description = nlDescription(stats, strategyName);
  const { verdict, tone, icon } = overallVerdict(stats);

  const highlights: Array<{ label: string; value: string; ok: boolean }> = [
    { label: '夏普比率', value: (stats.sharpeRatio ?? 0).toFixed(2), ok: (stats.sharpeRatio ?? 0) >= 1 },
    { label: '最大回撤', value: `${(stats.maxDrawdownPct ?? 0).toFixed(1)}%`, ok: Math.abs(stats.maxDrawdownPct ?? 0) <= 15 },
    { label: '胜率', value: `${(stats.winRatePct ?? 0).toFixed(0)}%`, ok: (stats.winRatePct ?? 0) >= 50 },
    { label: '盈亏比', value: (stats.profitFactor ?? 0).toFixed(2), ok: (stats.profitFactor ?? 0) >= 1.2 },
  ];

  return (
    <div className="rounded-xl bg-gradient-to-br from-card/60 to-card/30 border border-border/20 overflow-hidden">
      <div className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <Brain className="h-4 w-4 text-cyan" />
          <span className="text-xs font-semibold text-foreground">AI 综合评估</span>
          <span className={`text-xs font-bold ml-auto flex items-center gap-1 ${tone}`}>
            {icon}
            {verdict}
          </span>
        </div>

        <p className="text-[11px] text-secondary-text leading-relaxed">
          {description}
        </p>

        <div className="grid grid-cols-4 gap-2 mt-3">
          {highlights.map((h) => (
            <div key={h.label} className="flex flex-col items-center gap-0.5 px-2 py-1.5 rounded-lg bg-card/40 border border-border/20">
              <span className={`text-xs font-bold tabular-nums ${h.ok ? 'text-success' : 'text-warning'}`}>
                {h.value}
              </span>
              <span className="text-[8px] text-muted-text">{h.label}</span>
            </div>
          ))}
        </div>

        <div className="mt-3 pt-3 border-t border-border/20 text-[9px] text-muted-text/60 space-y-1">
          {strategyName && symbol && (
            <p>📌 {strategyName} · {symbol}</p>
          )}
          <p>⚠️ 回测结果不代表未来收益。以上评估基于历史数据生成的规则化描述。</p>
        </div>
      </div>
    </div>
  );
}
