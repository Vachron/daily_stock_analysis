import { Sliders } from 'lucide-react';
import { useState, useEffect } from 'react';
import apiClient from '../../api/index';

interface FactorDef {
  id: string;
  display_name: string;
  type: string;
  default: number;
  current: number;
  range: number[];
  step: number;
}

interface StrategyFactorGroup {
  name: string;
  display_name: string;
  category: string;
  description: string;
  weight: number;
  factors: FactorDef[];
}

interface AlphaFactorPanelProps {
  onClose: () => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  trend: 'border-l-cyan',
  reversal: 'border-l-purple',
  volume_price: 'border-l-amber',
  pattern: 'border-l-emerald',
};

export function AlphaFactorPanel({ onClose }: AlphaFactorPanelProps) {
  const [data, setData] = useState<StrategyFactorGroup[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [totals, setTotals] = useState({ strategies: 0, factors: 0 });

  useEffect(() => {
    apiClient.get<Record<string, unknown>>('/api/v1/alpha/factors').then(r => {
      const strategies = (r.data?.strategies || []) as StrategyFactorGroup[];
      setData(strategies);
      setTotals({
        strategies: (r.data?.total_strategies as number) || 0,
        factors: (r.data?.total_factors as number) || 0,
      });
    }).catch(() => {}).finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-md bg-card border-l border-border h-full overflow-y-auto shadow-2xl animate-fade-in"
        onClick={e => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-card/95 backdrop-blur px-4 py-3 border-b border-border/50 flex items-center justify-between z-10">
          <div>
            <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <Sliders className="h-4 w-4 text-amber" />策略因子参数
            </h2>
            <p className="text-[10px] text-muted-text mt-0.5">
              {totals.strategies} 个策略 · {totals.factors} 个可调因子
            </p>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-hover transition-colors text-muted-text">
            ✕
          </button>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-12 text-secondary-text text-xs">
            加载中...
          </div>
        )}

        <div className="px-4 py-3 space-y-4">
          {data.map((strategy) => (
            <div key={strategy.name} className="rounded-xl border border-border/30 bg-card/50 overflow-hidden">
              <div className={`border-l-2 ${CATEGORY_COLORS[strategy.category] || 'border-l-muted'} px-3 py-2.5`}>
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-xs font-medium text-foreground">{strategy.display_name}</span>
                    <span className="ml-1.5 text-[10px] text-muted-text">{strategy.name}</span>
                  </div>
                  <span className="text-[10px] text-muted-text">
                    权重 {(strategy.weight || 1).toFixed(2)}
                  </span>
                </div>
                <p className="text-[10px] text-muted-text mt-0.5">{strategy.description}</p>
              </div>

              {strategy.factors.map((factor) => {
                const rangeSpan = factor.range[1] - factor.range[0];
                const pct = rangeSpan > 0
                  ? ((factor.current - factor.range[0]) / rangeSpan) * 100
                  : 50;
                const isDefault = Math.abs(factor.current - factor.default) < 0.001;
                const isOptimized = !isDefault;

                return (
                  <div key={factor.id} className="px-3 py-2 border-t border-border/10">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1">
                        <span className="text-[11px] text-secondary-text">{factor.display_name}</span>
                        <span className="text-[10px] text-muted-text">({factor.id})</span>
                        {isOptimized && (
                          <span className="text-[9px] text-amber bg-amber/10 px-1 rounded">已优化</span>
                        )}
                      </div>
                      <span className="text-[11px] font-mono tabular-nums text-foreground">
                        {factor.current.toFixed(2)}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[9px] font-mono text-muted-text w-8 text-right">
                        {factor.range[0].toFixed(1)}
                      </span>
                      <div className="flex-1 h-1.5 rounded-full bg-border/20 overflow-hidden relative">
                        <div
                          className="absolute h-full rounded-full bg-amber/50"
                          style={{ width: `${pct}%` }}
                        />
                        <div
                          className="absolute top-0 h-full w-0.5 bg-foreground"
                          style={{ left: `${((factor.default - factor.range[0]) / rangeSpan) * 100}%` }}
                          title={`默认值: ${factor.default}`}
                        />
                      </div>
                      <span className="text-[9px] font-mono text-muted-text w-8">
                        {factor.range[1].toFixed(1)}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 mt-0.5">
                      <span className="text-[9px] text-muted-text">
                        默认: {factor.default.toFixed(2)}
                      </span>
                      {factor.step > 0 && (
                        <span className="text-[9px] text-muted-text">步长: {factor.step}</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}

          {!isLoading && data.length === 0 && (
            <div className="text-xs text-muted-text text-center py-8">
              暂无因子数据
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
