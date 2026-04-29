import { useMemo } from 'react';
import { TrendingDown, AlertTriangle } from 'lucide-react';
import { ComposedChart, CartesianGrid, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, Area } from 'recharts';

interface RiskTabProps {
  nav: Array<{ date: string; nav: number }>;
  metrics: Record<string, number>;
}

function calcDrawdown(nav: Array<{ date: string; nav: number }>) {
  let peak = -Infinity;
  let maxDD = 0;
  const ddSeries: Array<{ label: string; drawdown: number; nav: number }> = [];

  for (const p of nav) {
    if (p.nav > peak) peak = p.nav;
    const dd = peak > 0 ? (1 - p.nav / peak) * 100 : 0;
    if (dd > maxDD) maxDD = dd;
    ddSeries.push({
      label: p.date?.slice(5) ?? '',
      drawdown: -dd,
      nav: p.nav,
    });
  }
  return { ddSeries, maxDD };
}

export function RiskTab({ nav, metrics }: RiskTabProps) {
  const { ddSeries, maxDD } = useMemo(() => calcDrawdown(nav), [nav]);

  if (!nav || nav.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-text gap-2">
        <AlertTriangle className="h-8 w-8" />
        <span className="text-xs">暂无数据</span>
      </div>
    );
  }

  const maxDrawdownPct = metrics.max_drawdown_pct ?? maxDD;
  const lastDd = ddSeries[ddSeries.length - 1]?.drawdown ?? 0;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-lg bg-card/40 border border-border/20 p-3 text-center">
          <div className="text-[10px] text-muted-text mb-1">最大回撤</div>
          <div className="text-sm font-mono font-medium text-danger">-{maxDrawdownPct.toFixed(2)}%</div>
        </div>
        <div className="rounded-lg bg-card/40 border border-border/20 p-3 text-center">
          <div className="text-[10px] text-muted-text mb-1">当前回撤</div>
          <div className="text-sm font-mono font-medium text-warning">{lastDd.toFixed(2)}%</div>
        </div>
        <div className="rounded-lg bg-card/40 border border-border/20 p-3 text-center">
          <div className="text-[10px] text-muted-text mb-1">数据点数</div>
          <div className="text-sm font-mono font-medium text-foreground">{nav.length}</div>
        </div>
      </div>

      <div className="rounded-xl bg-card/40 border border-border/20 p-3">
        <div className="flex items-center gap-2 mb-2">
          <TrendingDown className="h-3.5 w-3.5 text-danger" />
          <span className="text-xs font-medium text-secondary-text">回撤曲线</span>
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <ComposedChart data={ddSeries} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.15} />
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
              interval={Math.max(1, Math.floor(ddSeries.length / 8))} />
            <YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
              tickFormatter={(v: number) => `${v.toFixed(1)}%`} domain={['auto', 0]} />
            <RechartsTooltip
              contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8, fontSize: 11 }}
              labelStyle={{ color: 'hsl(var(--foreground))' }}
              formatter={(v: unknown) => [`${Number(v ?? 0).toFixed(2)}%`, '回撤']}
            />
            <Area type="monotone" dataKey="drawdown" fill="hsl(var(--destructive) / 0.15)" stroke="hsl(var(--destructive))" strokeWidth={1.5} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <div className="rounded-lg bg-card/40 border border-border/20 p-3">
          <div className="text-[10px] text-muted-text mb-2">风险提示</div>
          <ul className="text-[10px] text-secondary-text space-y-1">
            <li>• 最大回撤超过20%需关注策略鲁棒性</li>
            <li>• 回测表现不代表未来收益</li>
            <li>• 建议观察最长回撤恢复期</li>
          </ul>
        </div>
        <div className="rounded-lg bg-card/40 border border-border/20 p-3">
          <div className="text-[10px] text-muted-text mb-2">关键指标</div>
          <div className="space-y-1 text-[10px]">
            <div className="flex justify-between">
              <span className="text-muted-text">最大回撤</span>
              <span className="font-mono text-danger">-{maxDrawdownPct.toFixed(2)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-text">Calmar比率</span>
              <span className="font-mono text-foreground">{((metrics.annualized_return_pct ?? 0) / (maxDrawdownPct || 1)).toFixed(3)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-text">跟踪误差</span>
              <span className="font-mono text-foreground">{((metrics.tracking_error_pct as number | undefined) ?? 0).toFixed(2)}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
