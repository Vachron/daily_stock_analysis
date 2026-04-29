import { Area, AreaChart, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { EmptyState } from '../common';

interface DrawdownChartProps {
  equityCurve: Array<{ date?: string; Date?: string; DrawdownPct: number }>;
  height?: number;
}

export function DrawdownChart({ equityCurve, height = 200 }: DrawdownChartProps) {
  if (!equityCurve || equityCurve.length === 0) {
    return <EmptyState title="暂无回撤数据" description="执行回测后将展示回撤曲线" className="border-dashed h-40" />;
  }

  const chartData = equityCurve.slice(-1000).map((p) => ({
    date: (p.date || p.Date || '').slice(5),
    drawdown: Number(Number(p.DrawdownPct).toFixed(2)),
  }));

  const minDD = Math.min(...chartData.map((d) => d.drawdown), 0);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-secondary-text">回撤曲线</span>
        <span className="text-[10px] text-muted-text">
          最大回撤: <span className="text-danger">{minDD.toFixed(2)}%</span>
        </span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
          <defs>
            <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ef4444" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#64748b' }} interval={Math.max(1, Math.floor(chartData.length / 8))} />
          <YAxis tick={{ fontSize: 10, fill: '#64748b' }} domain={[minDD * 1.2, 0]} tickFormatter={(v: number) => `${v.toFixed(0)}%`} />
          <RechartsTooltip
            contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: '11px', color: '#e2e8f0' }}
            formatter={((value: unknown) => [`${Number(value).toFixed(2)}%`, '回撤']) as never}
          />
          <ReferenceLine y={0} stroke="#475569" strokeDasharray="3 3" />
          <Area type="monotone" dataKey="drawdown" stroke="#ef4444" strokeWidth={1.5} fill="url(#ddGrad)" name="回撤" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
