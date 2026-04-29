import { useState } from 'react';
import type { StrategyFactor, OptimizeRequest } from '../../types/backtest';

interface OptimizeConfigFormProps {
  factors: StrategyFactor[];
  defaultRanges: Record<string, number[]>;
  onRun: (params: OptimizeRequest) => void;
  loading?: boolean;
  disabled?: boolean;
}

export function OptimizeConfigForm({ factors, defaultRanges, onRun, loading, disabled }: OptimizeConfigFormProps) {
  const [enabledFactors, setEnabledFactors] = useState<Set<string>>(new Set(factors.slice(0, 2).map((f) => f.id)));
  const [maximize, setMaximize] = useState('Sharpe Ratio');
  const [method, setMethod] = useState<'grid' | 'bayesian'>('grid');
  const [maxTries, setMaxTries] = useState(200);

  const toggleFactor = (id: string) => {
    setEnabledFactors((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const handleRun = () => {
    const activeFactors = factors.filter((f) => enabledFactors.has(f.id));
    const ranges: Record<string, number[]> = {};
    for (const f of activeFactors) {
      ranges[f.id] = defaultRanges[f.id] || [f.range[0], f.range[f.range.length - 1]];
    }
    onRun({
      strategy: '',
      codes: [],
      maximize,
      method,
      maxTries,
      factorRanges: ranges,
    });
  };

  return (
    <div className="space-y-3">
      <span className="text-[10px] font-medium text-secondary-text">参数优化配置</span>

      <div className="space-y-1.5">
        <p className="text-[9px] text-muted-text">选择要优化的参数：</p>
        {factors.map((f) => (
          <div key={f.id} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={enabledFactors.has(f.id)}
              onChange={() => toggleFactor(f.id)}
              disabled={disabled}
              className="rounded accent-cyan"
            />
            <span className="text-[10px] text-muted-text flex-1">{f.displayName}</span>
            <span className="text-[9px] text-muted-text/60 font-mono">
              [{f.range[0]}~{f.range[f.range.length - 1]}] 步长 {f.step}
            </span>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="flex flex-col gap-1">
          <label className="text-[9px] text-muted-text">优化目标</label>
          <select
            value={maximize}
            onChange={(e) => setMaximize(e.target.value)}
            disabled={disabled}
            className="h-7 rounded-lg border border-border/30 bg-transparent px-2 text-[10px] focus:outline-none focus:border-cyan/50"
          >
            <option>Sharpe Ratio</option>
            <option>Return [%]</option>
            <option>Sortino Ratio</option>
            <option>Calmar Ratio</option>
            <option>Win Rate [%]</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[9px] text-muted-text">优化方法</label>
          <select
            value={method}
            onChange={(e) => setMethod(e.target.value as 'grid' | 'bayesian')}
            disabled={disabled}
            className="h-7 rounded-lg border border-border/30 bg-transparent px-2 text-[10px] focus:outline-none focus:border-cyan/50"
          >
            <option value="grid">网格搜索</option>
            <option value="bayesian">贝叶斯优化</option>
          </select>
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-[9px] text-muted-text">最大尝试次数</label>
        <input
          type="number"
          value={maxTries}
          onChange={(e) => setMaxTries(parseInt(e.target.value, 10) || 200)}
          disabled={disabled}
          min={10}
          max={2000}
          className="h-7 w-24 rounded-lg border border-border/30 bg-transparent px-2 text-[10px] text-center focus:outline-none focus:border-cyan/50"
        />
      </div>

      <button
        type="button"
        onClick={handleRun}
        disabled={disabled || loading || enabledFactors.size === 0}
        className="w-full py-2 rounded-lg bg-cyan/10 border border-cyan/20 text-cyan text-xs font-medium hover:bg-cyan/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? '优化中...' : `开始优化 (${enabledFactors.size} 个参数)`}
      </button>
    </div>
  );
}
