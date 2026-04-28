import type React from 'react';
import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Play, RefreshCw, Target, Zap,
  Database, Loader2, CheckCircle2, XCircle, AlertTriangle,
} from 'lucide-react';
import { alphaApi } from '../api/alpha';
import type { AlphaMetrics, AlphaHealthItem } from '../api/alpha';
import { useAlphaStream } from '../hooks/useAlphaStream';
import type { AlphaProgress } from '../hooks/useAlphaStream';
import { getParsedApiError } from '../api/error';
import type { ParsedApiError } from '../api/error';
import { ApiErrorAlert, Card, EmptyState, StatCard } from '../components/common';

const formatPct = (v?: number) => (v != null ? `${v > 0 ? '+' : ''}${v.toFixed(2)}%` : '--');
const formatIR = (v?: number) => (v != null ? v.toFixed(4) : '--');

const AlphaPage: React.FC = () => {
  useEffect(() => { document.title = 'Alpha超额收益 - DSA'; }, []);

  const [benchmark, setBenchmark] = useState('000300');
  const [topN, setTopN] = useState(20);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<ParsedApiError | null>(null);
  const [alphaProgress, setAlphaProgress] = useState<AlphaProgress | null>(null);
  const [lastMetrics, setLastMetrics] = useState<AlphaMetrics | null>(null);

  const [health, setHealth] = useState<AlphaHealthItem[]>([]);
  const [healthSummary, setHealthSummary] = useState<{ healthy: number; aged: number; total: number } | null>(null);
  const [isLoadingHealth, setIsLoadingHealth] = useState(false);
  const [bestConfig, setBestConfig] = useState<Record<string, unknown> | null>(null);

  const { isConnected: sseConnected } = useAlphaStream({
    onProgress: (p) => {
      setAlphaProgress(p);
      if (p.status === 'completed' && p.metrics) {
        setLastMetrics(p.metrics as unknown as AlphaMetrics);
        setIsRunning(false);
      }
      if (p.status === 'failed') {
        setIsRunning(false);
        setRunError({ title: 'Alpha失败', message: p.message, rawMessage: p.message, category: 'unknown' });
      }
    },
  });

  const fetchHealth = useCallback(async () => {
    setIsLoadingHealth(true);
    try {
      const h = await alphaApi.getHealth();
      setHealth(h.factors || []);
      setHealthSummary({ healthy: h.healthy, aged: h.aged, total: h.totalFactors });
    } catch { /* ignore */ }
    setIsLoadingHealth(false);
  }, []);

  const fetchBestConfig = useCallback(async () => {
    try {
      const c = await alphaApi.getBestConfig();
      if (c.status === 'ok' && c.config) setBestConfig(c.config);
    } catch { /* ignore */ }
  }, []);

  const isInitialMount = useRef(true);
  useEffect(() => {
    void (async () => {
      if (isInitialMount.current) {
        isInitialMount.current = false;
        await fetchHealth();
        await fetchBestConfig();
      }
    })();
  }, [fetchHealth, fetchBestConfig]);

  const handleRun = async () => {
    setIsRunning(true);
    setRunError(null);
    setLastMetrics(null);
    try {
      await alphaApi.run({ benchmarkCode: benchmark, topN });
    } catch (err) {
      const parsed = getParsedApiError(err);
      setRunError(parsed);
      setIsRunning(false);
    }
  };

  const handleAuto = async () => {
    setIsRunning(true);
    setRunError(null);
    try {
      await alphaApi.auto({ benchmarkCode: benchmark, topN, maxIterations: 50 });
    } catch (err) {
      const parsed = getParsedApiError(err);
      setRunError(parsed);
      setIsRunning(false);
    }
  };

  return (
    <div className="min-h-full flex flex-col rounded-[1.5rem] bg-transparent">
      <header className="flex-shrink-0 border-b border-white/5 px-4 py-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <h1 className="text-sm font-semibold text-foreground">Alpha 超额收益</h1>
            <span className="text-[10px] text-muted-text bg-white/5 rounded-lg px-2 py-0.5">
              SSE {sseConnected ? <span className="text-success">●</span> : <span className="text-muted-text">○</span>}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <select value={benchmark} onChange={(e) => setBenchmark(e.target.value)}
            className="input-surface input-focus-glow h-8 rounded-lg border bg-transparent px-2 text-xs">
            <option value="000300">沪深300</option>
            <option value="000905">中证500</option>
            <option value="000852">中证1000</option>
          </select>
          <label className="flex items-center gap-1 text-xs text-secondary-text">
            Top-N
            <input type="number" value={topN} onChange={(e) => setTopN(Number(e.target.value))}
              className="input-surface input-focus-glow h-8 w-14 rounded-lg border bg-transparent px-2 text-xs text-center" min={5} max={50} />
          </label>
          <button type="button" onClick={handleRun} disabled={isRunning}
            className="btn-primary flex items-center gap-1.5 text-xs h-8 px-3">
            {isRunning ? <><Loader2 className="h-3.5 w-3.5 animate-spin" />运行中...</> : <><Play className="h-3.5 w-3.5" />运行</>}
          </button>
          <button type="button" onClick={handleAuto} disabled={isRunning}
            className="btn-secondary flex items-center gap-1.5 text-xs h-8 px-3">
            {isRunning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Zap className="h-3.5 w-3.5" />}
            自动优化
          </button>
          <button type="button" onClick={fetchHealth} disabled={isLoadingHealth}
            className="btn-ghost flex items-center gap-1.5 text-xs h-8 px-2">
            <RefreshCw className={`h-3.5 w-3.5 ${isLoadingHealth ? 'animate-spin' : ''}`} />
            因子健康
          </button>
        </div>

        {runError && <ApiErrorAlert error={runError} className="mt-2" />}

        {alphaProgress && alphaProgress.status === 'running' && (
          <div className="mt-2 rounded-xl border border-cyan/20 bg-cyan/5 p-3 animate-fade-in">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Loader2 className="h-3.5 w-3.5 text-cyan animate-spin" />
                <span className="text-xs font-medium text-foreground">{alphaProgress.message}</span>
              </div>
              <span className="text-xs font-mono text-cyan">{alphaProgress.progressPct.toFixed(0)}%</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-white/5">
              <div className="h-full rounded-full bg-gradient-to-r from-cyan to-blue-500 transition-all duration-500"
                style={{ width: `${Math.min(100, alphaProgress.progressPct)}%` }} />
            </div>
          </div>
        )}
      </header>

      <main className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto p-4 animate-fade-in">
        {lastMetrics && (
          <section>
            <h2 className="text-xs font-semibold text-secondary-text mb-2 uppercase tracking-wider">最近一次运行</h2>
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
              <StatCard label="信息比率" value={formatIR(lastMetrics.informationRatio)} />
              <StatCard label="超额收益" value={formatPct(lastMetrics.excessReturnPct)} />
              <StatCard label="夏普比率" value={formatIR(lastMetrics.sharpeRatio)} />
              <StatCard label="最大回撤" value={formatPct(lastMetrics.maxDrawdownPct)} />
              <StatCard label="总收益" value={formatPct(lastMetrics.totalReturnPct)} />
              <StatCard label="年化收益" value={formatPct(lastMetrics.annualizedReturnPct)} />
              <StatCard label="跟踪误差" value={formatPct(lastMetrics.trackingErrorPct)} />
            </div>
          </section>
        )}

        {bestConfig && (
          <Card variant="gradient" padding="sm">
            <div className="flex items-center gap-2 mb-2">
              <Database className="h-3.5 w-3.5 text-cyan" />
              <span className="text-xs font-medium text-foreground">历史最优配置</span>
            </div>
            <div className="text-xs text-secondary-text">
              {Object.entries(bestConfig.strategies || {}).slice(0, 5).map(([name, cfg]) => (
                <div key={name} className="flex items-center gap-2 mb-1">
                  <span className="text-foreground font-mono">{name}</span>
                  <span className="text-muted-text">权重={(cfg as { weight?: number }).weight?.toFixed(2)}</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {healthSummary && (
          <section>
            <h2 className="text-xs font-semibold text-secondary-text mb-2 uppercase tracking-wider">因子健康</h2>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs text-success">{healthSummary.healthy} 健康</span>
              {healthSummary.aged > 0 && <span className="text-xs text-danger">{healthSummary.aged} 老化</span>}
              <span className="text-xs text-muted-text">/ {healthSummary.total} 总计</span>
            </div>
            <div className="space-y-1 max-h-48 overflow-auto">
              {health.slice(0, 15).map((f, i) => {
                const icon = f.status === 'healthy' ? <CheckCircle2 className="h-3 w-3 text-success" />
                  : f.status === 'warning' ? <AlertTriangle className="h-3 w-3 text-warning" />
                    : <XCircle className="h-3 w-3 text-danger" />;
                return (
                  <div key={i} className="flex items-center gap-2 text-xs py-0.5">
                    {icon}
                    <span className="text-secondary-text font-mono">{f.strategy}:{f.factor}</span>
                    <span className={`font-mono ${(f.ic || 0) > 0 ? 'text-success' : 'text-danger'}`}>IC={f.ic?.toFixed(4)}</span>
                    <span className="text-muted-text">IR={f.icIr?.toFixed(2)}</span>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {!lastMetrics && !isRunning && !runError && (
          <EmptyState
            title="Alpha 超额收益系统"
            description="基于多因子模型的超额收益预测框架。运行 Alpha Pipeline 以查看: 截面Alpha打分 → 风险中性化 → 组合模拟 → 超额评估 vs 沪深300"
            className="border-dashed h-48"
            icon={<Target className="h-6 w-6" />}
          />
        )}
      </main>
    </div>
  );
};

export default AlphaPage;
