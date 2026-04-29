import { useState } from 'react';
import { Info } from 'lucide-react';

interface MetricExplanationCardProps {
  metricKey: string;
  nameCn: string;
  value: number | null | undefined;
  oneLiner: string;
  rating: { excellent: number; good: number; fair: number; poor: number };
  format?: 'pct' | 'num' | 'int';
}

function rateValue(val: number | null | undefined, rating: { excellent: number; good: number; fair: number; poor: number }): string {
  if (val == null) return 'text-muted-text';
  if (val >= rating.excellent) return 'text-success';
  if (val >= rating.good) return 'text-cyan';
  if (val >= rating.fair) return 'text-warning';
  return 'text-danger';
}

export function MetricExplanationCard({
  nameCn, value, oneLiner, rating, format = 'num',
}: MetricExplanationCardProps) {
  const [open, setOpen] = useState(false);
  const valStr = value == null ? '--' : format === 'pct' ? `${value >= 0 ? '+' : ''}${value.toFixed(2)}%` : format === 'int' ? String(Math.round(value)) : value.toFixed(3);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex flex-col items-center gap-0.5 px-3 py-2 rounded-xl bg-card/50 border border-border/30 hover:border-cyan/20 transition-colors w-full text-left group"
      >
        <div className="flex items-center gap-1">
          <span className={`text-lg font-bold tabular-nums ${rateValue(value, rating)}`}>{valStr}</span>
          <Info className="h-3 w-3 text-muted-text/40 group-hover:text-cyan/60 transition-colors" />
        </div>
        <span className="text-[10px] text-muted-text">{nameCn}</span>
      </button>
      {open && (
        <div className="absolute z-20 top-full mt-1 left-0 right-0 rounded-lg bg-card border border-border/30 shadow-lg p-2.5 animate-fade-in">
          <p className="text-[10px] text-secondary-text leading-relaxed">{oneLiner}</p>
          <div className="mt-1.5 flex gap-1 text-[8px]">
            <span className="px-1.5 py-0.5 bg-success/10 text-success rounded">优秀 ≥{rating.excellent}</span>
            <span className="px-1.5 py-0.5 bg-cyan/10 text-cyan rounded">良好 ≥{rating.good}</span>
            <span className="px-1.5 py-0.5 bg-warning/10 text-warning rounded">一般 ≥{rating.fair}</span>
          </div>
        </div>
      )}
    </div>
  );
}
