import { useState, useEffect } from 'react';
import { Search, ChevronDown } from 'lucide-react';
import type { StrategyInfo } from '../../types/backtest';
import { backtestApi } from '../../api/backtest';
import { Badge } from '../common';

interface StrategySelectorProps {
  value: string;
  onChange: (strategyName: string) => void;
  disabled?: boolean;
}

const CATEGORY_LABELS: Record<string, string> = {
  trend: '趋势',
  momentum: '动量',
  reversal: '反转',
  pattern: '形态',
  volume: '量价',
  framework: '框架',
  oscillator: '震荡',
};

export function StrategySelector({ value, onChange, disabled }: StrategySelectorProps) {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  useEffect(() => {
    backtestApi.getStrategies().then((res) => {
      setStrategies(res.items);
    }).catch(() => {
      setStrategies([]);
    }).finally(() => setLoading(false));
  }, []);

  const categories = [...new Set(strategies.map((s) => s.category))];

  const filtered = strategies.filter((s) => {
    if (selectedCategory && s.category !== selectedCategory) return false;
    if (search && !s.displayName.includes(search) && !s.name.includes(search)) return false;
    return true;
  });

  const selected = strategies.find((s) => s.name === value);

  if (loading) {
    return (
      <div className="space-y-2 animate-pulse">
        <div className="h-8 bg-muted/20 rounded-lg" />
        <div className="h-8 bg-muted/20 rounded-lg w-3/4" />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1 mb-1 overflow-x-auto">
        <button
          type="button"
          onClick={() => setSelectedCategory(null)}
          className={`px-2 py-0.5 rounded text-[10px] transition-colors whitespace-nowrap ${
            !selectedCategory ? 'bg-cyan/10 text-cyan' : 'text-muted-text hover:text-foreground'
          }`}
        >
          全部
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            type="button"
            onClick={() => setSelectedCategory(cat === selectedCategory ? null : cat)}
            className={`px-2 py-0.5 rounded text-[10px] transition-colors whitespace-nowrap ${
              cat === selectedCategory ? 'bg-cyan/10 text-cyan' : 'text-muted-text hover:text-foreground'
            }`}
          >
            {CATEGORY_LABELS[cat] || cat}
          </button>
        ))}
      </div>

      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-text" />
        <input
          type="text"
          placeholder="搜索策略..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full h-8 pl-7 pr-3 rounded-lg border border-border/30 bg-transparent text-xs focus:outline-none focus:border-cyan/50 disabled:opacity-50"
          disabled={disabled}
        />
      </div>

      <div className="max-h-52 overflow-y-auto space-y-0.5 rounded-lg border border-border/20 p-1">
        {filtered.length === 0 ? (
          <div className="text-center py-4 text-xs text-muted-text">无匹配策略</div>
        ) : (
          filtered.map((s) => (
            <button
              key={s.name}
              type="button"
              onClick={() => onChange(s.name)}
              disabled={disabled}
              className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                s.name === value
                  ? 'bg-cyan/10 border border-cyan/20'
                  : 'hover:bg-muted/10 border border-transparent'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className={`text-xs font-medium ${s.name === value ? 'text-cyan' : 'text-foreground'}`}>
                  {s.displayName}
                </span>
                <Badge variant="default" className="text-[9px]">
                  {CATEGORY_LABELS[s.category] || s.category}
                </Badge>
              </div>
              <p className="text-[10px] text-muted-text mt-0.5 line-clamp-1">
                {s.description}
              </p>
            </button>
          ))
        )}
      </div>

      {selected && (
        <details className="text-[10px] text-muted-text bg-muted/5 rounded-lg p-2">
          <summary className="cursor-pointer hover:text-foreground flex items-center gap-1">
            <ChevronDown className="h-3 w-3" />
            {selected.displayName} 因子
          </summary>
          <div className="mt-1 space-y-0.5">
            {selected.factors.map((f) => (
              <div key={f.id} className="flex justify-between">
                <span>{f.displayName}</span>
                <span className="font-mono text-secondary-text">
                  {f.default} ({f.type} [{f.range[0]}~{f.range[f.range.length - 1]}])
                </span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
