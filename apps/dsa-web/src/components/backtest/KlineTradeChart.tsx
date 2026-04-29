import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { EmptyState } from '../common';

interface TradeMarker {
  date: string;
  price: number;
  type: 'buy' | 'sell';
  returnPct?: number;
}

interface KlineTradeChartProps {
  equityCurve: Array<{ date?: string; Date?: string; Equity: number }>;
  trades: Array<{ entryTime?: string; exitTime?: string; entryPrice?: number; exitPrice?: number; size?: number; returnPct?: number }>;
  height?: number;
}

export function KlineTradeChart({ equityCurve, trades, height = 300 }: KlineTradeChartProps) {
  if (!equityCurve || equityCurve.length === 0) {
    return <EmptyState title="暂无数据" description="执行回测后将展示权益与交易标记" className="border-dashed h-40" />;
  }

  const priceData = equityCurve.map((p, i) => ({
    idx: i,
    date: (p.date || p.Date || '').slice(5),
    equity: Number(Number(p.Equity).toFixed(0)),
  }));

  const markers: TradeMarker[] = [];
  for (const t of trades) {
    if (t.entryTime && t.entryPrice) {
      markers.push({ date: t.entryTime.slice(5, 10), price: t.entryPrice, type: 'buy', returnPct: t.returnPct });
    }
    if (t.exitTime && t.exitPrice) {
      markers.push({ date: t.exitTime.slice(5, 10), price: t.exitPrice, type: 'sell', returnPct: t.returnPct });
    }
  }
  markers.sort((a, b) => a.date.localeCompare(b.date));

  const maxEquity = Math.max(...priceData.map((d) => d.equity));
  const minEquity = Math.min(...priceData.map((d) => d.equity));

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-secondary-text">权益曲线 + 交易标记</span>
        <div className="flex items-center gap-2 text-[9px]">
          <span className="flex items-center gap-0.5"><div className="h-1.5 w-1.5 rounded-sm bg-green-400" />买入</span>
          <span className="flex items-center gap-0.5"><div className="h-1.5 w-1.5 rounded-sm bg-red-400" />卖出</span>
        </div>
        <span className="text-[10px] text-muted-text ml-auto">{markers.length} 个标记</span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={priceData} margin={{ top: 10, right: 10, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#64748b' }} interval={Math.max(1, Math.floor(priceData.length / 8))} />
          <YAxis tick={{ fontSize: 10, fill: '#64748b' }} domain={[minEquity * 0.95, maxEquity * 1.05]} tickFormatter={(v: number) => `¥${(v / 1000).toFixed(0)}k`} />
          <RechartsTooltip
            contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: '11px', color: '#e2e8f0' }}
            formatter={((value: unknown, name: string) => {
              if (name === 'equity') return [`¥${Number(value).toLocaleString()}`, '权益'];
              return [String(value), name];
            }) as never}
          />
          <Line type="monotone" dataKey="equity" stroke="#38bdf8" strokeWidth={2} dot={false} name="权益" />
          <ReferenceLine y={priceData[0]?.equity} stroke="#64748b" strokeDasharray="4 4" strokeWidth={1} />
        </ComposedChart>
      </ResponsiveContainer>

      {markers.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {markers.slice(-20).map((m, i) => (
            <div
              key={i}
              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[8px] font-mono ${
                m.type === 'buy' ? 'bg-green-400/10 text-green-400' : 'bg-red-400/10 text-red-400'
              }`}
              title={`${m.type === 'buy' ? '买入' : '卖出'} @ ${m.price.toFixed(2)} ${m.returnPct != null ? `${m.returnPct >= 0 ? '+' : ''}${m.returnPct.toFixed(2)}%` : ''}`}
            >
              {m.type === 'buy' ? '▲' : '▼'} {m.date} {m.price.toFixed(2)}
              {m.returnPct != null && <span className="opacity-70">{m.returnPct >= 0 ? '+' : ''}{m.returnPct.toFixed(1)}%</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
