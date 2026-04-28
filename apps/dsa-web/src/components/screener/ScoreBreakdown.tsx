import { Loader2, ChevronUp } from 'lucide-react';
import type { CategoryBreakdown } from '../../types/screener';

export interface ScoreBreakdownData {
  code: string;
  name: string;
  score: number;
  price: number;
  marketCap: number;
  turnoverRate: number;
  peRatio: number | null;
  qualityTier: string;
  baseScore: {
    total: number;
    max: number;
    components: Record<string, { score: string; raw: number }>;
  };
  strategyBreakdown: {
    fusionScore: number;
    strategyAvg: number;
    regime: string;
    regimeLabel: string;
    categoryBreakdown: Record<string, CategoryBreakdown>;
    triggeredStrategies: Array<{ name: string; displayName: string; score: number; weight: number; category: string }>;
  };
}

interface ScoreBreakdownProps {
  data: ScoreBreakdownData | null;
  isLoading: boolean;
  onClose: () => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  trend: '#22d3ee',
  reversal: '#a78bfa',
  pattern: '#fbbf24',
  framework: '#34d399',
  volume_price: '#f472b6',
  alpha101: '#fb923c',
};

const CATEGORY_NAMES: Record<string, string> = {
  trend: '趋势',
  reversal: '反转',
  pattern: '形态',
  framework: '框架',
  volume_price: '量价',
  alpha101: 'Alpha',
};

const SIGNAL_LABELS: Record<string, string> = {
  turnover_signal: '换手率',
  momentum_signal: '动量',
  pe_signal: '市盈率',
  pb_signal: '市净率',
  cap_signal: '市值',
  moderate_active: '适中活跃',
  low_active: '低活跃',
  high_active: '高活跃',
  extreme: '极端',
  gentle_up: '温和上涨',
  moderate_up: '中幅上涨',
  slight_pullback: '小幅回调',
  chase_risk: '追高风险',
  high_chase_risk: '高追高风险',
  weak: '弱势',
  reasonable: '合理',
  low_pe: '低估值',
  high_pe: '高估值',
  below_book: '破净',
  high_pb: '高市净率',
  mid_cap: '中盘',
  large_cap: '大盘',
};

function capYi(value?: number): string {
  if (value == null || value <= 0) return '--';
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万亿`;
  return `${value.toFixed(1)}亿`;
}

function BaseScoreBar({ total, max, components }: ScoreBreakdownData['baseScore']) {
  const pct = Math.min(100, (total / max) * 100);

  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[11px] font-medium text-secondary-text">基础评分</span>
        <span className="text-xs font-mono tabular-nums text-foreground">
          {total.toFixed(0)} <span className="text-muted-text">/ {max}</span>
        </span>
      </div>
      <div className="h-2 rounded-full bg-border/20 overflow-hidden mb-2">
        <div
          className="h-full rounded-full bg-gradient-to-r from-cyan/40 to-cyan/70 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-muted-text">
        {Object.entries(components).map(([key, val]) => {
          const label = SIGNAL_LABELS[key] || key;
          const signalLabel = SIGNAL_LABELS[val.score] || val.score;
          return (
            <span key={key} className="inline-flex items-center gap-0.5">
              <span className="text-secondary-text">{label}:</span>
              <span className={
                signalLabel === '合理' || signalLabel === '适中活跃' || signalLabel === '温和上涨' || signalLabel === '中盘'
                  ? 'text-success' : signalLabel === '追高风险' || signalLabel === '极端'
                  ? 'text-danger' : 'text-secondary-text'
              }>{signalLabel}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}

function StrategyWaterfall({ breakdown }: { breakdown: ScoreBreakdownData['strategyBreakdown'] }) {
  const entries = Object.entries(breakdown.categoryBreakdown)
    .filter(([, v]) => v.avgScore > 0)
    .sort(([, a], [, b]) => b.avgScore - a.avgScore);

  if (entries.length === 0) return null;

  return (
    <div>
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[11px] font-medium text-secondary-text">策略分组得分</span>
        <span className="text-[10px] text-muted-text">
          综合 {breakdown.fusionScore.toFixed(1)} · 均值 {breakdown.strategyAvg.toFixed(1)}
        </span>
      </div>
      <div className="space-y-1.5">
        {entries.map(([key, val]) => {
          const pctVal = Math.min(100, Math.max(0, val.avgScore));
          const color = CATEGORY_COLORS[key] || '#6b7280';
          return (
            <div key={key} className="flex items-center gap-2 text-[11px]">
              <span className="w-10 shrink-0 text-right text-secondary-text">
                {CATEGORY_NAMES[key] || key}
              </span>
              <div className="flex-1 h-2.5 rounded-full bg-border/20 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${pctVal}%`,
                    backgroundColor: color,
                    opacity: 0.55,
                  }}
                />
              </div>
              <span className="w-12 shrink-0 font-mono tabular-nums text-secondary-text text-right">
                {val.avgScore.toFixed(0)} · {val.weight.toFixed(2)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ScoreBreakdown({ data, isLoading, onClose }: ScoreBreakdownProps) {
  if (isLoading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
        <div className="bg-card border border-border rounded-2xl p-6 shadow-2xl min-w-[320px]" onClick={e => e.stopPropagation()}>
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-cyan" />
            <span className="text-sm text-secondary-text">加载得分拆解...</span>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const { code, name, score, price, marketCap, turnoverRate, peRatio, baseScore, strategyBreakdown } = data;
  const triggered = strategyBreakdown.triggeredStrategies || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-2xl shadow-2xl max-w-lg w-full mx-4 max-h-[85vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-card/95 backdrop-blur px-5 py-3 border-b border-border/50 flex items-center justify-between">
          <div>
            <span className="text-sm font-semibold text-foreground">{name || code}</span>
            <span className="ml-2 text-xs text-secondary-text">{code}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono tabular-nums text-cyan font-medium">
              评分 {score.toFixed(1)}
            </span>
            <button onClick={onClose} className="text-muted-text hover:text-foreground transition-colors">
              <ChevronUp className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="px-5 py-4 space-y-4">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-text">
            <span>¥{price.toFixed(2)}</span>
            <span>{capYi(marketCap)}</span>
            <span>换手 {turnoverRate?.toFixed(2) ?? '--'}%</span>
            <span>PE {peRatio?.toFixed(1) ?? '--'}</span>
          </div>

          <BaseScoreBar total={baseScore.total} max={baseScore.max} components={baseScore.components} />

          <StrategyWaterfall breakdown={strategyBreakdown} />

          {triggered.length > 0 && (
            <div>
              <span className="text-[11px] font-medium text-secondary-text block mb-1.5">触发信号详情</span>
              <div className="space-y-1">
                {triggered.map((s) => (
                  <div
                    key={s.name}
                    className="flex items-center justify-between py-1 px-2 rounded-lg bg-border/10"
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-foreground">{s.displayName}</span>
                      <span className="text-[10px] text-muted-text">{CATEGORY_NAMES[s.category] || s.category}</span>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] font-mono tabular-nums">
                      <span className="text-secondary-text">得分 {s.score.toFixed(0)}</span>
                      <span className="text-muted-text">权重 {s.weight.toFixed(3)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {strategyBreakdown.regimeLabel && (
            <div className="text-[10px] text-muted-text pt-1 border-t border-border/20">
              市场环境: {strategyBreakdown.regimeLabel}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
