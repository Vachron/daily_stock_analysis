import { useState } from 'react';
import { Zap, TrendingUp, TrendingDown, ChevronDown, ChevronUp } from 'lucide-react';

interface ParamImpactProps {
  paramName: string;
  currentValue: number;
  originalValue: number;
  originalStats: Record<string, number>;
  newStats: Record<string, number>;
  loading?: boolean;
  onRerun: () => void;
  onCompare: () => void;
}

interface ImpactRow {
  label: string;
  key: string;
  format: 'pct' | 'num' | 'int';
}

const IMPACT_ROWS: ImpactRow[] = [
  { label: '交易次数', key: 'tradeCount', format: 'int' },
  { label: '胜率', key: 'winRatePct', format: 'pct' },
  { label: '最大回撤', key: 'maxDrawdownPct', format: 'pct' },
  { label: '总收益', key: 'returnPct', format: 'pct' },
  { label: '夏普比率', key: 'sharpeRatio', format: 'num' },
  { label: '盈亏比', key: 'profitFactor', format: 'num' },
];

function fmtVal(val: number | null | undefined, format: string): string {
  if (val == null) return '--';
  if (format === 'pct') return `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`;
  if (format === 'int') return String(Math.round(val));
  return val.toFixed(3);
}

export function ParamImpactPanel({
  paramName, currentValue, originalValue, originalStats, newStats, loading, onRerun, onCompare,
}: ParamImpactProps) {
  const [open, setOpen] = useState(false);

  const hasChange = currentValue !== originalValue;

  if (!hasChange && Object.keys(originalStats).length === 0) return null;

  return (
    <div className="rounded-xl bg-card/30 border border-border/20">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between p-3 text-left"
      >
        <div className="flex items-center gap-2">
          <Zap className="h-3.5 w-3.5 text-warning" />
          <span className="text-xs font-medium text-foreground">⚙️ 参数影响预览</span>
          <span className="text-[9px] text-muted-text">
            {paramName}: {originalValue} → {currentValue}
          </span>
        </div>
        {open ? <ChevronUp className="h-3.5 w-3.5 text-muted-text" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-text" />}
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-3 animate-fade-in">
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead>
                <tr className="border-b border-border/20">
                  <th className="text-left py-1.5 px-2 text-muted-text">指标</th>
                  <th className="text-right py-1.5 px-2 text-muted-text">原值({originalValue})</th>
                  <th className="text-right py-1.5 px-2 text-muted-text">新值({currentValue})</th>
                  <th className="text-right py-1.5 px-2 text-muted-text">变化</th>
                </tr>
              </thead>
              <tbody>
                {IMPACT_ROWS.map((row) => {
                  const orig = originalStats[row.key];
                  const now = newStats[row.key];
                  const delta = orig != null && now != null ? Number(now) - Number(orig) : undefined;
                  return (
                    <tr key={row.key} className="border-b border-border/10">
                      <td className="py-1.5 px-2 text-secondary-text">{row.label}</td>
                      <td className="py-1.5 px-2 text-right font-mono tabular-nums text-muted-text">
                        {fmtVal(orig as number | undefined, row.format)}
                      </td>
                      <td className="py-1.5 px-2 text-right font-mono tabular-nums text-foreground">
                        {fmtVal(now as number | undefined, row.format)}
                      </td>
                      <td className={`py-1.5 px-2 text-right font-mono tabular-nums flex items-center gap-0.5 justify-end ${
                        delta != null ? (delta > 0 ? 'text-success' : delta < 0 ? 'text-danger' : 'text-muted-text') : 'text-muted-text'
                      }`}>
                        {delta != null ? (
                          <>{delta > 0 ? <TrendingUp className="h-2.5 w-2.5" /> : delta < 0 ? <TrendingDown className="h-2.5 w-2.5" /> : null}
                          {delta > 0 ? '+' : ''}{row.format === 'pct' ? delta.toFixed(2) + '%' : row.format === 'int' ? Math.round(delta) : delta.toFixed(3)}</>
                        ) : '--'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {currentValue < originalValue && paramName.includes('止损') && (
            <p className="text-[9px] text-warning/80">
              ⚠️ 更紧的止损会减少单笔亏损，但可能增加止损触发频率。建议在 {currentValue}%-{originalValue}% 之间做网格搜索找最优平衡点。
            </p>
          )}
          {currentValue > originalValue && paramName.includes('止损') && (
            <p className="text-[9px] text-cyan/80">
              💡 更宽松的止损容忍更大的回撤，但可能让盈利仓位跑得更远。
            </p>
          )}

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onRerun}
              disabled={loading}
              className="px-3 py-1 rounded-lg bg-cyan/10 border border-cyan/20 text-cyan text-[10px] hover:bg-cyan/20 transition-colors disabled:opacity-50"
            >
              {loading ? '计算中...' : '▶ 用新参数重新回测'}
            </button>
            <button
              type="button"
              onClick={onCompare}
              className="px-3 py-1 rounded-lg border border-border/20 text-muted-text text-[10px] hover:text-foreground transition-colors"
            >
              📋 对比两次结果
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
