import { PieChart, Pie, Cell, Tooltip as RechartsTooltip, ResponsiveContainer, Legend } from 'recharts';
import { EmptyState } from '../common';

interface ExitReasonPieChartProps {
  trades: Array<{ exitReason?: string; returnPct?: number }>;
  height?: number;
}

const REASON_COLORS: Record<string, string> = {
  take_profit: '#22c55e',
  partial_take_profit: '#4ade80',
  trailing_stop: '#eab308',
  stop_loss: '#ef4444',
  signal_lost: '#38bdf8',
  fixed_days: '#a855f7',
  max_hold_days: '#f97316',
  force_close: '#9ca3af',
  manual: '#64748b',
};

const REASON_LABELS: Record<string, string> = {
  take_profit: '止盈',
  partial_take_profit: '部分止盈',
  trailing_stop: '移动止损',
  stop_loss: '固定止损',
  signal_lost: '信号消失',
  fixed_days: '固定天数',
  max_hold_days: '最大持仓',
  force_close: '强制平仓',
  manual: '手动平仓',
};

export function ExitReasonPieChart({ trades, height = 280 }: ExitReasonPieChartProps) {
  const counts: Record<string, { count: number; totalReturn: number }> = {};
  let totalTrades = 0;

  for (const t of trades) {
    const reason = t.exitReason || 'force_close';
    if (!counts[reason]) counts[reason] = { count: 0, totalReturn: 0 };
    counts[reason].count++;
    counts[reason].totalReturn += t.returnPct ?? 0;
    totalTrades++;
  }

  const data = Object.entries(counts)
    .map(([reason, { count, totalReturn }]) => ({
      name: REASON_LABELS[reason] || reason,
      reason,
      value: count,
      avgReturn: totalReturn / count,
    }))
    .sort((a, b) => b.value - a.value);

  if (data.length === 0) {
    return <EmptyState title="暂无平仓数据" description="执行回测后将展示平仓原因分布" className="border-dashed" />;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-secondary-text">平仓原因分布</span>
        <span className="text-[10px] text-muted-text">共 {totalTrades} 笔</span>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <ResponsiveContainer width="100%" height={height}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={100}
              paddingAngle={2}
              dataKey="value"
            >
              {data.map((entry, i) => (
                <Cell key={i} fill={REASON_COLORS[entry.reason] || '#64748b'} stroke="transparent" />
              ))}
            </Pie>
            <RechartsTooltip
              contentStyle={{
                background: '#1e293b',
                border: '1px solid #334155',
                borderRadius: '8px',
                fontSize: '11px',
                color: '#e2e8f0',
              }}
              formatter={((value: unknown, _name: string, props: unknown) => {
                const p = props as { payload?: { avgReturn: number } };
                const avg = p?.payload?.avgReturn ?? 0;
                return [`${value} 笔 (均 ${avg >= 0 ? '+' : ''}${avg.toFixed(2)}%)`, ''];
              }) as never}
            />
            <Legend
              wrapperStyle={{ fontSize: '10px', color: '#94a3b8' }}
              formatter={(value: string) => <span style={{ color: '#94a3b8' }}>{value}</span>}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="space-y-1 text-[10px]">
          {data.map((d) => (
            <div key={d.reason} className="flex items-center justify-between py-0.5">
              <div className="flex items-center gap-1.5">
                <div className="h-2.5 w-2.5 rounded-sm" style={{ background: REASON_COLORS[d.reason] || '#64748b' }} />
                <span className="text-muted-text">{d.name}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-foreground tabular-nums">{d.value} 笔</span>
                <span className={`tabular-nums ${d.avgReturn >= 0 ? 'text-success' : 'text-danger'}`}>
                  {d.avgReturn >= 0 ? '+' : ''}{d.avgReturn.toFixed(2)}%
                </span>
                <span className="text-muted-text">({((d.value / totalTrades) * 100).toFixed(0)}%)</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
