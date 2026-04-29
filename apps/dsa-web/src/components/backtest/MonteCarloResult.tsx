import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, ResponsiveContainer, Cell,
} from 'recharts';
import type { MontecarloResultItem } from '../../types/backtest';
import { EmptyState } from '../common';

interface MonteCarloResultProps {
  originalStats: Record<string, number>;
  medianReturn: number;
  p5Return: number;
  p95Return: number;
  ruinProbability: number;
  results: MontecarloResultItem[];
  nSimulations: number;
  height?: number;
}

export function MonteCarloResult({
  originalStats, medianReturn, p5Return, p95Return,
  ruinProbability, results, nSimulations, height = 300,
}: MonteCarloResultProps) {
  if (results.length === 0) {
    return <EmptyState title="暂无模拟数据" description="执行蒙特卡洛模拟后将展示收益分布" className="border-dashed" />;
  }

  const returns = results.map((r) => r.returnPct);
  const minR = Math.min(...returns);
  const maxR = Math.max(...returns);
  const bins = 30;
  const binWidth = (maxR - minR) / bins || 1;
  const histogram: { bin: number; count: number }[] = [];

  for (let i = 0; i < bins; i++) {
    const low = minR + i * binWidth;
    const high = low + binWidth;
    histogram.push({
      bin: Number((low + binWidth / 2).toFixed(1)),
      count: returns.filter((r) => r >= low && r < high).length,
    });
  }

  const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
  const sharpeAvg = results.reduce((a, b) => a + (b.sharpeRatio ?? 0), 0) / results.length;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-5 gap-2">
        {[
          { label: '模拟次数', value: String(nSimulations), sub: '' },
          { label: '原始收益', value: `${(originalStats.return_pct ?? 0) >= 0 ? '+' : ''}${(originalStats.return_pct ?? 0).toFixed(2)}%`, sub: '' },
          { label: '中位收益', value: `${medianReturn >= 0 ? '+' : ''}${medianReturn.toFixed(2)}%`, sub: '' },
          { label: 'P5 最差', value: `${p5Return >= 0 ? '+' : ''}${p5Return.toFixed(2)}%`, sub: '最差5%场景' },
          { label: 'P95 最佳', value: `${p95Return >= 0 ? '+' : ''}${p95Return.toFixed(2)}%`, sub: '最佳5%场景' },
          { label: '平均收益', value: `${avgReturn >= 0 ? '+' : ''}${avgReturn.toFixed(2)}%`, sub: '' },
          { label: '平均夏普', value: sharpeAvg.toFixed(2), sub: '' },
          { label: '破产概率', value: `${(ruinProbability * 100).toFixed(2)}%`, sub: '亏损>50%' },
        ].map((m, i) => (
          <div key={i} className="flex flex-col items-center gap-0.5 px-2 py-2 rounded-xl bg-card/50 border border-border/30">
            <span className={`text-sm font-bold tabular-nums ${m.label === '破产概率' && ruinProbability > 0.1 ? 'text-danger' : m.label === 'P5 最差' ? 'text-warning' : 'text-foreground'}`}>
              {m.value}
            </span>
            <span className="text-[9px] text-muted-text">{m.label}</span>
            {m.sub && <span className="text-[8px] text-muted-text/60">{m.sub}</span>}
          </div>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={histogram} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="bin" tick={{ fontSize: 10, fill: '#64748b' }} label={{ value: '收益率 (%)', position: 'bottom', fontSize: 10, fill: '#64748b' }} />
          <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
          <RechartsTooltip
            contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: '11px', color: '#e2e8f0' }}
            formatter={((value: unknown) => [`${value} 次`, '频次']) as never}
          />
          <Bar dataKey="count" radius={[2, 2, 0, 0]} maxBarSize={20}>
            {histogram.map((entry, i) => {
              const isPositive = entry.bin >= 0;
              return <Cell key={i} fill={isPositive ? '#22c55e80' : '#ef444480'} />;
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <p className="text-[9px] text-muted-text text-center">
        蒙特卡洛模拟基于随机生成的价格数据，{nSimulations} 次独立模拟。破产概率 = 收益率 &lt; -50% 的模拟占比。
        回测结果不代表未来收益。
      </p>
    </div>
  );
}
