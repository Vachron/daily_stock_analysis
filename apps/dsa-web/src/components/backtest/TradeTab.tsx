import { useState, useMemo } from 'react';
import { TrendingUp, TrendingDown, Search, Filter } from 'lucide-react';

interface Trade {
  date: string;
  code: string;
  action: string;
  shares: number;
  price: number;
  cost: number;
  reason: string;
}

interface TradeTabProps {
  trades: Trade[];
}

const ACTION_LABELS: Record<string, string> = { buy: '买入', sell: '卖出', hold: '持有' };
const ACTION_COLORS: Record<string, string> = { buy: 'text-success', sell: 'text-danger', hold: 'text-muted-text' };

export function TradeTab({ trades }: TradeTabProps) {
  const [filterAction, setFilterAction] = useState<string>('all');
  const [searchCode, setSearchCode] = useState('');
  const [visibleCount, setVisibleCount] = useState(50);

  const filtered = useMemo(() => {
    let result = trades;
    if (filterAction !== 'all') {
      result = result.filter(t => t.action === filterAction);
    }
    if (searchCode.trim()) {
      const upper = searchCode.trim().toUpperCase();
      result = result.filter(t => t.code?.toUpperCase().includes(upper));
    }
    return result;
  }, [trades, filterAction, searchCode]);

  const visible = filtered.slice(0, visibleCount);
  const buyCount = trades.filter(t => t.action === 'buy').length;
  const sellCount = trades.filter(t => t.action === 'sell').length;

  if (trades.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-text gap-2">
        <Filter className="h-8 w-8" />
        <span className="text-xs">暂无交易记录</span>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1 rounded-lg bg-border/10 p-0.5">
          <button
            onClick={() => setFilterAction('all')}
            className={`px-2 py-0.5 rounded text-[10px] font-medium transition-all ${filterAction === 'all' ? 'bg-cyan/20 text-cyan' : 'text-muted-text hover:text-secondary-text'}`}
          >
            全部 ({trades.length})
          </button>
          <button
            onClick={() => setFilterAction('buy')}
            className={`px-2 py-0.5 rounded text-[10px] font-medium transition-all flex items-center gap-0.5 ${filterAction === 'buy' ? 'bg-success/20 text-success' : 'text-muted-text hover:text-secondary-text'}`}
          >
            <TrendingUp className="h-2.5 w-2.5" />买入 ({buyCount})
          </button>
          <button
            onClick={() => setFilterAction('sell')}
            className={`px-2 py-0.5 rounded text-[10px] font-medium transition-all flex items-center gap-0.5 ${filterAction === 'sell' ? 'bg-danger/20 text-danger' : 'text-muted-text hover:text-secondary-text'}`}
          >
            <TrendingDown className="h-2.5 w-2.5" />卖出 ({sellCount})
          </button>
        </div>
        <div className="relative flex-1 min-w-[120px]">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-text" />
          <input
            type="text"
            value={searchCode}
            onChange={e => setSearchCode(e.target.value.toUpperCase())}
            placeholder="搜索代码..."
            className="pl-6 pr-2 py-1 rounded-md bg-border/10 text-[10px] text-foreground border border-border/20 w-full focus:outline-none focus:border-cyan/30"
          />
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border/20">
        <table className="w-full text-[10px]">
          <thead className="bg-border/10">
            <tr>
              <th className="text-left px-2 py-1.5 text-muted-text font-medium">日期</th>
              <th className="text-left px-2 py-1.5 text-muted-text font-medium">代码</th>
              <th className="text-center px-2 py-1.5 text-muted-text font-medium">方向</th>
              <th className="text-right px-2 py-1.5 text-muted-text font-medium">价格</th>
              <th className="text-right px-2 py-1.5 text-muted-text font-medium">数量</th>
              <th className="text-right px-2 py-1.5 text-muted-text font-medium">金额</th>
              <th className="text-left px-2 py-1.5 text-muted-text font-medium hidden sm:table-cell">原因</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((t, i) => (
              <tr key={i} className="border-t border-border/10 hover:bg-border/5">
                <td className="px-2 py-1 font-mono text-muted-text">{t.date?.slice(0, 10)}</td>
                <td className="px-2 py-1 font-mono text-foreground">{t.code}</td>
                <td className={`px-2 py-1 text-center font-medium ${ACTION_COLORS[t.action] || 'text-muted-text'}`}>
                  {ACTION_LABELS[t.action] || t.action}
                </td>
                <td className="px-2 py-1 font-mono text-right text-secondary-text">¥{t.price?.toFixed(2) ?? '--'}</td>
                <td className="px-2 py-1 font-mono text-right text-muted-text">{t.shares > 0 ? t.shares.toLocaleString() : '--'}</td>
                <td className="px-2 py-1 font-mono text-right text-muted-text">¥{t.cost > 0 ? t.cost.toLocaleString() : '--'}</td>
                <td className="px-2 py-1 text-muted-text hidden sm:table-cell max-w-[140px] truncate">{t.reason || '--'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {filtered.length > visibleCount && (
        <div className="text-center">
          <button
            onClick={() => setVisibleCount(prev => prev + 50)}
            className="text-[10px] text-cyan hover:text-cyan/80 transition-colors"
          >
            显示更多 (剩余 {filtered.length - visibleCount} 笔)
          </button>
        </div>
      )}

      {filtered.length === 0 && (
        <div className="text-center py-4 text-[10px] text-muted-text">无匹配记录</div>
      )}
    </div>
  );
}
