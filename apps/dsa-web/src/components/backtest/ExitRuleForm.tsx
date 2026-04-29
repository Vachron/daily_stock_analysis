import type { ExitRuleConfig } from '../../types/backtest';
import { Checkbox } from '../common';

interface ExitRuleFormProps {
  value: ExitRuleConfig;
  onChange: (value: ExitRuleConfig) => void;
  disabled?: boolean;
}

const INPUT_CLS = 'h-7 w-16 rounded-lg border border-border/30 bg-transparent px-2 text-[10px] text-right focus:outline-none focus:border-cyan/50 disabled:opacity-50';

export function ExitRuleForm({ value, onChange, disabled }: ExitRuleFormProps) {
  const set = (key: keyof ExitRuleConfig, val: unknown) => {
    onChange({ ...value, [key]: val });
  };

  return (
    <div className="space-y-2">
      <span className="text-[10px] font-medium text-secondary-text">平仓规则</span>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Checkbox
              checked={value.trailingStopPct != null}
              onChange={(c) => set('trailingStopPct', c ? 5 : undefined)}
              disabled={disabled}
            />
            <span className="text-[10px] text-muted-text">移动止损</span>
            <span className="text-[8px] text-muted-text/60">从最高点回撤</span>
          </div>
          <input
            type="number"
            value={value.trailingStopPct ?? ''}
            onChange={(e) => set('trailingStopPct', e.target.value ? parseFloat(e.target.value) : undefined)}
            disabled={disabled || value.trailingStopPct == null}
            placeholder="5"
            className={INPUT_CLS}
          />
          <span className="text-[9px] text-muted-text">%</span>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Checkbox
              checked={value.takeProfitPct != null}
              onChange={(c) => set('takeProfitPct', c ? 10 : undefined)}
              disabled={disabled}
            />
            <span className="text-[10px] text-muted-text">目标止盈</span>
          </div>
          <input
            type="number"
            value={value.takeProfitPct ?? ''}
            onChange={(e) => set('takeProfitPct', e.target.value ? parseFloat(e.target.value) : undefined)}
            disabled={disabled || value.takeProfitPct == null}
            placeholder="10"
            className={INPUT_CLS}
          />
          <span className="text-[9px] text-muted-text">%</span>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Checkbox
              checked={value.stopLossPct != null}
              onChange={(c) => set('stopLossPct', c ? 3 : undefined)}
              disabled={disabled}
            />
            <span className="text-[10px] text-muted-text">固定止损</span>
          </div>
          <input
            type="number"
            value={value.stopLossPct ?? ''}
            onChange={(e) => set('stopLossPct', e.target.value ? parseFloat(e.target.value) : undefined)}
            disabled={disabled || value.stopLossPct == null}
            placeholder="3"
            className={INPUT_CLS}
          />
          <span className="text-[9px] text-muted-text">%</span>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Checkbox
              checked={value.maxHoldDays != null}
              onChange={(c) => set('maxHoldDays', c ? 10 : undefined)}
              disabled={disabled}
            />
            <span className="text-[10px] text-muted-text">最大持仓</span>
          </div>
          <input
            type="number"
            value={value.maxHoldDays ?? ''}
            onChange={(e) => set('maxHoldDays', e.target.value ? parseInt(e.target.value, 10) : undefined)}
            disabled={disabled || value.maxHoldDays == null}
            placeholder="10"
            className={INPUT_CLS}
          />
          <span className="text-[9px] text-muted-text">天</span>
        </div>

        {value.takeProfitPct != null && (
          <div className="flex items-center justify-between pl-5">
            <div className="flex items-center gap-1.5">
              <Checkbox
                checked={value.partialExitEnabled ?? false}
                onChange={(c) => set('partialExitEnabled', c)}
                disabled={disabled}
              />
              <span className="text-[9px] text-muted-text">部分止盈</span>
            </div>
            <input
              type="number"
              value={value.partialExitPct ? value.partialExitPct * 100 : 50}
              onChange={(e) => set('partialExitPct', parseFloat(e.target.value) / 100)}
              disabled={disabled || !value.partialExitEnabled}
              className={INPUT_CLS}
            />
            <span className="text-[9px] text-muted-text">%平仓</span>
          </div>
        )}
      </div>
    </div>
  );
}
