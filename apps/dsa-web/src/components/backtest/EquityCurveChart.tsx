import { TrendingUp } from 'lucide-react';
import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts';
import { EmptyState } from '../common';

interface EquityCurveChartProps {
  data: Array<{
    date?: string;
    Date?: string;
    Equity: number;
    DrawdownPct: number;
    DrawdownDuration?: number;
  }>;
  initialCash?: number;
  isLoading?: boolean;
  height?: number;
}

export function EquityCurveChart({ data, initialCash = 100000, isLoading, height = 320 }: EquityCurveChartProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-52">
        <div className="backtest-spinner md" />
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <EmptyState
        title="暂无权益曲线"
        description="执行策略回测后将在此展示权益曲线与回撤"
        className="h-52 border-dashed"
        icon={<TrendingUp className="h-5 w-5" />}
      />
    );
  }

  const chartData = data.slice(-1000).map((p, i) => ({
    idx: i,
    date: (p.date || p.Date || '').slice(5),
    equity: Number(Number(p.Equity).toFixed(0)),
    drawdown: Number(Number(p.DrawdownPct).toFixed(2)),
  }));

  const minEquity = Math.min(...chartData.map((d) => d.equity));
  const maxEquity = Math.max(...chartData.map((d) => d.equity));
  const minDD = Math.min(...chartData.map((d) => d.drawdown), 0);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <TrendingUp className="h-3.5 w-3.5 text-cyan" />
        <span className="text-xs font-medium text-secondary-text">权益曲线</span>
        <span className="text-[9px] text-muted-text">
          初始 ¥{initialCash.toLocaleString()}
          {chartData.length > 0 && ` | 最终 ¥${chartData[chartData.length - 1].equity.toLocaleString()}`}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
          <defs>
            <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.15} />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ef4444" stopOpacity={0.2} />
              <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#64748b' }} interval={Math.max(1, Math.floor(chartData.length / 8))} />
          <YAxis yAxisId="equity" tick={{ fontSize: 10, fill: '#64748b' }} domain={[minEquity * 0.95, maxEquity * 1.05]} tickFormatter={(v: number) => `¥${(v / 1000).toFixed(0)}k`} />
          <YAxis yAxisId="dd" orientation="right" tick={{ fontSize: 10, fill: '#64748b' }} domain={[minDD * 1.2, 0]} tickFormatter={(v: number) => `${v.toFixed(0)}%`} />
          <RechartsTooltip
            contentStyle={{
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: '8px',
              fontSize: '11px',
              color: '#e2e8f0',
            }}
            formatter={((value: unknown, name: string) => {
              const v = Number(value);
              if (name === 'equity') return [`¥${v.toLocaleString()}`, '权益'];
              return [`${v}%`, '回撤'];
            }) as any}
          />
          <ReferenceLine yAxisId="equity" y={initialCash} stroke="#64748b" strokeDasharray="4 4" strokeWidth={1} />
          <Area yAxisId="dd" type="monotone" dataKey="drawdown" stroke="#ef4444" strokeWidth={1} fill="url(#ddGrad)" name="回撤" />
          <Line yAxisId="equity" type="monotone" dataKey="equity" stroke="#06b6d4" strokeWidth={2} dot={false} name="策略权益" />
          <Legend wrapperStyle={{ fontSize: '10px', color: '#94a3b8' }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
