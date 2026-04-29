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

interface V2Trade {
  size?: number;
  entryBar?: number;
  exitBar?: number;
  entryPrice?: number;
  exitPrice?: number;
  sl?: number;
  tp?: number;
  pnl?: number;
  returnPct?: number;
  entryTime?: string;
  exitTime?: string;
  duration?: string;
  tag?: string;
  exitReason?: string;
}

interface TradeDetailTableProps {
  trades: Trade[];
  v2Trades?: V2Trade[];
  maxItems?: number;
}

const ACTION_LABELS: Record<string, string> = { buy: '买入', sell: '卖出', hold: '持有' };
const ACTION_COLORS: Record<string, string> = { buy: 'text-success', sell: 'text-danger', hold: 'text-muted-text' };
const EXIT_LABELS: Record<string, string> = {
  take_profit: '止盈', partial_take_profit: '部分止盈', trailing_stop: '移动止损',
  stop_loss: '固定止损', signal_lost: '信号消失', fixed_days: '固定天数',
  max_hold_days: '最大持仓', force_close: '强制平仓', manual: '手动',
};

export function TradeDetailTable({ trades, v2Trades, maxItems = 50 }: TradeDetailTableProps) {
  const allTrades = v2Trades && v2Trades.length > 0 ? v2Trades : trades;
  const totalCount = (v2Trades || trades).length;
  const visible: (Trade | V2Trade)[] = allTrades.slice(0, maxItems);
  const isV2 = v2Trades && v2Trades.length > 0;

  if (visible.length === 0) {
    return (
      <div className="text-center py-4 text-xs text-muted-text">
        暂无交易记录
      </div>
    );
  }

  if (isV2) {
    return (
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-medium text-secondary-text">
            交易明细 ({Math.min(totalCount, maxItems)} 笔
            {totalCount > maxItems ? ` / 共 ${totalCount}` : ''})
          </span>
        </div>
        <div className="overflow-x-auto rounded-lg border border-border/30">
          <table className="w-full text-[10px]">
            <thead className="bg-border/10">
              <tr>
                <th className="text-left px-2 py-1.5 text-muted-text">入场</th>
                <th className="text-left px-2 py-1.5 text-muted-text">出场</th>
                <th className="text-right px-2 py-1.5 text-muted-text">入场价</th>
                <th className="text-right px-2 py-1.5 text-muted-text">出场价</th>
                <th className="text-right px-2 py-1.5 text-muted-text">盈亏</th>
                <th className="text-left px-2 py-1.5 text-muted-text">原因</th>
              </tr>
            </thead>
            <tbody>
              {(visible as V2Trade[]).map((t, i) => (
                <tr key={i} className="border-t border-border/10 hover:bg-border/5">
                  <td className="px-2 py-1 font-mono text-muted-text">{t.entryTime?.slice(0, 10) || t.entryBar || '--'}</td>
                  <td className="px-2 py-1 font-mono text-muted-text">{t.exitTime?.slice(0, 10) || t.exitBar || '--'}</td>
                  <td className={`px-2 py-1 font-mono text-right ${(t.size ?? 0) > 0 ? 'text-success' : 'text-danger'}`}>¥{t.entryPrice?.toFixed(2) || '--'}</td>
                  <td className="px-2 py-1 font-mono text-right">¥{t.exitPrice?.toFixed(2) || '--'}</td>
                  <td className={`px-2 py-1 font-mono text-right ${(t.returnPct ?? 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                    {(t.returnPct ?? 0) >= 0 ? '+' : ''}{t.returnPct?.toFixed(2)}%
                  </td>
                  <td className="px-2 py-1">
                    <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] ${
                      t.exitReason === 'take_profit' ? 'bg-success/10 text-success' : t.exitReason === 'trailing_stop' ? 'bg-warning/10 text-warning' : t.exitReason === 'stop_loss' ? 'bg-danger/10 text-danger' : 'bg-muted/10 text-muted-text'
                    }`}>
                      {EXIT_LABELS[t.exitReason || ''] || t.exitReason || '--'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-medium text-secondary-text">
          交易明细 ({Math.min(totalCount, maxItems)} 笔
          {totalCount > maxItems ? ` / 共 ${totalCount}` : ''})
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
            {visible.map((t, i) => {
              const trade = t as Trade;
              return (
                <tr key={i} className="border-t border-border/10 hover:bg-border/5">
                  <td className="px-2 py-1 font-mono text-muted-text">{trade.date}</td>
                  <td className="px-2 py-1 font-mono text-foreground">{trade.code}</td>
                  <td className={`px-2 py-1 text-center font-medium ${ACTION_COLORS[trade.action] || 'text-muted-text'}`}>
                    {ACTION_LABELS[trade.action] || trade.action}
                  </td>
                  <td className="px-2 py-1 font-mono text-right text-secondary-text">
                    ¥{trade.price?.toFixed(2) ?? '--'}
                  </td>
                  <td className="px-2 py-1 font-mono text-right text-muted-text">
                    {trade.shares > 0 ? trade.shares.toLocaleString() : '--'}
                  </td>
                  <td className="px-2 py-1 font-mono text-right text-muted-text">
                    {trade.cost > 0 ? `¥${trade.cost.toLocaleString()}` : '--'}
                  </td>
                  <td className="px-2 py-1 text-muted-text max-w-[120px] truncate">
                    {trade.reason || '--'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
