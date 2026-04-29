import { useState, useEffect } from 'react';
import { Zap } from 'lucide-react';
import type { PresetInfo } from '../../types/backtest';
import { backtestApi } from '../../api/backtest';

interface PresetSelectorProps {
  value: string | null;
  onChange: (presetName: string | null) => void;
  disabled?: boolean;
}

const ACTIVITY_LABELS: Record<string, string> = {
  low: '低波动',
  medium: '中等波动',
  high: '高波动',
  extreme: '极端波动',
};

const SIZE_LABELS: Record<string, string> = {
  large: '大盘',
  mid: '中盘',
  small: '小盘',
  micro: '微盘',
};

export function PresetSelector({ value, onChange, disabled }: PresetSelectorProps) {
  const [presets, setPresets] = useState<PresetInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    backtestApi.getPresets().then((res) => {
      setPresets(res.items);
    }).catch(() => {
      setPresets([]);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-2 animate-pulse">
        <div className="h-6 bg-muted/20 rounded w-1/3" />
        <div className="grid grid-cols-2 gap-1">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-12 bg-muted/20 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  const selected = presets.find((p) => p.name === value);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-medium text-secondary-text">参数预设</span>
        <button
          type="button"
          onClick={() => onChange(null)}
          disabled={disabled || !value}
          className="text-[9px] text-muted-text hover:text-foreground disabled:opacity-30"
        >
          不使用预设
        </button>
      </div>

      <div className="grid grid-cols-2 gap-1 max-h-44 overflow-y-auto rounded-lg border border-border/20 p-1">
        {presets.map((p) => {
          const isActive = p.name === value;
          return (
            <button
              key={p.name}
              type="button"
              onClick={() => onChange(p.name === value ? null : p.name)}
              disabled={disabled}
              className={`text-left px-2 py-1.5 rounded-lg transition-colors ${
                isActive
                  ? 'bg-cyan/10 border border-cyan/20'
                  : 'hover:bg-muted/10 border border-transparent'
              }`}
            >
              <div className="flex items-center gap-1">
                <Zap className={`h-2.5 w-2.5 ${isActive ? 'text-cyan' : 'text-muted-text'}`} />
                <span className={`text-[10px] font-medium ${isActive ? 'text-cyan' : 'text-foreground'}`}>
                  {p.displayName}
                </span>
              </div>
              <div className="flex items-center gap-1 mt-0.5">
                <span className="text-[8px] text-muted-text bg-muted/20 px-1 rounded">
                  {ACTIVITY_LABELS[p.activityLevel] || p.activityLevel}
                </span>
                <span className="text-[8px] text-muted-text bg-muted/20 px-1 rounded">
                  {SIZE_LABELS[p.capSize] || p.capSize}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {selected && (
        <div className="text-[9px] text-muted-text grid grid-cols-2 gap-x-4 gap-y-0.5 bg-muted/5 rounded-lg p-2">
          <div className="flex justify-between"><span>概率阈值</span><span className="text-secondary-text">{selected.threshold}</span></div>
          <div className="flex justify-between"><span>仓位模式</span><span className="text-secondary-text">{selected.positionSizing}</span></div>
          {selected.trailingStopPct != null && (
            <div className="flex justify-between"><span>移动止损</span><span className="text-secondary-text">{selected.trailingStopPct}%</span></div>
          )}
          {selected.takeProfitPct != null && (
            <div className="flex justify-between"><span>目标止盈</span><span className="text-secondary-text">{selected.takeProfitPct}%</span></div>
          )}
          {selected.stopLossPct != null && (
            <div className="flex justify-between"><span>固定止损</span><span className="text-secondary-text">{selected.stopLossPct}%</span></div>
          )}
          {selected.maxHoldDays != null && (
            <div className="flex justify-between"><span>最大持仓</span><span className="text-secondary-text">{selected.maxHoldDays}天</span></div>
          )}
        </div>
      )}
    </div>
  );
}
