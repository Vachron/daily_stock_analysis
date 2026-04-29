import { TrendingUp, Activity } from 'lucide-react';
import { ComposedChart, CartesianGrid, XAxis, YAxis, Tooltip as RechartsTooltip, ReferenceLine, Line, Legend, ResponsiveContainer } from 'recharts';
import { StatCard } from '../common';

interface OverviewTabProps {
  metrics: Record<string, number>;
  nav: Array<{ date: string; nav: number }>;
  benchmarkNav?: Array<{ date: string; nav: number }>;
}

const formatPct = (v?: number) => (v != null ? `${v > 0 ? '+' : ''}${v.toFixed(2)}%` : '--');
const formatNum = (v?: number, dec = 2) => (v != null ? v.toFixed(dec) : '--');

export function OverviewTab({ metrics, nav, benchmarkNav }: OverviewTabProps) {
  if (!metrics || Object.keys(metrics).length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-text gap-2">
        <Activity className="h-8 w-8" />
        <span className="text-xs">暂无回测数据</span>
      </div>
    );
  }

  const chartData = nav.map((p, i) => ({
    label: p.date?.slice(5) ?? '',
    nav: p.nav,
    benchmark: benchmarkNav?.[i]?.nav,
  }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
        <StatCard label="总收益" value={formatPct(metrics.total_return_pct as number | undefined)} />
        <StatCard label="年化收益" value={formatPct(metrics.annualized_return_pct as number | undefined)} />
        <StatCard label="夏普比率" value={formatNum(metrics.sharpe_ratio as number | undefined, 3)} />
        <StatCard label="最大回撤" value={formatPct(metrics.max_drawdown_pct as number | undefined)} />
        <StatCard label="超额收益" value={formatPct(metrics.excess_return_pct as number | undefined)} />
        <StatCard label="信息比率" value={formatNum(metrics.information_ratio as number | undefined, 3)} />
        <StatCard label="胜率" value={formatPct(metrics.win_rate_pct as number | undefined)} />
        <StatCard label="换手率" value={formatPct(metrics.turnover_rate_pct as number | undefined)} />
      </div>

      {chartData.length > 0 && (
        <div className="rounded-xl bg-card/40 border border-border/20 p-3">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="h-3.5 w-3.5 text-success" />
            <span className="text-xs font-medium text-secondary-text">净值曲线</span>
            {benchmarkNav && benchmarkNav.length > 0 && (
              <span className="text-[10px] text-muted-text">vs 沪深300</span>
            )}
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.15} />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                interval={Math.max(1, Math.floor(chartData.length / 8))} />
              <YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                tickFormatter={(v: number) => `¥${(v / 1000).toFixed(1)}K`} />
              <RechartsTooltip
                contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8, fontSize: 11 }}
                labelStyle={{ color: 'hsl(var(--foreground))' }}
                formatter={(v: unknown) => [`¥${Number(v ?? 0).toFixed(2)}`, '净值']}
              />
              <ReferenceLine y={chartData[0]?.nav ?? 0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
              <Line type="monotone" dataKey="nav" stroke="hsl(var(--primary))" strokeWidth={1.5} dot={false} name="组合净值" />
              {benchmarkNav && benchmarkNav.length > 0 && (
                <Line type="monotone" dataKey="benchmark" stroke="hsl(var(--muted-foreground))" strokeWidth={1} dot={false} strokeDasharray="4 4" name="沪深300" />
              )}
              <Legend wrapperStyle={{ fontSize: 10 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
