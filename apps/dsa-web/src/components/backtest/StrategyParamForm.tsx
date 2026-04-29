import type { StrategyFactor } from '../../types/backtest';

interface StrategyParamFormProps {
  factors: StrategyFactor[];
  values: Record<string, number>;
  onChange: (id: string, value: number) => void;
  disabled?: boolean;
}

export function StrategyParamForm({ factors, values, onChange, disabled }: StrategyParamFormProps) {
  if (factors.length === 0) {
    return (
      <div className="text-center py-3 text-[10px] text-muted-text">
        该策略无可调参数
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <span className="text-[10px] font-medium text-secondary-text">策略参数</span>
      {factors.map((f) => {
        const currentVal = values[f.id] ?? f.default;
        const minVal = Math.min(...f.range);
        const maxVal = Math.max(...f.range);
        const step = f.step || ((maxVal - minVal) / 20);
        const isDefault = currentVal === f.default;

        return (
          <div key={f.id} className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-text">{f.displayName}</span>
              <div className="flex items-center gap-1">
                <span className="text-[10px] font-mono tabular-nums text-foreground">
                  {f.type === 'int' ? Math.round(currentVal) : currentVal.toFixed(1)}
                </span>
                {!isDefault && (
                  <button
                    type="button"
                    onClick={() => onChange(f.id, f.default)}
                    className="text-[9px] text-cyan hover:underline"
                  >
                    重置
                  </button>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-muted-text w-6 text-right tabular-nums">{minVal}</span>
              <input
                type="range"
                min={minVal}
                max={maxVal}
                step={step}
                value={currentVal}
                onChange={(e) => onChange(f.id, parseFloat(e.target.value))}
                disabled={disabled}
                className="flex-1 h-1.5 accent-cyan cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
              />
              <span className="text-[9px] text-muted-text w-6 tabular-nums">{maxVal}</span>
            </div>
            {f.type === 'int' && (
              <input
                type="number"
                value={Math.round(currentVal)}
                onChange={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (!isNaN(v)) onChange(f.id, Math.max(minVal, Math.min(maxVal, v)));
                }}
                disabled={disabled}
                className="w-full h-7 rounded-lg border border-border/30 bg-transparent px-2 text-[10px] text-center focus:outline-none focus:border-cyan/50 disabled:opacity-50"
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
