import { useState, useEffect, useCallback } from 'react';
import { Scale, TrendingUp, TrendingDown, Minus, RefreshCw, Loader2, ChevronRight, ChevronDown, Info, X } from 'lucide-react';

interface WeightChange {
  strategy: string;
  display_name: string;
  original_weight: number;
  optimized_weight: number;
  change_pct: number;
  direction: string;
  interpretation: string;
  performance_data?: Record<string, string>;
}

interface WeightPanelProps {
  visible: boolean;
  onClose: () => void;
}

const STRATEGY_DISPLAY_NAMES: Record<string, string> = {
  bull_trend: '多头趋势',
  bottom_volume: '底部放量',
  emotion_cycle: '情绪周期',
  momentum_reversal: '动量反转',
  ma_golden_cross: '均线金叉',
  volume_price_break: '量价突破',
  pullback_bounce: '回踩反弹',
  gap_up: '跳空高开',
  dragon_tiger: '龙虎榜跟踪',
  limit_up_break: '涨停突破',
  sector_leader: '板块龙头',
  new_high_break: '新高突破',
  oversold_bounce: '超跌反弹',
  volume_shrink: '缩量止跌',
  ma_support: '均线支撑',
  trend_follow: '趋势跟随',
  reversal_pattern: '反转形态',
  breakout_confirm: '突破确认',
  volume_confirm: '量能确认',
  risk_filter: '风险过滤',
  quality_filter: '质量筛选',
  market_cap_filter: '市值筛选',
  liquidity_filter: '流动性筛选',
  earnings_surprise: '业绩超预期',
  institutional_flow: '机构资金流',
  sentiment_shift: '情绪转向',
};

function displayName(strategyName: string): string {
  return STRATEGY_DISPLAY_NAMES[strategyName] || strategyName;
}

function changePill(direction: string, changePct: number) {
  if (direction === 'up') {
    return (
      <span className="inline-flex items-center gap-0.5 text-[10px] text-success font-medium">
        <TrendingUp className="h-3 w-3" />+{changePct}%
      </span>
    );
  }
  if (direction === 'down') {
    return (
      <span className="inline-flex items-center gap-0.5 text-[10px] text-danger font-medium">
        <TrendingDown className="h-3 w-3" />{changePct}%
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-0.5 text-[10px] text-muted-text">
      <Minus className="h-3 w-3" />--
    </span>
  );
}

export function StrategyWeightPanel({ visible, onClose }: WeightPanelProps) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedInterpretation, setExpandedInterpretation] = useState<Set<string>>(new Set());

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const { apiClient } = await import('../../api/index');
      const response = await apiClient.get<Record<string, unknown>>('/api/v1/screener/weights/interpretation');
      setData(response.data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (visible && !data) {
      fetchData();
    }
  }, [visible, data, fetchData]);

  if (!visible) return null;

  const interpretations = (data?.interpretations as WeightChange[]) || [];
  const weightsBefore = (data?.weights_before as Record<string, number>) || {};
  const weightsAfter = (data?.weights_after as Record<string, number>) || {};
  const marketRegime = (data?.market_regime as string) || '';
  const totalStrategies = (data?.total_strategies as number) || 0;
  const modifiedStrategies = (data?.modified_strategies as number) || 0;

  const allStrategies = Object.keys(weightsAfter).length > 0
    ? Object.keys(weightsAfter)
    : Object.keys(weightsBefore);

  const toggleInterpretation = (key: string) => {
    setExpandedInterpretation(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

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
              <Scale className="h-4 w-4 text-cyan" />策略权重管理
            </h2>
            <p className="text-[10px] text-muted-text mt-0.5">
              {totalStrategies} 个策略 · {modifiedStrategies} 个调整 · {marketRegime || '未知市场'}
            </p>
          </div>
          <button
            onClick={fetchData}
            disabled={isLoading}
            className="p-1.5 rounded-lg hover:bg-hover transition-colors disabled:opacity-50"
            title="刷新解读"
          >
            <RefreshCw className={`h-3.5 w-3.5 text-muted-text ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <button onClick={onClose} className="p-1 ml-1 rounded-lg hover:bg-hover transition-colors">
            <X className="h-4 w-4 text-muted-text" />
          </button>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-cyan" />
            <span className="ml-2 text-sm text-secondary-text">加载权重数据...</span>
          </div>
        )}

        {error && (
          <div className="px-4 py-3 text-xs text-danger bg-danger/5">
            加载失败: {error}
          </div>
        )}

        {!isLoading && data && (
          <div className="px-4 py-3 space-y-3">
            {allStrategies.map((strategyName) => {
              const before = weightsBefore[strategyName] ?? 1;
              const after = weightsAfter[strategyName] ?? before;
              const change = after - before;
              const direction = change > 0.01 ? 'up' : change < -0.01 ? 'down' : '';
              const changePct = before > 0 ? Math.round((change / before) * 1000) / 10 : 0;

              const interpretationEntry = interpretations.find(
                i => i.strategy === strategyName
              );
              const isExpanded = expandedInterpretation.has(strategyName);

              return (
                <div key={strategyName} className="rounded-xl border border-border/30 bg-card/50 p-3">
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-medium text-foreground">
                        {displayName(strategyName)}
                      </span>
                      <span className="text-[10px] text-muted-text">{strategyName}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-muted-text">
                        {before.toFixed(2)}→{after.toFixed(2)}
                      </span>
                      {changePill(direction, changePct)}
                    </div>
                  </div>

                  <div className="h-1.5 rounded-full bg-border/20 overflow-hidden">
                    <div className="flex h-full">
                      <div
                        className="h-full bg-cyan/40 rounded-l-full"
                        style={{ width: `${Math.min(100, (before / 2) * 100)}%` }}
                      />
                      {direction && (
                        <div
                          className={`h-full ${direction === 'up' ? 'bg-success/60' : 'bg-danger/60'}`}
                          style={{ width: `${Math.abs(changePct) * 0.5}%` }}
                        />
                      )}
                    </div>
                  </div>

                  {interpretationEntry && interpretationEntry.interpretation && (
                    <>
                      <button
                        onClick={() => toggleInterpretation(strategyName)}
                        className="mt-2 flex items-center gap-1 text-[10px] text-cyan hover:text-cyan/80 transition-colors"
                      >
                        <Info className="h-3 w-3" />
                        {isExpanded ? '收起解读' : '查看解读'}
                        {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                      </button>
                      {isExpanded && (
                        <div className="mt-1.5 p-2 rounded-lg bg-cyan/5 border border-cyan/10">
                          <p className="text-[11px] text-secondary-text leading-relaxed">
                            {interpretationEntry.interpretation}
                          </p>
                        </div>
                      )}
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {!isLoading && !data && !error && (
          <div className="flex flex-col items-center justify-center py-12 text-muted-text">
            <Scale className="h-6 w-6 mb-2 opacity-30" />
            <p className="text-xs">暂无权重数据</p>
            <button onClick={fetchData} className="mt-2 text-xs text-cyan hover:text-cyan/80">
              重新加载
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
