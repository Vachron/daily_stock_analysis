import type React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface Trade {
  date: string;
  code: string;
  action: string;
  shares: number;
  price: number;
  cost: number;
  reason: string;
}

interface TradeDetailTableProps {
  trades: Trade[];
  maxItems?: number;
}

const ACTION_LABELS: Record<string, string> = { buy: '买入', sell: '卖出', hold: '持有' };
const ACTION_COLORS: Record<string, string> = { buy: 'text-success', sell: 'text-danger', hold: 'text-muted-text' };

export function TradeDetailTable({ trades, maxItems = 50 }: TradeDetailTableProps) {
  const visible = trades.slice(0, maxItems);

  if (visible.length === 0) {
    return (
      <div className="text-center py-4 text-xs text-muted-text">
        暂无交易记录
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-medium text-secondary-text">
          交易明细 ({Math.min(trades.length, maxItems)} 笔
          {trades.length > maxItems ? ` / 共 ${trades.length}` : ''})
        </span>
        <div className="flex items-center gap-3 text-[9px] text-muted-text">
          <span className="flex items-center gap-0.5"><TrendingUp className="h-2.5 w-2.5 text-success" />买入</span>
          <span className="flex items-center gap-0.5"><TrendingDown className="h-2.5 w-2.5 text-danger" />卖出</span>
        </div>
      </div>
      <div className="overflow-x-auto rounded-lg border border-border/30">
        <table className="w-full text-[10px]">
          <thead className="bg-border/10">
            <tr>
              <th className="text-left px-2 py-1.5 text-muted-text font-medium">日期</th>
              <th className="text-left px-2 py-1.5 text-muted-text font-medium">代码</th>
              <th className="text-center px-2 py-1.5 text-muted-text font-medium">方向</th>
              <th className="text-right px-2 py-1.5 text-muted-text font-medium">价格</th>
              <th className="text-right px-2 py-1.5 text-muted-text font-medium">数量</th>
              <th className="text-right px-2 py-1.5 text-muted-text font-medium">金额</th>
              <th className="text-left px-2 py-1.5 text-muted-text font-medium">原因</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((t, i) => (
              <tr key={i} className="border-t border-border/10 hover:bg-border/5">
                <td className="px-2 py-1 font-mono text-muted-text">{t.date}</td>
                <td className="px-2 py-1 font-mono text-foreground">{t.code}</td>
                <td className={`px-2 py-1 text-center font-medium ${ACTION_COLORS[t.action] || 'text-muted-text'}`}>
                  {ACTION_LABELS[t.action] || t.action}
                </td>
                <td className="px-2 py-1 font-mono text-right text-secondary-text">
                  ¥{t.price?.toFixed(2) ?? '--'}
                </td>
                <td className="px-2 py-1 font-mono text-right text-muted-text">
                  {t.shares > 0 ? t.shares.toLocaleString() : '--'}
                </td>
                <td className="px-2 py-1 font-mono text-right text-muted-text">
                  {t.cost > 0 ? `¥${t.cost.toLocaleString()}` : '--'}
                </td>
                <td className="px-2 py-1 text-muted-text max-w-[120px] truncate">
                  {t.reason || '--'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
