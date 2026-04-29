import type React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Play, RotateCcw, ChevronDown, ChevronUp, TrendingUp, TrendingDown,
  Activity, Target, Zap, Shield, BarChart3, X, Database, Loader2,
} from 'lucide-react';
import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import apiClient from '../api/index';
import { ApiErrorAlert, Card, Badge, EmptyState, Pagination, Tooltip } from '../components/common';
import { OverviewTab } from '../components/backtest/OverviewTab';
import { PerformanceTab } from '../components/backtest/PerformanceTab';
import { TradeTab } from '../components/backtest/TradeTab';
import { RiskTab } from '../components/backtest/RiskTab';
import { useBacktestStream } from '../hooks/useBacktestStream';
import type { BacktestProgress, BacktestCompleted } from '../hooks/useBacktestStream';
import type {
  BacktestResultItem, BacktestRunResponse, EquityCurveResponse, PerformanceMetrics,
  ExitRuleConfig,
} from '../types/backtest';
import { StrategySelector } from '../components/backtest/StrategySelector';
import { StrategyParamForm } from '../components/backtest/StrategyParamForm';
import { PresetSelector } from '../components/backtest/PresetSelector';
import { ExitRuleForm } from '../components/backtest/ExitRuleForm';
import { EquityCurveChart as V2EquityCurveChart } from '../components/backtest/EquityCurveChart';
import { useStrategyList, useStrategyBacktest, useBacktestOptimize, useMonteCarlo } from '../hooks';
import { ExitReasonPieChart } from '../components/backtest/ExitReasonPieChart';
import { OptimizeConfigForm } from '../components/backtest/OptimizeConfigForm';
import { ParamHeatmap } from '../components/backtest/ParamHeatmap';
import { MonteCarloResult } from '../components/backtest/MonteCarloResult';
import { BacktestReportExport } from '../components/backtest/BacktestReportExport';
import { MonthlyHeatmap } from '../components/backtest/MonthlyHeatmap';
import { DrawdownChart } from '../components/backtest/DrawdownChart';
import { KlineTradeChart } from '../components/backtest/KlineTradeChart';
import { TradeTimeline } from '../components/backtest/TradeTimeline';
import { SignalFunnel } from '../components/backtest/SignalFunnel';
import { ParamSensitivityHeatmap } from '../components/backtest/ParamSensitivityHeatmap';
import { ParamChangeHistory, useParamChangeHistory } from '../components/backtest/ParamChangeHistory';
import { AISummaryCard } from '../components/backtest/AISummaryCard';
import { ProgressOverlay } from '../components/backtest/ProgressOverlay';

interface KlineStats {
  ready: boolean;
  stock_count: number;
  file_count: number;
  total_size_mb: number;
  date_range_from: string;
  date_range_to: string;
}

interface PortfolioMetricsLocal {
  sharpe_ratio?: number;
  total_return_pct?: number;
  annualized_return_pct?: number;
  max_drawdown_pct?: number;
  excess_return_pct?: number;
  information_ratio?: number;
  tracking_error_pct?: number;
  win_rate_pct?: number;
}

interface PortfolioResult {
  status: string;
  run_id: string;
  success: boolean;
  error: string | null;
  metrics: PortfolioMetricsLocal;
  trades: Array<{ date: string; code: string; action: string; shares: number; price: number; cost: number; reason: string }>;
  nav: Array<{ date: string; nav: number }>;
  elapsed_seconds: number;
}

function toKlineStats(raw: unknown): KlineStats | null {
  const s = raw as Record<string, unknown> | null;
  if (!s) return null;
  return {
    ready: Boolean(s.ready),
    stock_count: Number(s.stock_count ?? 0),
    file_count: Number(s.file_count ?? 0),
    total_size_mb: Number(s.total_size_mb ?? 0),
    date_range_from: String(s.date_range_from ?? ''),
    date_range_to: String(s.date_range_to ?? ''),
  };
}

function toPortfolioResult(raw: unknown): PortfolioResult | null {
  const r = raw as Record<string, unknown> | null;
  if (!r) return null;
  const metrics = (r.metrics ?? {}) as Record<string, unknown>;
  const rawTrades = Array.isArray(r.trades) ? r.trades : [];
  const rawNav = Array.isArray(r.nav) ? r.nav : [];
  return {
    status: String(r.status ?? ''),
    run_id: String(r.run_id ?? ''),
    success: Boolean(r.success),
    error: r.error ? String(r.error) : null,
    metrics: {
      sharpe_ratio: typeof metrics.sharpe_ratio === 'number' ? metrics.sharpe_ratio : undefined,
      total_return_pct: typeof metrics.total_return_pct === 'number' ? metrics.total_return_pct : undefined,
      annualized_return_pct: typeof metrics.annualized_return_pct === 'number' ? metrics.annualized_return_pct : undefined,
      max_drawdown_pct: typeof metrics.max_drawdown_pct === 'number' ? metrics.max_drawdown_pct : undefined,
      excess_return_pct: typeof metrics.excess_return_pct === 'number' ? metrics.excess_return_pct : undefined,
      information_ratio: typeof metrics.information_ratio === 'number' ? metrics.information_ratio : undefined,
      tracking_error_pct: typeof metrics.tracking_error_pct === 'number' ? metrics.tracking_error_pct : undefined,
      win_rate_pct: typeof metrics.win_rate_pct === 'number' ? metrics.win_rate_pct : undefined,
    },
    trades: (rawTrades as Array<Record<string, unknown>>).map((t) => ({
      date: String(t.date ?? ''),
      code: String(t.code ?? ''),
      action: String(t.action ?? ''),
      shares: Number(t.shares ?? 0),
      price: Number(t.price ?? 0),
      cost: Number(t.cost ?? 0),
      reason: String(t.reason ?? ''),
    })),
    nav: (rawNav as Array<Record<string, unknown>>).map((d) => {
      const keys = Object.keys(d);
      const dateKey = keys.find((k) => k.toLowerCase().includes('date')) || keys[0];
      const navKey = keys.find((k) => k.toLowerCase().includes('nav') && !k.toLowerCase().includes('bench')) || keys[1];
      return { date: String(d[dateKey] ?? ''), nav: Number(d[navKey] ?? 0) };
    }),
    elapsed_seconds: Number(r.elapsed_seconds ?? 0),
  };
}

const INPUT_CLASS =
  'input-surface input-focus-glow h-9 w-full rounded-xl border bg-transparent px-3 py-2 text-xs transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

function pct(v?: number | null): string {
  if (v == null) return '--';
  return `${v.toFixed(1)}%`;
}
function ratio(v?: number | null, d = 2): string {
  if (v == null) return '--';
  return v.toFixed(d);
}
function colorCls(v?: number | null, invert = false): string {
  if (v == null) return 'text-muted-text';
  if (invert) return v <= 0 ? 'text-success' : v > 0 ? 'text-danger' : 'text-secondary-text';
  return v > 0 ? 'text-success' : v < 0 ? 'text-danger' : 'text-secondary-text';
}

const OUTCOME_MAP: Record<string, { label: string; variant: 'success' | 'danger' | 'warning' | 'default' }> = {
  win: { label: '胜', variant: 'success' },
  loss: { label: '负', variant: 'danger' },
  neutral: { label: '平', variant: 'warning' },
};
const MOVEMENT_MAP: Record<string, { label: string; variant: 'success' | 'danger' | 'warning' | 'default' }> = {
  up: { label: '涨', variant: 'success' },
  down: { label: '跌', variant: 'danger' },
  flat: { label: '平', variant: 'warning' },
};
const STATUS_MAP: Record<string, { label: string; variant: 'success' | 'warning' | 'danger' | 'default' }> = {
  completed: { label: '已完成', variant: 'success' },
  insufficient_data: { label: '数据不足', variant: 'warning' },
  insufficient: { label: '数据不足', variant: 'warning' },
  error: { label: '错误', variant: 'danger' },
  pending: { label: '待处理', variant: 'default' },
};

const WIZARD_STEPS = [
  { key: 'config', label: '配置', icon: Target },
  { key: 'running', label: '执行', icon: Zap },
  { key: 'results', label: '结果', icon: BarChart3 },
] as const;

type WizardStep = typeof WIZARD_STEPS[number]['key'];

const StepIndicator: React.FC<{ current: WizardStep; completed: WizardStep[] }> = ({ current, completed }) => (
  <div className="flex items-center gap-1">
    {WIZARD_STEPS.map((step, i) => {
      const Icon = step.icon;
      const isActive = step.key === current;
      const isDone = completed.includes(step.key);
      return (
        <div key={step.key} className="flex items-center gap-1">
          {i > 0 && <div className={`w-6 h-px ${isDone || isActive ? 'bg-cyan/50' : 'bg-border'}`} />}
          <div className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs transition-all ${
            isActive ? 'bg-cyan/10 text-cyan font-medium' : isDone ? 'text-success' : 'text-muted-text'
          }`}>
            <Icon className="h-3.5 w-3.5" />
            <span>{step.label}</span>
            {isDone && step.key !== current && <span className="text-success">✓</span>}
          </div>
        </div>
      );
    })}
  </div>
);

const StockTag: React.FC<{ code: string; name?: string; onRemove?: () => void }> = ({ code, name, onRemove }) => (
  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-cyan/10 text-cyan text-xs font-medium">
    {code}{name ? ` ${name}` : ''}
    {onRemove && (
      <button type="button" onClick={onRemove} className="ml-0.5 hover:text-danger transition-colors">
        <X className="h-3 w-3" />
      </button>
    )}
  </span>
);

const MetricCard: React.FC<{
  label: string; value: string; icon?: React.ReactNode; tone?: 'success' | 'danger' | 'warning' | 'neutral';
  sub?: string;
}> = ({ label, value, icon, tone = 'neutral', sub }) => {
  const toneCls = tone === 'success' ? 'text-success' : tone === 'danger' ? 'text-danger' : tone === 'warning' ? 'text-warning' : 'text-foreground';
  return (
    <div className="flex flex-col items-center gap-0.5 px-3 py-2">
      {icon && <div className={`${toneCls} opacity-70`}>{icon}</div>}
      <span className={`text-lg font-bold tabular-nums ${toneCls}`}>{value}</span>
      <span className="text-[10px] text-muted-text">{label}</span>
      {sub && <span className="text-[10px] text-muted-text">{sub}</span>}
    </div>
  );
};

const PerformancePanel: React.FC<{ metrics: PerformanceMetrics; title: string; collapsible?: boolean }> = ({
  metrics, title, collapsible = true,
}) => {
  const [open, setOpen] = useState(!collapsible);
  const winRate = metrics.winRatePct;
  const wrTone = winRate != null ? (winRate >= 50 ? 'success' : winRate >= 30 ? 'warning' : 'danger') : 'neutral';
  const sharpeTone = metrics.sharpeRatio != null ? (metrics.sharpeRatio >= 1 ? 'success' : metrics.sharpeRatio >= 0 ? 'warning' : 'danger') : 'neutral';
  const ddTone = metrics.maxDrawdownPct != null ? (metrics.maxDrawdownPct <= 10 ? 'success' : metrics.maxDrawdownPct <= 20 ? 'warning' : 'danger') : 'neutral';

  return (
    <Card variant="gradient" padding="sm" className="animate-fade-in">
      <button
        type="button"
        onClick={() => collapsible && setOpen(!open)}
        className="flex w-full items-center justify-between"
      >
        <span className="text-xs font-medium text-secondary-text">{title}</span>
        {collapsible && (open ? <ChevronUp className="h-3.5 w-3.5 text-muted-text" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-text" />)}
      </button>

      <div className="flex flex-wrap justify-center gap-1 mt-2">
        <MetricCard label="胜率" value={pct(winRate)} tone={wrTone}
          icon={<Target className="h-4 w-4" />} sub={`${metrics.winCount}胜 ${metrics.lossCount}负 ${metrics.neutralCount}平`} />
        <MetricCard label="方向准确率" value={pct(metrics.directionAccuracyPct)} tone="neutral"
          icon={<Zap className="h-4 w-4" />} />
        <MetricCard label="夏普比率" value={ratio(metrics.sharpeRatio)} tone={sharpeTone}
          icon={<TrendingUp className="h-4 w-4" />} />
        <MetricCard label="最大回撤" value={pct(metrics.maxDrawdownPct)} tone={ddTone}
          icon={<Shield className="h-4 w-4" />} />
        <MetricCard label="盈亏比" value={ratio(metrics.profitFactor)} tone="neutral"
          icon={<BarChart3 className="h-4 w-4" />} />
        <MetricCard label="平均盈利" value={pct(metrics.avgWinPct)} tone="success" />
        <MetricCard label="平均亏损" value={pct(metrics.avgLossPct)} tone="danger" />
      </div>

      {open && (
        <div className="mt-3 pt-3 border-t border-border/30 space-y-1.5 animate-fade-in">
          <div className="flex justify-between text-xs">
            <span className="text-muted-text">模拟平均收益</span>
            <span className={colorCls(metrics.avgSimulatedReturnPct)}>{pct(metrics.avgSimulatedReturnPct)}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted-text">股票平均收益</span>
            <span className={colorCls(metrics.avgStockReturnPct)}>{pct(metrics.avgStockReturnPct)}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted-text">止损触发率</span>
            <span className="text-secondary-text">{pct(metrics.stopLossTriggerRate)}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted-text">止盈触发率</span>
            <span className="text-secondary-text">{pct(metrics.takeProfitTriggerRate)}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted-text">平均命中天数</span>
            <span className="text-secondary-text">{metrics.avgDaysToFirstHit != null ? metrics.avgDaysToFirstHit.toFixed(1) : '--'}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted-text">评估完成</span>
            <span className="text-secondary-text">{metrics.completedCount} / {metrics.totalEvaluations}</span>
          </div>
        </div>
      )}
    </Card>
  );
};

const EquityCurveChart: React.FC<{ data: EquityCurveResponse | null; isLoading: boolean }> = ({ data, isLoading }) => {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48">
        <div className="backtest-spinner md" />
      </div>
    );
  }
  if (!data || data.points.length === 0) {
    return (
      <EmptyState
        title="暂无资金曲线"
        description="执行回测后将在此展示累计收益率与回撤曲线"
        className="h-48 border-dashed"
        icon={<Activity className="h-5 w-5" />}
      />
    );
  }
  const chartData = data.points.map(p => ({
    date: p.date.slice(5),
    cumulativeReturn: Number(p.cumulativeReturnPct.toFixed(2)),
    drawdown: Number(p.drawdownPct.toFixed(2)),
  }));
  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-center gap-2 mb-1.5">
          <TrendingUp className="h-3.5 w-3.5 text-success" />
          <span className="text-xs font-medium text-secondary-text">累计收益率</span>
          <span className="text-[10px] text-muted-text">{data.totalTrades} 笔交易</span>
        </div>
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} tickFormatter={(v: number) => `${v}%`} />
              <RechartsTooltip
                contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', fontSize: 12 }}
                labelStyle={{ color: 'hsl(var(--foreground))' }}
                formatter={((value: number) => [`${value.toFixed(2)}%`, '累计收益率']) as never}
              />
              <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
              <Line type="monotone" dataKey="cumulativeReturn" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
              <Legend formatter={() => '累计收益率'} wrapperStyle={{ fontSize: 11 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div>
        <div className="flex items-center gap-2 mb-1.5">
          <TrendingDown className="h-3.5 w-3.5 text-danger" />
          <span className="text-xs font-medium text-secondary-text">回撤</span>
        </div>
        <div className="h-24">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} tickFormatter={(v: number) => `${v}%`} domain={['auto', 0]} />
              <RechartsTooltip
                contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: '8px', fontSize: 12 }}
                labelStyle={{ color: 'hsl(var(--foreground))' }}
                formatter={((value: number) => [`${value.toFixed(2)}%`, '回撤']) as never}
              />
              <Bar dataKey="drawdown" fill="hsl(var(--destructive))" opacity={0.7} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

const RunResultBanner: React.FC<{ data: BacktestRunResponse }> = ({ data }) => {
  const isEmpty = (data.processed ?? 0) === 0;

  if (isEmpty) {
    return (
      <div className="flex flex-wrap items-center gap-3 px-4 py-2.5 rounded-xl bg-warning/10 border border-warning/30 animate-fade-in">
        <span className="text-xs font-medium text-warning">无候选记录</span>
        <span className="text-xs text-secondary-text">
          这些股票尚无历史分析记录，请先在「首页」中对这些股票执行一次分析后再试。
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-3 px-4 py-2.5 rounded-xl bg-success/10 border border-success/30 animate-fade-in">
      <span className="text-xs font-medium text-success">回测完成</span>
      {(data.analyzed ?? 0) > 0 && <span className="text-xs text-secondary-text">自动分析 <span className="font-mono text-cyan">{data.analyzed}</span> 只</span>}
      <span className="text-xs text-secondary-text">候选 <span className="font-mono text-foreground">{data.processed}</span></span>
      <span className="text-xs text-secondary-text">写入 <span className="font-mono text-foreground">{data.saved}</span></span>
      <span className="text-xs text-secondary-text">完成 <span className="font-mono text-success">{data.completed}</span></span>
      <span className="text-xs text-secondary-text">数据不足 <span className="font-mono text-warning">{data.insufficient}</span></span>
      {data.errors > 0 && <span className="text-xs text-secondary-text">错误 <span className="font-mono text-danger">{data.errors}</span></span>}
    </div>
  );
};

const BacktestPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  useEffect(() => { document.title = '策略回测 - DSA'; }, []);

  const initialCodes = searchParams.get('codes')?.split(',').filter(Boolean) ?? [];
  const initialCode = searchParams.get('code') || '';
  const initialAutoRun = searchParams.get('autoRun') === '1';
  const initialFrom = searchParams.get('from') || '';
  const initialTo = searchParams.get('to') || '';

  const [selectedCodes, setSelectedCodes] = useState<string[]>(initialCodes.length > 0 ? initialCodes : initialCode ? [initialCode] : []);
  const [codeInput, setCodeInput] = useState('');
  const [evalDays, setEvalDays] = useState('10');
  const [forceRerun, setForceRerun] = useState(false);
  const [dateFrom, setDateFrom] = useState(initialFrom);
  const [dateTo, setDateTo] = useState(initialTo);

  const [wizardStep, setWizardStep] = useState<WizardStep>(initialAutoRun ? 'running' : 'config');
  const [completedSteps, setCompletedSteps] = useState<WizardStep[]>([]);

  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState<BacktestRunResponse | null>(null);
  const [runError, setRunError] = useState<ParsedApiError | null>(null);
  const [pageError, setPageError] = useState<ParsedApiError | null>(null);

  const [results, setResults] = useState<BacktestResultItem[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const pageSize = 20;

  const [overallPerf, setOverallPerf] = useState<PerformanceMetrics | null>(null);
  const [isLoadingPerf, setIsLoadingPerf] = useState(false);

  const [equityCurve, setEquityCurve] = useState<EquityCurveResponse | null>(null);
  const [isLoadingCurve, setIsLoadingCurve] = useState(false);

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [resultTab, setResultTab] = useState<'overview' | 'performance' | 'trades' | 'risk'>('overview');
  const [initCapital, setInitCapital] = useState(100000);
  const [maxPositions, setMaxPositions] = useState(10);
  const [rebalanceDays, setRebalanceDays] = useState(5);
  const [factorJson, setFactorJson] = useState('');
  const [klineStats, setKlineStats] = useState<KlineStats | null>(null);
  const [isCheckingKline, setIsCheckingKline] = useState(false);
  const effectiveMode: 'verify' | 'portfolio' = klineStats?.ready ? 'portfolio' : 'verify';
  const [pfRunResult, setPfRunResult] = useState<PortfolioResult | null>(null);
  const [pfRunError, setPfRunError] = useState<ParsedApiError | null>(null);
  const [isPfRunning, setIsPfRunning] = useState(false);
  const [streamParams, setStreamParams] = useState<Record<string, unknown> | null>(null);
  const [streamProgress, setStreamProgress] = useState<BacktestProgress | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);

  const [backtestMode, setBacktestMode] = useState<'verify' | 'v2' | 'optimize' | 'montecarlo'>('verify');

  const { strategies } = useStrategyList();
  const [v2Strategy, setV2Strategy] = useState('');
  const [v2Factors, setV2Factors] = useState<Record<string, number>>({});
  const [v2Preset, setV2Preset] = useState<string | null>(null);
  const [v2ExitRules, setV2ExitRules] = useState<ExitRuleConfig>({});
  const [v2Cash, setV2Cash] = useState(100000);
  const [v2Commission, setV2Commission] = useState(0.0003);
  const [v2Slippage, setV2Slippage] = useState(0.001);
  const { run: runV2, result: v2Result, loading: v2Loading, error: v2Error, reset: resetV2 } = useStrategyBacktest();

  const { run: runOpt, result: optResult, loading: optLoading, error: optError, reset: resetOpt } = useBacktestOptimize();
  const { run: runMC, result: mcResult, loading: mcLoading, error: mcError, reset: resetMC } = useMonteCarlo();
  const [mcN, setMCN] = useState(1000);
  const { history: paramHistory } = useParamChangeHistory();

  const exportV2Report = async () => {
      if (!v2Result) return;
      try {
        const resp = await fetch('/api/v1/backtest/strategy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            strategy: v2Strategy,
            codes: selectedCodes,
            cash: v2Cash,
            commission: v2Commission,
            slippage: v2Slippage,
            start_date: dateFrom || undefined,
            end_date: dateTo || undefined,
            factors: v2Factors,
            exit_rules: Object.keys(v2ExitRules).length > 0 ? {
              trailing_stop_pct: v2ExitRules.trailingStopPct,
              take_profit_pct: v2ExitRules.takeProfitPct,
              stop_loss_pct: v2ExitRules.stopLossPct,
              max_hold_days: v2ExitRules.maxHoldDays,
            } : undefined,
          }),
        });
        const data = await resp.json() as Record<string, unknown>;
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `backtest_${v2Result.strategyName}_${v2Result.symbol}.json`;
        a.click();
        URL.revokeObjectURL(url);
      } catch { /* ignore */ }
    };

  const selectedStrategy = strategies.find((s) => s.name === v2Strategy);
  useEffect(() => {
    if (selectedStrategy) {
      const defaults: Record<string, number> = {};
      for (const f of selectedStrategy.factors) {
        defaults[f.id] = f.default;
      }
      setV2Factors(defaults);
    }
  }, [v2Strategy, selectedStrategy]);

  const handleV2Run = async () => {
    if (!v2Strategy || selectedCodes.length === 0) return;
    setWizardStep('running');
    setCompletedSteps((prev) => prev.includes('config') ? prev : [...prev, 'config']);
    await runV2({
      strategy: v2Strategy,
      codes: selectedCodes,
      cash: v2Cash,
      commission: v2Commission,
      slippage: v2Slippage,
      startDate: dateFrom || undefined,
      endDate: dateTo || undefined,
      factors: v2Factors,
      preset: v2Preset ?? undefined,
      exitRules: Object.keys(v2ExitRules).length > 0 ? v2ExitRules : undefined,
    });
    setWizardStep('results');
    setCompletedSteps((prev) => {
      const next = new Set(prev);
      next.add('running');
      return [...next] as WizardStep[];
    });
  };

  const checkKlineStats = useCallback(async () => {
    setIsCheckingKline(true);
    try {
      const response = await apiClient.get<Record<string, unknown>>('/api/v1/backtest/kline-stats');
      setKlineStats(toKlineStats(response.data?.stats));
    } catch {
      setKlineStats(null);
    } finally {
      setIsCheckingKline(false);
    }
  }, []);

  const handlePortfolioRun = useCallback(async () => {
    setIsPfRunning(true);
    setPfRunResult(null);
    setPfRunError(null);
    try {
      const params: Record<string, string | number> = {
        initial_capital: initCapital,
        max_positions: maxPositions,
        rebalance_days: rebalanceDays,
      };
      if (dateFrom) params.start_date = dateFrom;
      if (dateTo) params.end_date = dateTo;
      if (factorJson.trim()) params.factor_json = factorJson.trim();

      const response = await apiClient.post<Record<string, unknown>>(
        '/api/v1/backtest/portfolio',
        null,
        { params, timeout: 120000 },
      );
      setPfRunResult(toPortfolioResult(response.data));
    } catch (err: unknown) {
      setPfRunError(getParsedApiError(err));
    } finally {
      setIsPfRunning(false);
    }
  }, [initCapital, maxPositions, rebalanceDays, dateFrom, dateTo, factorJson]);

  const addCode = () => {
    const trimmed = codeInput.trim().toUpperCase();
    if (trimmed && !selectedCodes.includes(trimmed)) {
      setSelectedCodes(prev => [...prev, trimmed]);
    }
    setCodeInput('');
  };
  const removeCode = (code: string) => setSelectedCodes(prev => prev.filter(c => c !== code));
  const handleCodeKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter') { e.preventDefault(); addCode(); } };

  const fetchResults = useCallback(async (page = 1) => {
    setIsLoadingResults(true);
    try {
      const code = selectedCodes.length === 1 ? selectedCodes[0] : undefined;
      const windowDays = evalDays ? parseInt(evalDays, 10) : undefined;
      const response = await backtestApi.getResults({
        code, evalWindowDays: windowDays,
        analysisDateFrom: dateFrom || undefined, analysisDateTo: dateTo || undefined,
        page, limit: pageSize,
      });
      setResults(response.items);
      setTotalResults(response.total);
      setCurrentPage(response.page);
      setPageError(null);
    } catch (err) {
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingResults(false);
    }
  }, [selectedCodes, evalDays, dateFrom, dateTo]);

  const fetchPerformance = useCallback(async () => {
    setIsLoadingPerf(true);
    try {
      const windowDays = evalDays ? parseInt(evalDays, 10) : undefined;
      const overall = await backtestApi.getOverallPerformance({
        evalWindowDays: windowDays, analysisDateFrom: dateFrom || undefined, analysisDateTo: dateTo || undefined,
      });
      setOverallPerf(overall);
      setPageError(null);
    } catch (err) {
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingPerf(false);
    }
  }, [evalDays, dateFrom, dateTo]);

  const fetchEquityCurve = useCallback(async () => {
    setIsLoadingCurve(true);
    try {
      const code = selectedCodes.length === 1 ? selectedCodes[0] : undefined;
      const windowDays = evalDays ? parseInt(evalDays, 10) : undefined;
      const data = await backtestApi.getEquityCurve({
        code, evalWindowDays: windowDays,
        analysisDateFrom: dateFrom || undefined, analysisDateTo: dateTo || undefined,
      });
      setEquityCurve(data);
    } catch (err) {
      console.error('获取资金曲线失败:', err);
    } finally {
      setIsLoadingCurve(false);
    }
  }, [selectedCodes, evalDays, dateFrom, dateTo]);

  const loadResults = useCallback(async () => {
    await fetchResults(1);
    await fetchPerformance();
    await fetchEquityCurve();
  }, [fetchResults, fetchPerformance, fetchEquityCurve]);

  const handleStreamCompleted = useCallback((data: BacktestCompleted) => {
    if ((data.submitted_for_analysis ?? 0) > 0) {
      setRunResult({
        processed: 0, saved: 0, completed: 0, insufficient: 0, errors: 0, analyzed: data.submitted_for_analysis,
      } as unknown as BacktestRunResponse);
      setWizardStep('results');
      setCompletedSteps(['config', 'running']);
      setIsRunning(false);
      setStreamParams(null);
      return;
    }

    setRunResult({
      processed: data.processed,
      saved: data.saved,
      completed: data.completed,
      insufficient: data.insufficient,
      errors: data.errors,
      analyzed: data.analyzed,
    } as unknown as BacktestRunResponse);
    setWizardStep('results');
    setCompletedSteps(['config', 'running']);
    setIsRunning(false);
    setStreamParams(null);
    loadResults();
  }, [loadResults]);

  useBacktestStream(streamParams, {
    enabled: streamParams !== null,
    onProgress: setStreamProgress,
    onCompleted: handleStreamCompleted,
    onError: (msg) => {
      setStreamError(msg);
      setRunError({ title: '回测失败', message: msg, rawMessage: msg, category: 'unknown' });
      setWizardStep('config');
      setIsRunning(false);
      setStreamParams(null);
    },
  });

  const handleRun = useCallback(() => {
    setIsRunning(true);
    setRunResult(null);
    setRunError(null);
    setStreamProgress(null);
    setStreamError(null);
    setWizardStep('running');

    const codes = selectedCodes.length > 0 ? selectedCodes : undefined;
    const code = !codes || codes.length === 0 ? undefined : codes.length === 1 ? codes[0] : undefined;
    const evalWindowDays = evalDays ? parseInt(evalDays, 10) : undefined;

    const params: Record<string, unknown> = {
      force: forceRerun || false,
      min_age_days: forceRerun ? 0 : 14,
      auto_analyze: true,
    };
    if (code) params.code = code;
    if (codes && codes.length > 1) params.codes = codes;
    if (evalWindowDays) params.eval_window_days = evalWindowDays;

    setStreamParams(params);
  }, [selectedCodes, evalDays, forceRerun]);

  useEffect(() => {
    if (initialAutoRun && selectedCodes.length > 0) {
      handleRun();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!initialAutoRun) {
      loadResults();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleReset = () => {
    setSelectedCodes([]);
    setEvalDays('10');
    setForceRerun(false);
    setDateFrom('');
    setDateTo('');
    setRunResult(null);
    setRunError(null);
    setWizardStep('config');
    setCompletedSteps([]);
  };

  const totalPages = Math.ceil(totalResults / pageSize);
  const handlePageChange = (page: number) => fetchResults(page);

  const isNextDay = evalDays === '1';

  return (
    <div className="min-h-full flex flex-col rounded-[1.5rem] bg-transparent">
      <header className="flex-shrink-0 border-b border-white/5 px-4 py-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <h1 className="text-sm font-semibold text-foreground">策略回测</h1>
            <StepIndicator current={wizardStep} completed={completedSteps} />
            {klineStats && klineStats.ready ? (
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-success/10 border border-success/30 text-[10px]">
                <div className="h-1.5 w-1.5 rounded-full bg-success" />
                <span className="text-success font-medium">策略回测</span>
                <span className="text-muted-text">{klineStats.stock_count}只股可用</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-cyan/10 border border-cyan/30 text-[10px]">
                <div className="h-1.5 w-1.5 rounded-full bg-cyan" />
                <span className="text-cyan font-medium">历史验证</span>
                <span className="text-muted-text">基于分析记录</span>
              </div>
            )}
          </div>
          <button type="button" onClick={handleReset}
            className="btn-secondary flex items-center gap-1 text-xs">
            <RotateCcw className="h-3 w-3" />重置
          </button>
        </div>

        <div className="flex items-center gap-0 mt-3 bg-border/10 rounded-lg p-0.5 w-fit">
          <button
            type="button"
            onClick={() => { setBacktestMode('verify'); setWizardStep('config'); setCompletedSteps([]); }}
            className={`px-3 py-1 rounded-md text-[10px] font-medium transition-all ${
              backtestMode === 'verify' ? 'bg-cyan/20 text-cyan' : 'text-muted-text hover:text-secondary-text'
            }`}
          >
            📋 AI验证回测
          </button>
          <button
            type="button"
            onClick={() => { setBacktestMode('v2'); setWizardStep('config'); setCompletedSteps([]); resetV2(); }}
            className={`px-3 py-1 rounded-md text-[10px] font-medium transition-all ${
              backtestMode === 'v2' ? 'bg-cyan/20 text-cyan' : 'text-muted-text hover:text-secondary-text'
            }`}
          >
            📊 策略回测 (v2)
          </button>
          <button
            type="button"
            onClick={() => { setBacktestMode('optimize' as never); setWizardStep('config'); setCompletedSteps([]); resetOpt(); }}
            className={`px-3 py-1 rounded-md text-[10px] font-medium transition-all ${
              backtestMode === 'optimize' ? 'bg-cyan/20 text-cyan' : 'text-muted-text hover:text-secondary-text'
            }`}
          >
            🔧 参数优化
          </button>
          <button
            type="button"
            onClick={() => { setBacktestMode('montecarlo' as never); setWizardStep('config'); setCompletedSteps([]); resetMC(); }}
            className={`px-3 py-1 rounded-md text-[10px] font-medium transition-all ${
              backtestMode === 'montecarlo' ? 'bg-cyan/20 text-cyan' : 'text-muted-text hover:text-secondary-text'
            }`}
          >
            🎲 蒙特卡洛
          </button>
        </div>

        {backtestMode === 'verify' && effectiveMode === 'portfolio' && (
          <div className="space-y-3 animate-fade-in">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-muted-text">初始资金</label>
                <input type="number" value={initCapital} onChange={e => setInitCapital(Number(e.target.value))}
                  min={10000} step={10000}
                  className={`${INPUT_CLASS} w-full text-center tabular-nums`} />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-muted-text">持仓上限</label>
                <input type="number" value={maxPositions} onChange={e => setMaxPositions(Number(e.target.value))}
                  min={1} max={50}
                  className={`${INPUT_CLASS} w-full text-center tabular-nums`} />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-muted-text">调仓周期(日)</label>
                <input type="number" value={rebalanceDays} onChange={e => setRebalanceDays(Number(e.target.value))}
                  min={1} max={60}
                  className={`${INPUT_CLASS} w-full text-center tabular-nums`} />
              </div>
              <div className="flex items-end">
                <button onClick={checkKlineStats} disabled={isCheckingKline}
                  className="btn-secondary flex items-center gap-1 text-[10px] w-full justify-center">
                  <Database className="h-3 w-3" />
                  {isCheckingKline ? '检查中...' : klineStats ? `${String(klineStats.stock_count)}只股` : '检查数据'}
                </button>
              </div>
            </div>
            <div className="flex gap-2">
              <div className="flex flex-col gap-1 flex-1">
                <label className="text-[10px] text-muted-text">回测起始</label>
                <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                  className={`${INPUT_CLASS} flex-1`} />
              </div>
              <div className="flex flex-col gap-1 flex-1">
                <label className="text-[10px] text-muted-text">回测结束</label>
                <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
                  className={`${INPUT_CLASS} flex-1`} />
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-muted-text">
                策略因子值 (JSON, 可选)
              </label>
              <textarea
                value={factorJson}
                onChange={e => setFactorJson(e.target.value)}
                placeholder='{"bull_trend":{"trend_score":12},"bottom_volume":{"decline_threshold":0.15}}'
                rows={2}
                className={`${INPUT_CLASS} resize-none font-mono text-[10px]`}
              />
            </div>
            {klineStats && klineStats.ready && (
              <div className="flex items-center gap-2 text-[10px] text-success">
                <div className="h-1.5 w-1.5 rounded-full bg-success" />
                K线数据就绪 · {klineStats.total_size_mb.toFixed(0)} MB · {klineStats.date_range_to}
              </div>
            )}
            <div className="flex items-center gap-3 pt-1">
              <button type="button" onClick={handlePortfolioRun} disabled={isPfRunning}
                className="btn-primary flex items-center gap-2 text-sm px-6 py-2.5">
                {isPfRunning ? (
                  <><svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>回测执行中...</>
                ) : (<><Play className="h-4 w-4" />开始策略回测</>)}
              </button>
              <span className="text-[10px] text-muted-text">
                基于本地K线数据和策略因子进行完整组合回测
              </span>
            </div>
            {pfRunError && <ApiErrorAlert error={pfRunError} className="mt-2" />}
            {pfRunResult && !pfRunError && (
              <div className="space-y-2 animate-fade-in">
                <div className="flex items-center rounded-lg bg-border/10 p-0.5 w-fit">
                  {(['overview', 'performance', 'trades', 'risk'] as const).map(tab => (
                    <button
                      key={tab}
                      onClick={() => setResultTab(tab)}
                      className={`px-3 py-1 rounded-md text-[10px] font-medium transition-all ${
                        resultTab === tab ? 'bg-cyan/20 text-cyan' : 'text-muted-text hover:text-secondary-text'
                      }`}
                    >
                      {{ overview: '概览', performance: '绩效', trades: '交易', risk: '风险' }[tab]}
                    </button>
                  ))}
                </div>
                <div className="min-h-[120px]">
                  {resultTab === 'overview' && <OverviewTab metrics={pfRunResult.metrics as unknown as Record<string, number>} nav={pfRunResult.nav} />}
                  {resultTab === 'performance' && <PerformanceTab metrics={pfRunResult.metrics as unknown as Record<string, number>} />}
                  {resultTab === 'trades' && <TradeTab trades={pfRunResult.trades} />}
                  {resultTab === 'risk' && <RiskTab nav={pfRunResult.nav} metrics={pfRunResult.metrics as unknown as Record<string, number>} />}
                </div>
              </div>
            )}
          </div>
        )}

        {effectiveMode === 'verify' && wizardStep === 'config' && (
          <div className="space-y-3 animate-fade-in">
            <div>
              <label className="text-xs text-muted-text mb-1 block">
                回测股票 {selectedCodes.length > 0 && <span className="text-cyan">({selectedCodes.length} 只)</span>}
                {selectedCodes.length === 0 && <span className="text-warning ml-1">不选则回测全部</span>}
              </label>
              <div className="flex items-center gap-2">
                <input type="text" value={codeInput} onChange={e => setCodeInput(e.target.value.toUpperCase())}
                  onKeyDown={handleCodeKeyDown} placeholder="输入股票代码后回车添加"
                  className={`${INPUT_CLASS} flex-1`} />
                <button type="button" onClick={addCode} className="btn-secondary text-xs px-3">添加</button>
              </div>
              {selectedCodes.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {selectedCodes.map(code => (
                    <StockTag key={code} code={code} onRemove={() => removeCode(code)} />
                  ))}
                  <button type="button" onClick={() => setSelectedCodes([])}
                    className="text-[10px] text-muted-text hover:text-danger transition-colors">全部清除</button>
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-text">评估窗口（交易日）</label>
                <div className="flex items-center gap-1">
                  <input type="number" min={1} max={120} value={evalDays}
                    onChange={e => setEvalDays(e.target.value)} className={`${INPUT_CLASS} w-20 text-center tabular-nums`} />
                  <button type="button" onClick={() => setEvalDays('1')}
                    className={`text-[10px] px-2 py-1 rounded-lg border transition-all ${
                      isNextDay ? 'bg-cyan/10 border-cyan/30 text-cyan' : 'border-border/50 text-muted-text hover:text-secondary-text'
                    }`}>
                    次日验证
                  </button>
                  <button type="button" onClick={() => setEvalDays('5')}
                    className={`text-[10px] px-2 py-1 rounded-lg border transition-all ${
                      evalDays === '5' ? 'bg-cyan/10 border-cyan/30 text-cyan' : 'border-border/50 text-muted-text hover:text-secondary-text'
                    }`}>
                    5日
                  </button>
                  <button type="button" onClick={() => setEvalDays('10')}
                    className={`text-[10px] px-2 py-1 rounded-lg border transition-all ${
                      evalDays === '10' ? 'bg-cyan/10 border-cyan/30 text-cyan' : 'border-border/50 text-muted-text hover:text-secondary-text'
                    }`}>
                    10日
                  </button>
                </div>
                <span className="text-[10px] text-muted-text">
                  {isNextDay ? '对比 AI 预测与下一个交易日实际走势' : `评估未来 ${evalDays} 个交易日的收益表现`}
                </span>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-text">分析日期起</label>
                <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                  className={`${INPUT_CLASS} w-36 tabular-nums`} />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-muted-text">分析日期止</label>
                <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
                  className={`${INPUT_CLASS} w-36 tabular-nums`} />
              </div>

              <button type="button" onClick={() => setShowAdvanced(!showAdvanced)}
                className="text-[10px] text-muted-text hover:text-secondary-text transition-colors flex items-center gap-0.5">
                {showAdvanced ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                高级选项
              </button>
            </div>

            {showAdvanced && (
              <div className="flex items-center gap-4 px-3 py-2 rounded-xl bg-card/50 border border-border/30 animate-fade-in">
                <label className="flex items-center gap-2 text-xs cursor-pointer">
                  <input type="checkbox" checked={forceRerun} onChange={e => setForceRerun(e.target.checked)}
                    className="rounded border-border" />
                  <span className="text-secondary-text">强制重跑</span>
                  <span className="text-[10px] text-muted-text">（忽略已有结果，重新计算）</span>
                </label>
              </div>
            )}

            <div className="flex items-center gap-3 pt-1">
              <button type="button" onClick={handleRun} disabled={isRunning}
                className="btn-primary flex items-center gap-2 text-sm px-6 py-2.5">
                {isRunning ? (
                  <><svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>回测执行中...</>
                ) : (<><Play className="h-4 w-4" />开始回测</>)}
              </button>
              <span className="text-[10px] text-muted-text">
                {selectedCodes.length > 0
                  ? `将对 ${selectedCodes.length} 只股票的历史分析记录进行回测`
                  : '将对所有有历史分析的股票进行回测'}
              </span>
            </div>
          </div>
        )}

        {backtestMode === 'verify' && wizardStep === 'running' && isRunning && (
          <div className="flex flex-col items-center gap-3 py-6 animate-fade-in">
            {!streamProgress && !streamError && (
              <div className="flex flex-col items-center gap-2">
                <div className="backtest-spinner lg" />
                <p className="text-sm text-secondary-text">正在连接回测引擎...</p>
              </div>
            )}

            {streamProgress && (
              <div className="w-full max-w-md space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <svg className="h-4 w-4 text-cyan animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <span className="text-sm font-medium text-foreground">
                      {streamProgress.stage === 'analyzing' ? '自动分析中' : streamProgress.stage === 'evaluating' ? '回测评估中' : '检查中'}
                    </span>
                  </div>
                  <span className="font-mono text-sm text-cyan">{streamProgress.progressPct}%</span>
                </div>
                <div className="h-2 w-full rounded-full bg-border/20 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500 ease-out"
                    style={{
                      width: `${Math.min(100, streamProgress.progressPct)}%`,
                      background: 'linear-gradient(to right, hsl(var(--primary) / 0.3), hsl(var(--primary) / 0.65))',
                    }}
                  />
                </div>
                <p className="text-xs text-secondary-text">{streamProgress.message}</p>
                {streamProgress.codeIndex && streamProgress.codeTotal && (
                  <div className="flex items-center gap-2 text-[10px] text-muted-text">
                    <span>{streamProgress.codeIndex}/{streamProgress.codeTotal} 只</span>
                    {streamProgress.code && <span className="font-mono text-cyan">{streamProgress.code}</span>}
                  </div>
                )}
                {streamProgress.current && streamProgress.total && (
                  <div className="text-[10px] text-muted-text">
                    评估进度: {streamProgress.current}/{streamProgress.total}
                  </div>
                )}
              </div>
            )}

            {streamError && (
              <div className="flex flex-col items-center gap-2 text-center">
                <div className="h-8 w-8 rounded-full bg-danger/10 border border-danger/30 flex items-center justify-center">
                  <span className="text-danger text-sm font-bold">!</span>
                </div>
                <p className="text-sm text-danger font-medium">回测失败</p>
                <p className="text-xs text-muted-text max-w-xs">{streamError}</p>
              </div>
            )}
          </div>
        )}

        {runResult && <div className="mt-2"><RunResultBanner data={runResult} /></div>}
        {runError && <ApiErrorAlert error={runError} className="mt-2" />}
      </header>

      {backtestMode === 'verify' && wizardStep === 'results' && (
        <main className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden p-4 animate-fade-in">
          {pageError && <ApiErrorAlert error={pageError} className="mb-2" />}

          {(isLoadingPerf || isLoadingCurve || isLoadingResults) ? (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="backtest-spinner lg" />
              <p className="mt-3 text-secondary-text text-sm">正在加载回测数据...</p>
              <p className="mt-1 text-xs text-muted-text">
                {isLoadingPerf ? '绩效指标加载中' : isLoadingCurve ? '资金曲线加载中' : '回测明细加载中'}
              </p>
            </div>
          ) : (
            <>
              {overallPerf ? (
                <PerformancePanel metrics={overallPerf} title="整体表现" />
              ) : (
                <EmptyState title="暂无绩效数据"
                  description="执行回测后将在此展示整体绩效指标"
                  className="h-24 border-dashed bg-card/45 shadow-none" />
              )}

              <Card variant="gradient" padding="sm">
                <EquityCurveChart data={equityCurve} isLoading={false} />
              </Card>

              {results.length === 0 && (runResult?.analyzed ?? 0) > 0 && (runResult?.completed ?? 0) === 0 ? (
                <Card variant="gradient" padding="md">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-cyan/10 flex items-center justify-center">
                      <Loader2 className="h-5 w-5 text-cyan animate-spin" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-foreground">后台分析进行中</div>
                      <div className="text-xs text-secondary-text mt-0.5">
                        已提交 {runResult?.analyzed} 只股票到后台 AI 分析队列（4 线程并行，每只约 60 秒）。
                        分析完成后点击「重新开始」即可直接进入回测评估。
                      </div>
                    </div>
                  </div>
                </Card>
              ) : results.length === 0 ? (
                <EmptyState
                  title={runResult != null ? "回测无结果" : "暂无回测结果"}
                  description={runResult != null
                    ? "选中的股票尚无历史分析记录，请在首页中对这些股票执行分析后再回测"
                    : "点击上方「开始回测」按钮执行回测评估"}
                  className="h-32 border-dashed"
                  icon={<BarChart3 className="h-5 w-5" />}
                />
              ) : (
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-secondary-text">
                    {isNextDay ? '次日验证明细' : '回测明细'}
                  </span>
                  <span className="text-[10px] text-muted-text">
                    {selectedCodes.length > 0 ? selectedCodes.join(', ') : '全部股票'}
                    {evalDays ? ` · ${evalDays}日窗口` : ''}
                  </span>
                </div>
                <span className="text-[10px] text-muted-text">左右滑动查看更多列</span>
              </div>
              <div className="backtest-table-wrapper">
                <table className="backtest-table min-w-[780px] w-full text-xs">
                  <thead className="backtest-table-head">
                    <tr>
                      <th className="backtest-table-head-cell">股票</th>
                      <th className="backtest-table-head-cell">分析日期</th>
                      <th className="backtest-table-head-cell">AI预测</th>
                      <th className="backtest-table-head-cell">实际走势</th>
                      <th className="backtest-table-head-cell">方向正确</th>
                      <th className="backtest-table-head-cell">模拟收益</th>
                      <th className="backtest-table-head-cell">结果</th>
                      <th className="backtest-table-head-cell">状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map(row => {
                      const outcome = OUTCOME_MAP[row.outcome || ''] || { label: '--', variant: 'default' as const };
                      const movement = MOVEMENT_MAP[row.actualMovement || ''] || { label: '--', variant: 'default' as const };
                      const status = STATUS_MAP[row.evalStatus] || { label: row.evalStatus, variant: 'default' as const };
                      return (
                        <tr key={row.analysisHistoryId} className="backtest-table-row">
                          <td className="backtest-table-cell backtest-table-code">
                            <div className="flex flex-col">
                              <span>{row.code}</span>
                              <span className="text-[10px] text-muted-text">{row.stockName || '--'}</span>
                            </div>
                          </td>
                          <td className="backtest-table-cell text-secondary-text">{row.analysisDate || '--'}</td>
                          <td className="backtest-table-cell max-w-[180px]">
                            {(row.trendPrediction || row.operationAdvice) ? (
                              <Tooltip content={[row.trendPrediction, row.operationAdvice].filter(Boolean).join(' / ')} focusable>
                                <div className="flex flex-col gap-0.5">
                                  <span className="block truncate text-foreground">{row.trendPrediction || '--'}</span>
                                  <span className="block truncate text-[10px] text-muted-text">{row.operationAdvice || '--'}</span>
                                </div>
                              </Tooltip>
                            ) : '--'}
                          </td>
                          <td className="backtest-table-cell">
                            <div className="flex items-center gap-1.5">
                              <Badge variant={movement.variant}>{movement.label}</Badge>
                              <span className={colorCls(row.actualReturnPct)}>{pct(row.actualReturnPct)}</span>
                            </div>
                          </td>
                          <td className="backtest-table-cell">
                            {row.directionCorrect === true ? <span className="text-success">✓</span>
                              : row.directionCorrect === false ? <span className="text-danger">✗</span>
                              : <span className="text-muted-text">--</span>}
                            <span className="text-[10px] text-muted-text ml-1">{row.directionExpected || ''}</span>
                          </td>
                          <td className="backtest-table-cell">
                            <span className={colorCls(row.simulatedReturnPct)}>{pct(row.simulatedReturnPct)}</span>
                          </td>
                          <td className="backtest-table-cell"><Badge variant={outcome.variant} glow>{outcome.label}</Badge></td>
                          <td className="backtest-table-cell"><Badge variant={status.variant}>{status.label}</Badge></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="mt-3">
                <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={handlePageChange} />
              </div>
              <p className="text-[10px] text-muted-text text-center mt-1.5">
                共 {totalResults} 条 · 第 {currentPage} / {Math.max(totalPages, 1)} 页
              </p>
            </div>
          )}
            </>
          )}
        </main>
      )}

      {backtestMode === 'v2' && wizardStep === 'config' && (
        <main className="flex-1 overflow-y-auto px-4 py-3">
          <div className="space-y-3 animate-fade-in max-w-3xl">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-text mb-1 block">
                  选择策略 {v2Strategy && <span className="text-cyan">✓ 已选</span>}
                </label>
                <StrategySelector value={v2Strategy} onChange={setV2Strategy} disabled={v2Loading} />
              </div>
              <div className="space-y-3">
                <PresetSelector value={v2Preset} onChange={setV2Preset} disabled={v2Loading} />
                <ExitRuleForm value={v2ExitRules} onChange={setV2ExitRules} disabled={v2Loading} />
              </div>
            </div>

            {selectedStrategy && selectedStrategy.factors.length > 0 && (
              <StrategyParamForm factors={selectedStrategy.factors} values={v2Factors} onChange={(id, val) => setV2Factors((prev) => ({ ...prev, [id]: val }))} disabled={v2Loading} />
            )}

            <div className="grid grid-cols-3 gap-2">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-muted-text">初始资金</label>
                <input type="number" value={v2Cash} onChange={e => setV2Cash(Number(e.target.value))} min={10000} step={10000} className={`${INPUT_CLASS} tabular-nums text-center`} disabled={v2Loading} />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-muted-text">佣金率</label>
                <input type="number" value={v2Commission} onChange={e => setV2Commission(Number(e.target.value))} min={0} max={0.01} step={0.0001} className={`${INPUT_CLASS} tabular-nums text-center`} disabled={v2Loading} />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-muted-text">滑点率</label>
                <input type="number" value={v2Slippage} onChange={e => setV2Slippage(Number(e.target.value))} min={0} max={0.1} step={0.0001} className={`${INPUT_CLASS} tabular-nums text-center`} disabled={v2Loading} />
              </div>
            </div>

            <div className="flex items-center gap-3 pt-1">
              <button type="button" onClick={handleV2Run} disabled={v2Loading || !v2Strategy || selectedCodes.length === 0}
                className="btn-primary flex items-center gap-2 text-sm px-6 py-2.5 disabled:opacity-50">
                {v2Loading ? (
                  <><svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>回测执行中...</>
                ) : (<><Play className="h-4 w-4" />开始策略回测 (v2)</>)}
              </button>
              <span className="text-[10px] text-muted-text">
                基于 {selectedStrategy?.displayName || '选择策略'}，{selectedCodes.length} 只股票，K线数据回测
              </span>
            </div>
            {v2Error && (
              <div className="px-4 py-2.5 rounded-xl bg-danger/10 border border-danger/30 text-xs text-danger">
                {v2Error}
              </div>
            )}
          </div>
        </main>
      )}

      {backtestMode === 'v2' && wizardStep === 'running' && (
        <main className="flex-1 overflow-y-auto px-4 py-3">
          <ProgressOverlay visible={true} stage="evaluating" progressPct={50} message={`正在对 ${selectedCodes.length} 只股票执行 ${selectedStrategy?.displayName || v2Strategy}...`}>
            <div className="h-20" />
          </ProgressOverlay>
        </main>
      )}

      {backtestMode === 'optimize' && wizardStep === 'config' && (
        <main className="flex-1 overflow-y-auto px-4 py-3">
          <div className="space-y-4 animate-fade-in max-w-3xl">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-text mb-1 block">
                  选择策略 {v2Strategy && <span className="text-cyan">✓</span>}
                </label>
                <StrategySelector value={v2Strategy} onChange={setV2Strategy} disabled={optLoading} />
              </div>
              {selectedStrategy && selectedStrategy.factors.length > 0 && (
                <OptimizeConfigForm
                  factors={selectedStrategy.factors}
                  defaultRanges={Object.fromEntries(selectedStrategy.factors.map((f) => [f.id, f.range]))}
                  onRun={(params) => {
                    setWizardStep('running');
                    setCompletedSteps((prev) => {
                      const next = new Set(prev);
                      next.add('config');
                      return [...next] as WizardStep[];
                    });
                    runOpt({ ...params, strategy: v2Strategy, codes: selectedCodes });
                    setWizardStep('results');
                    setCompletedSteps((prev) => {
                      const next = new Set(prev);
                      next.add('running');
                      return [...next] as WizardStep[];
                    });
                  }}
                  loading={optLoading}
                  disabled={!v2Strategy || selectedCodes.length === 0}
                />
              )}
            </div>
            {optError && (
              <div className="px-4 py-2.5 rounded-xl bg-danger/10 border border-danger/30 text-xs text-danger">{optError}</div>
            )}
          </div>
        </main>
      )}

      {backtestMode === 'optimize' && wizardStep === 'results' && optResult && (
        <main className="flex-1 overflow-y-auto px-4 py-3">
          <div className="space-y-4 animate-fade-in max-w-5xl">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-foreground">参数优化结果</h2>
                <p className="text-[10px] text-muted-text">
                  策略: {v2Strategy} | 共 {optResult.totalTrials} 次试验 | {optResult.elapsedSeconds?.toFixed(1)}s
                </p>
              </div>
              <button type="button" onClick={() => { setWizardStep('config'); resetOpt(); }}
                className="btn-secondary flex items-center gap-1 text-[10px]">
                <RotateCcw className="h-3 w-3" />重新优化
              </button>
            </div>

            <div className="grid grid-cols-3 gap-2">
              {[
                { label: '最优值', value: optResult.bestValue.toFixed(3), sub: '' },
                { label: '最优收益', value: `${(optResult.bestStats.returnPct ?? 0) >= 0 ? '+' : ''}${(optResult.bestStats.returnPct ?? 0).toFixed(2)}%`, sub: '' },
                { label: '最优夏普', value: (optResult.bestStats.sharpeRatio ?? 0).toFixed(2), sub: '' },
              ].map((m, i) => (
                <div key={i} className="flex flex-col items-center gap-0.5 px-2 py-2 rounded-xl bg-card/50 border border-border/30">
                  <span className="text-lg font-bold tabular-nums text-cyan">{m.value}</span>
                  <span className="text-[9px] text-muted-text">{m.label}</span>
                </div>
              ))}
            </div>

            <div className="rounded-xl bg-card/30 border border-border/20 p-3">
              <h3 className="text-[10px] font-medium text-cyan mb-2">最优参数</h3>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(optResult.bestParams).map(([k, v]) => (
                  <div key={k} className="flex justify-between text-[10px]">
                    <span className="text-muted-text">{k}</span>
                    <span className="font-mono text-foreground">{typeof v === 'number' ? v.toFixed(2) : String(v)}</span>
                  </div>
                ))}
              </div>
            </div>

            <ParamHeatmap heatmap={optResult.heatmap} />

            {optResult.heatmap?.data ? (
              <ParamSensitivityHeatmap
                data={(() => {
                  const hm = optResult.heatmap as { data: Record<number, Record<number, number>>; x_param: string; y_param: string };
                  const xVals = Object.keys(hm.data).map(Number);
                  const yKeys = [...new Set(xVals.flatMap((x) => Object.keys(hm.data[x] || {}).map(Number)))];
                  const allVals = xVals.flatMap((x) => yKeys.map((y) => hm.data[x]?.[y] ?? 0)).filter((v: number) => v !== 0);
                  const maxAbs = Math.max(1, Math.abs(Math.max(...allVals)), Math.abs(Math.min(...allVals)));
                  const cells: Array<{ metric: string; paramName: string; score: number }> = xVals.flatMap((x) =>
                    yKeys.map((y) => ({
                      metric: y.toFixed(1),
                      paramName: String(hm.x_param),
                      score: Math.abs((hm.data[x]?.[y] ?? 0) / maxAbs),
                    }))
                  ) as Array<{ metric: string; paramName: string; score: number }>;
                  return cells;
                })()}
                params={[String((optResult.heatmap as Record<string, unknown>).x_param || optResult.heatmap?.x_param || (Object.keys(optResult.bestParams))[0] || 'param')]}
                metrics={Object.keys(optResult.bestParams).length > 0 ? (Object.keys(optResult.bestParams) as string[]) : ['return', 'sharpe']}
              />
            ) : null}

            <div className="rounded-xl bg-card/30 border border-border/20 p-3">
              <h3 className="text-[10px] font-medium text-cyan mb-2">优化后策略回测详情</h3>
              <div className="grid grid-cols-4 gap-3">
                {[
                  { title: '收益', rows: [['总收益', optResult.bestStats.returnPct, '%'], ['年化', optResult.bestStats.returnAnnPct, '%'], ['CAGR', optResult.bestStats.cagrPct, '%']] },
                  { title: '风险', rows: [['最大回撤', optResult.bestStats.maxDrawdownPct, '%'], ['平均回撤', optResult.bestStats.avgDrawdownPct, '%'], ['波动率', optResult.bestStats.volatilityAnnPct, '%']] },
                  { title: '交易', rows: [['次数', optResult.bestStats.tradeCount, ''], ['胜率', optResult.bestStats.winRatePct, '%'], ['盈亏比', optResult.bestStats.profitFactor, '']] },
                  { title: '调整', rows: [['夏普', optResult.bestStats.sharpeRatio, ''], ['Sortino', optResult.bestStats.sortinoRatio, ''], ['Calmar', optResult.bestStats.calmarRatio, '']] },
                ].map((group, gi) => (
                  <div key={gi} className="rounded-xl bg-card/30 border border-border/20 p-3">
                    <h3 className="text-[10px] font-medium text-cyan mb-2">{group.title}</h3>
                    {group.rows.map((row: (string | number | undefined)[], ri: number) => {
                      const label = String(row[0] ?? '');
                      const value = row[1];
                      const suffix = String(row[2] ?? '');
                      return (
                        <div key={ri} className="flex justify-between text-[10px] py-0.5">
                          <span className="text-muted-text">{label}</span>
                          <span className="font-mono tabular-nums text-foreground">{value != null ? `${Number(value).toFixed(2)}${suffix}` : '--'}</span>
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </main>
      )}

      {backtestMode === 'montecarlo' && wizardStep === 'config' && (
        <main className="flex-1 overflow-y-auto px-4 py-3">
          <div className="space-y-4 animate-fade-in max-w-3xl">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted-text mb-1 block">选择策略</label>
                <StrategySelector value={v2Strategy} onChange={setV2Strategy} disabled={mcLoading} />
              </div>
              <div className="space-y-3">
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] text-muted-text">模拟次数</label>
                  <div className="flex items-center gap-1">
                    {[100, 500, 1000, 5000].map((n) => (
                      <button key={n} type="button" onClick={() => setMCN(n)} disabled={mcLoading}
                        className={`px-2 py-1 rounded text-[10px] ${mcN === n ? 'bg-cyan/10 text-cyan border border-cyan/20' : 'text-muted-text border border-border/30 hover:text-foreground'}`}>
                        {n}
                      </button>
                    ))}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={async () => {
                    if (!v2Strategy || selectedCodes.length === 0) return;
                    setWizardStep('running');
                    setCompletedSteps((prev) => {
                      const next = new Set(prev);
                      next.add('config');
                      return [...next] as WizardStep[];
                    });
                    await runMC({ strategy: v2Strategy, codes: selectedCodes, nSimulations: mcN, startDate: dateFrom || undefined, endDate: dateTo || undefined });
                    setWizardStep('results');
                    setCompletedSteps((prev) => {
                      const next = new Set(prev);
                      next.add('running');
                      return [...next] as WizardStep[];
                    });
                  }}
                  disabled={mcLoading || !v2Strategy || selectedCodes.length === 0}
                  className="w-full py-2.5 rounded-lg bg-cyan/10 border border-cyan/20 text-cyan text-xs font-medium hover:bg-cyan/20 disabled:opacity-50 transition-colors"
                >
                  {mcLoading ? '蒙特卡洛模拟中...' : `开始蒙特卡洛模拟 (${mcN} 次)`}
                </button>
                <p className="text-[9px] text-muted-text">
                  对策略进行随机数据鲁棒性测试。模拟次数越多结果越可靠，但耗时更长。
                </p>
              </div>
            </div>
            {mcError && (
              <div className="px-4 py-2.5 rounded-xl bg-danger/10 border border-danger/30 text-xs text-danger">{mcError}</div>
            )}
          </div>
        </main>
      )}

      {backtestMode === 'montecarlo' && wizardStep === 'results' && mcResult && (
        <main className="flex-1 overflow-y-auto px-4 py-3">
          <div className="space-y-4 animate-fade-in max-w-5xl">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-foreground">蒙特卡洛模拟</h2>
                <p className="text-[10px] text-muted-text">策略: {v2Strategy} | {mcResult.nSimulations} 次模拟 | {mcResult.elapsedSeconds?.toFixed(1)}s</p>
              </div>
              <button type="button" onClick={() => { setWizardStep('config'); resetMC(); }}
                className="btn-secondary flex items-center gap-1 text-[10px]">
                <RotateCcw className="h-3 w-3" />重新模拟
              </button>
            </div>
            <MonteCarloResult
              originalStats={mcResult.originalStats}
              medianReturn={mcResult.medianReturnPct}
              p5Return={mcResult.p5ReturnPct}
              p95Return={mcResult.p95ReturnPct}
              ruinProbability={mcResult.ruinProbability}
              results={mcResult.results}
              nSimulations={mcResult.nSimulations}
            />
          </div>
        </main>
      )}

      {backtestMode === 'v2' && wizardStep === 'results' && v2Result && (
        <main className="flex-1 overflow-y-auto px-4 py-3">
          <div className="space-y-4 animate-fade-in max-w-5xl">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-foreground">{v2Result.strategyName}</h2>
                <p className="text-[10px] text-muted-text">{v2Result.symbol} | {v2Result.startDate} ~ {v2Result.endDate} | 初始 ¥{v2Result.initialCash.toLocaleString()} | {v2Result.elapsedSeconds?.toFixed(2)}s</p>
              </div>
              <div className="flex items-center gap-2">
                <BacktestReportExport onExport={exportV2Report} />
                <button type="button" onClick={() => { setWizardStep('config'); resetV2(); }} className="btn-secondary flex items-center gap-1 text-[10px]">
                  <RotateCcw className="h-3 w-3" />重新配置
                </button>
              </div>
            </div>

            <AISummaryCard stats={v2Result.stats as unknown as Record<string, number>} strategyName={v2Result.strategyName} symbol={v2Result.symbol} />

            <ParamChangeHistory history={paramHistory} onSelect={() => {}} />

            <div className="grid grid-cols-4 gap-2">
              {[
                { label: '累计收益', value: `${(v2Result.stats.returnPct ?? 0) >= 0 ? '+' : ''}${(v2Result.stats.returnPct ?? 0).toFixed(2)}%`, tone: (v2Result.stats.returnPct ?? 0) >= 0 ? 'text-success' : 'text-danger' as const },
                { label: '夏普比率', value: (v2Result.stats.sharpeRatio ?? 0).toFixed(2), tone: (v2Result.stats.sharpeRatio ?? 0) >= 1 ? 'text-success' : (v2Result.stats.sharpeRatio ?? 0) >= 0 ? 'text-warning' : 'text-danger' as const },
                { label: '最大回撤', value: `${(v2Result.stats.maxDrawdownPct ?? 0).toFixed(2)}%`, tone: Math.abs(v2Result.stats.maxDrawdownPct ?? 0) <= 10 ? 'text-success' : Math.abs(v2Result.stats.maxDrawdownPct ?? 0) <= 20 ? 'text-warning' : 'text-danger' as const },
                { label: '胜率', value: `${(v2Result.stats.winRatePct ?? 0).toFixed(1)}%`, tone: (v2Result.stats.winRatePct ?? 0) >= 50 ? 'text-success' : (v2Result.stats.winRatePct ?? 0) >= 30 ? 'text-warning' : 'text-danger' as const },
              ].map((m, i) => (
                <div key={i} className="flex flex-col items-center gap-0.5 px-3 py-2 rounded-xl bg-card/50 border border-border/30">
                  <span className={`text-lg font-bold tabular-nums ${m.tone}`}>{m.value}</span>
                  <span className="text-[10px] text-muted-text">{m.label}</span>
                </div>
              ))}
            </div>

            <V2EquityCurveChart data={v2Result.equityCurve} initialCash={v2Result.initialCash} height={280} />

            <DrawdownChart equityCurve={v2Result.equityCurve} />

            <KlineTradeChart equityCurve={v2Result.equityCurve} trades={v2Result.trades} />

            <MonthlyHeatmap equityCurve={v2Result.equityCurve} />

            <ExitReasonPieChart trades={v2Result.trades || []} />

            <SignalFunnel stats={v2Result.stats as unknown as Record<string, number>} exitRules={v2ExitRules} />

            <TradeTimeline trades={v2Result.trades || []} maxItems={5} />

            <div className="grid grid-cols-4 gap-3">
              {[
                { title: '收益', rows: [['总收益率', v2Result.stats.returnPct, '%'], ['年化收益', v2Result.stats.returnAnnPct, '%'], ['CAGR', v2Result.stats.cagrPct, '%'], ['买入持有', v2Result.stats.buyHoldReturnPct, '%']] },
                { title: '风险', rows: [['年化波动', v2Result.stats.volatilityAnnPct, '%'], ['最大回撤', v2Result.stats.maxDrawdownPct, '%'], ['平均回撤', v2Result.stats.avgDrawdownPct, '%']] },
                { title: '交易', rows: [['交易次数', v2Result.stats.tradeCount, ''], ['胜率', v2Result.stats.winRatePct, '%'], ['盈亏比', v2Result.stats.profitFactor, ''], ['SQN', v2Result.stats.sqn, '']] },
                { title: '风险调整', rows: [['夏普', v2Result.stats.sharpeRatio, ''], ['Sortino', v2Result.stats.sortinoRatio, ''], ['Calmar', v2Result.stats.calmarRatio, ''], ['Alpha', v2Result.stats.alphaPct, '%']] },
              ].map((group, gi) => (
                <div key={gi} className="rounded-xl bg-card/30 border border-border/20 p-3">
                  <h3 className="text-[10px] font-medium text-cyan mb-2">{group.title}</h3>
                  {group.rows.map((row: (string | number | undefined)[], ri: number) => {
                    const label = String(row[0] ?? '');
                    const value = row[1];
                    const suffix = String(row[2] ?? '');
                    return (
                    <div key={ri} className="flex justify-between text-[10px] py-0.5">
                      <span className="text-muted-text">{label}</span>
                      <span className="font-mono tabular-nums text-foreground">{value != null ? `${Number(value).toFixed(2)}${suffix}` : '--'}</span>
                    </div>
                  )})}
                </div>
              ))}
            </div>

            {v2Result.trades && v2Result.trades.length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-secondary-text mb-2">交易明细 ({v2Result.trades.length} 笔)</h3>
                <div className="overflow-x-auto rounded-lg border border-border/20">
                  <table className="w-full text-[10px]">
                    <thead className="bg-border/10">
                      <tr>
                        <th className="text-left px-2 py-1.5 text-muted-text">入场</th>
                        <th className="text-left px-2 py-1.5 text-muted-text">出场</th>
                        <th className="text-right px-2 py-1.5 text-muted-text">入场价</th>
                        <th className="text-right px-2 py-1.5 text-muted-text">出场价</th>
                        <th className="text-right px-2 py-1.5 text-muted-text">收益</th>
                        <th className="text-left px-2 py-1.5 text-muted-text">平仓原因</th>
                      </tr>
                    </thead>
                    <tbody>
                      {v2Result.trades.slice(0, 50).map((t, ti) => (
                        <tr key={ti} className="border-t border-border/10 hover:bg-border/5">
                          <td className="px-2 py-1 font-mono text-muted-text">{t.entryTime?.slice(0, 10) || t.entryBar}</td>
                          <td className="px-2 py-1 font-mono text-muted-text">{t.exitTime?.slice(0, 10) || t.exitBar || '--'}</td>
                          <td className={`px-2 py-1 font-mono text-right ${t.size > 0 ? 'text-success' : 'text-danger'}`}>{t.entryPrice?.toFixed(2)}</td>
                          <td className="px-2 py-1 font-mono text-right">{t.exitPrice?.toFixed(2) || '--'}</td>
                          <td className={`px-2 py-1 font-mono text-right ${(t.returnPct ?? 0) >= 0 ? 'text-success' : 'text-danger'}`}>{(t.returnPct ?? 0) >= 0 ? '+' : ''}{(t.returnPct ?? 0).toFixed(2)}%</td>
                          <td className="px-2 py-1"><span className={`inline-block px-1.5 py-0.5 rounded text-[9px] ${t.exitReason === 'take_profit' ? 'bg-success/10 text-success' : t.exitReason === 'trailing_stop' ? 'bg-warning/10 text-warning' : t.exitReason === 'stop_loss' ? 'bg-danger/10 text-danger' : 'bg-muted/10 text-muted-text'}`}>{t.exitReason || '--'}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

          </div>
        </main>
      )}
    </div>
  );
};

export default BacktestPage;
