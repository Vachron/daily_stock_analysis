import { EmptyState } from '../common';

interface MonthlyHeatmapProps {
  equityCurve: Array<{ date?: string; Date?: string; Equity: number; DrawdownPct: number }>;
  height?: number;
}

export function MonthlyHeatmap({ equityCurve }: MonthlyHeatmapProps) {
  if (!equityCurve || equityCurve.length < 2) {
    return <EmptyState title="暂无月度数据" description="回测数据不足以生成月度热力图" className="border-dashed h-40" />;
  }

  const returns: Map<string, number> = new Map();
  for (let i = 1; i < equityCurve.length; i++) {
    const dateKey = equityCurve[i].date || equityCurve[i].Date || '';
    const monthKey = dateKey.slice(0, 7);
    const prev = equityCurve[i - 1].Equity;
    const curr = equityCurve[i].Equity;
    if (prev > 0) {
      returns.set(monthKey, (returns.get(monthKey) || 0) + (curr / prev - 1));
    }
  }

  const monthReturns: { ym: string; year: number; month: number; returnPct: number }[] = [];
  for (const [ym, cum] of returns) {
    const [y, m] = ym.split('-');
    monthReturns.push({ ym, year: parseInt(y, 10), month: parseInt(m, 10), returnPct: cum * 100 });
  }
  monthReturns.sort((a, b) => a.ym.localeCompare(b.ym));

  if (monthReturns.length === 0) {
    return <EmptyState title="无月度收益数据" description="" className="border-dashed h-40" />;
  }

  const minYear = monthReturns[0].year;
  const maxYear = monthReturns[monthReturns.length - 1].year;
  const years: number[] = [];
  for (let y = minYear; y <= maxYear; y++) years.push(y);
  const months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

  const lookup: Map<string, number> = new Map();
  for (const mr of monthReturns) lookup.set(mr.ym, mr.returnPct);

  const allVals = monthReturns.map((m) => m.returnPct);
  const maxAbs = Math.max(Math.abs(Math.max(...allVals)), Math.abs(Math.min(...allVals)), 1);

  const MONTH_LABELS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-secondary-text">月度收益热力图</span>
        <span className="text-[10px] text-muted-text">{minYear} ~ {maxYear}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="border-collapse text-[10px]">
          <thead>
            <tr>
              <th className="text-left px-1.5 py-1 text-muted-text font-medium">年份</th>
              {months.map((m) => (
                <th key={m} className="text-center px-1.5 py-1 text-muted-text font-medium w-12">
                  {MONTH_LABELS[m - 1]}
                </th>
              ))}
              <th className="text-center px-1.5 py-1 text-muted-text font-medium">年收益</th>
            </tr>
          </thead>
          <tbody>
            {years.map((year) => {
              let yearReturn = 0;
              return (
                <tr key={year}>
                  <td className="text-left px-1.5 py-0.5 font-mono text-muted-text">{year}</td>
                  {months.map((month) => {
                    const key = `${year}-${String(month).padStart(2, '0')}`;
                    const v = lookup.get(key);
                    if (v == null) return <td key={month} className="text-center px-1 py-0.5 text-muted-text/40">--</td>;
                    yearReturn += v;
                    const ratio = v / maxAbs;
                    const alpha = Math.abs(ratio) * 0.6 + 0.1;
                    const bg = ratio >= 0
                      ? `rgba(34,197,94,${alpha.toFixed(2)})`
                      : `rgba(239,68,68,${alpha.toFixed(2)})`;
                    return (
                      <td
                        key={month}
                        className="text-center px-1 py-0.5 tabular-nums font-mono"
                        style={{ background: bg }}
                        title={`${key}: ${v >= 0 ? '+' : ''}${v.toFixed(2)}%`}
                      >
                        <span className={v >= 0 ? 'text-success' : 'text-danger'}>
                          {v >= 0 ? '+' : ''}{v.toFixed(1)}
                        </span>
                      </td>
                    );
                  })}
                  <td className={`text-center px-1.5 py-0.5 font-mono font-medium tabular-nums ${yearReturn >= 0 ? 'text-success' : 'text-danger'}`}>
                    {yearReturn >= 0 ? '+' : ''}{yearReturn.toFixed(1)}%
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-1.5 justify-center">
        <span className="text-[8px] text-muted-text">亏损</span>
        <div className="h-2 w-16 rounded" style={{ background: 'linear-gradient(to right, rgba(239,68,68,0.7), rgba(239,68,68,0.1), transparent, rgba(34,197,94,0.1), rgba(34,197,94,0.7))' }} />
        <span className="text-[8px] text-muted-text">盈利</span>
      </div>
    </div>
  );
}
