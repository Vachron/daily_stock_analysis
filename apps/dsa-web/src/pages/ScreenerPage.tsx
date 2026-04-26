import type React from 'react';
import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Crosshair,
  Eye,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Play,
  BarChart3,
  Database,
  X,
  Timer,
  Layers,
  Clock,
  Target,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from 'lucide-react';
import { screenerApi } from '../api/screener';
import { getParsedApiError } from '../api/error';
import type { ParsedApiError } from '../api/error';
import type { PoolStatusResponse, PoolSummaryResponse } from '../types/screener';
import {
  ApiErrorAlert,
  Badge,
  Card,
  EmptyState,
  StatCard,
  Tooltip,
} from '../components/common';
import type {
  ScreenerPickItem,
  ScreenerPerformanceResponse,
  StrategyScores,
  DataFetchFailure,
} from '../types/screener';

type TabKey = 'today' | 'watch' | 'performance';

function pct(value?: number | null): string {
  if (value == null) return '--';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function capYi(value?: number | null): string {
  if (value == null) return '--';
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万亿`;
  return `${value.toFixed(1)}亿`;
}

function statusBadge(status: string) {
  switch (status) {
    case 'watch':
      return <Badge variant="info">观察中</Badge>;
    case 'closed':
      return <Badge variant="default">已关闭</Badge>;
    default:
      return <Badge variant="default">{status}</Badge>;
  }
}

function exitReasonBadge(reason?: string | null) {
  if (!reason) return null;
  switch (reason) {
    case 'stop_loss':
      return <Badge variant="danger">止损</Badge>;
    case 'take_profit':
      return <Badge variant="success">止盈</Badge>;
    case 'window_expired':
      return <Badge variant="warning">到期</Badge>;
    default:
      return <Badge variant="default">{reason}</Badge>;
  }
}

function returnCell(value?: number | null) {
  if (value == null) return <span className="text-secondary-text">--</span>;
  const cls = value > 0 ? 'text-success' : value < 0 ? 'text-danger' : 'text-secondary-text';
  return <span className={`font-mono tabular-nums ${cls}`}>{pct(value)}</span>;
}

function scoreBar(score: number) {
  const pctVal = Math.min(100, Math.max(0, score));
  const color =
    pctVal >= 80 ? 'bg-success' : pctVal >= 60 ? 'bg-cyan' : pctVal >= 40 ? 'bg-warning' : 'bg-danger';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 rounded-full bg-elevated/75">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pctVal}%` }} />
      </div>
      <span className="font-mono text-xs tabular-nums text-foreground">{score.toFixed(0)}</span>
    </div>
  );
}

const TAB_ITEMS: { key: TabKey; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'today', label: '今日选股', icon: Crosshair },
  { key: 'watch', label: '观察池', icon: Eye },
  { key: 'performance', label: '表现统计', icon: BarChart3 },
];

const ScreenerPage: React.FC = () => {
  useEffect(() => {
    document.title = '智能选股 - DSA';
  }, []);

  const [activeTab, setActiveTab] = useState<TabKey>('today');
  const [pageError, setPageError] = useState<ParsedApiError | null>(null);

  // Today picks
  const [todayPicks, setTodayPicks] = useState<ScreenerPickItem[]>([]);
  const [todayDate, setTodayDate] = useState('');
  const [isLoadingPicks, setIsLoadingPicks] = useState(false);

  // Run screener
  const [topN, setTopN] = useState(10);
  const [scanMode, setScanMode] = useState<string>('quality_only');
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<ParsedApiError | null>(null);
  const [dataFailures, setDataFailures] = useState<DataFetchFailure[]>([]);
  const [qualitySummary, setQualitySummary] = useState<Record<string, number> | null>(null);

  // Watch list
  const [watchList, setWatchList] = useState<ScreenerPickItem[]>([]);
  const [isLoadingWatch, setIsLoadingWatch] = useState(false);
  const [isUpdatingTracking, setIsUpdatingTracking] = useState(false);

  // Performance
  const [perf, setPerf] = useState<ScreenerPerformanceResponse | null>(null);
  const [isLoadingPerf, setIsLoadingPerf] = useState(false);

  // Backtest feedback
  const [isFeedbacking, setIsFeedbacking] = useState(false);

  const [poolStatus, setPoolStatus] = useState<PoolStatusResponse | null>(null);
  const [poolSummary, setPoolSummary] = useState<PoolSummaryResponse | null>(null);
  const [isInitingPool, setIsInitingPool] = useState(false);
  const [showPoolPanel, setShowPoolPanel] = useState(false);
  const poolPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchTodayPicks = useCallback(async () => {
    setIsLoadingPicks(true);
    try {
      const data = await screenerApi.getTodayPicks();
      setTodayPicks(data.picks);
      setTodayDate(data.date);
      setPageError(null);
    } catch (err) {
      console.error('Failed to fetch today picks:', err);
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingPicks(false);
    }
  }, []);

  const fetchWatchList = useCallback(async () => {
    setIsLoadingWatch(true);
    try {
      const data = await screenerApi.getWatchList(30);
      setWatchList(data.watchList);
      setPageError(null);
    } catch (err) {
      console.error('Failed to fetch watch list:', err);
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingWatch(false);
    }
  }, []);

  const fetchPerformance = useCallback(async () => {
    setIsLoadingPerf(true);
    try {
      const data = await screenerApi.getPerformance();
      setPerf(data);
      setPageError(null);
    } catch (err) {
      console.error('Failed to fetch performance:', err);
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingPerf(false);
    }
  }, []);

  useEffect(() => {
    fetchTodayPicks();
  }, [fetchTodayPicks]);

  useEffect(() => {
    if (activeTab === 'watch' && watchList.length === 0) {
      fetchWatchList();
    }
    if (activeTab === 'performance' && !perf) {
      fetchPerformance();
    }
  }, [activeTab]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchPoolStatus = useCallback(async () => {
    try {
      const data = await screenerApi.getPoolStatus();
      setPoolStatus(data);
      if (data.status === 'completed' && !poolSummary) {
        const summary = await screenerApi.getPoolSummary();
        setPoolSummary(summary);
      }
    } catch (err) {
      console.error('Failed to fetch pool status:', err);
    }
  }, [poolSummary]);

  const startPoolPolling = useCallback(() => {
    if (poolPollRef.current) return;
    let pollCount = 0;
    const MAX_POLLS = 1200;
    poolPollRef.current = setInterval(async () => {
      if (document.visibilityState !== 'visible') return;
      pollCount++;
      if (pollCount > MAX_POLLS) {
        if (poolPollRef.current) {
          clearInterval(poolPollRef.current);
          poolPollRef.current = null;
        }
        return;
      }
      try {
        const data = await screenerApi.getPoolStatus();
        setPoolStatus(data);
        if (data.status !== 'running') {
          if (poolPollRef.current) {
            clearInterval(poolPollRef.current);
            poolPollRef.current = null;
          }
          if (data.status === 'completed') {
            const summary = await screenerApi.getPoolSummary();
            setPoolSummary(summary);
          }
        }
      } catch (err) {
        console.error('Pool status poll failed:', err);
      }
    }, 3000);
  }, []);

  useEffect(() => {
    fetchPoolStatus();
    return () => {
      if (poolPollRef.current) {
        clearInterval(poolPollRef.current);
        poolPollRef.current = null;
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (poolStatus?.status === 'running') {
      startPoolPolling();
    }
  }, [poolStatus?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRun = async () => {
    setIsRunning(true);
    setRunError(null);
    setDataFailures([]);
    try {
      const result = await screenerApi.run({ topN, scanMode });
      if (result.dataFailures && result.dataFailures.length > 0) {
        setDataFailures(result.dataFailures);
      }
      if (result.qualitySummary) {
        setQualitySummary(result.qualitySummary);
      }
      await fetchTodayPicks();
      if (activeTab === 'watch') await fetchWatchList();
      if (activeTab === 'performance') await fetchPerformance();
    } catch (err) {
      setRunError(getParsedApiError(err));
    } finally {
      setIsRunning(false);
    }
  };

  const handleUpdateTracking = async () => {
    setIsUpdatingTracking(true);
    try {
      await screenerApi.updateTracking();
      await fetchWatchList();
    } catch (err) {
      setPageError(getParsedApiError(err));
    } finally {
      setIsUpdatingTracking(false);
    }
  };

  const handleBacktestFeedback = async () => {
    setIsFeedbacking(true);
    try {
      await screenerApi.applyBacktestFeedback();
      await fetchWatchList();
      await fetchPerformance();
    } catch (err) {
      setPageError(getParsedApiError(err));
    } finally {
      setIsFeedbacking(false);
    }
  };

  const handleInitPool = async () => {
    setIsInitingPool(true);
    try {
      await screenerApi.initPool(45);
      await fetchPoolStatus();
      startPoolPolling();
    } catch (err) {
      setPageError(getParsedApiError(err));
    } finally {
      setIsInitingPool(false);
    }
  };

  const handleCancelPool = async () => {
    try {
      await screenerApi.cancelPoolInit();
      await fetchPoolStatus();
    } catch (err) {
      setPageError(getParsedApiError(err));
    }
  };

  const formatEta = (seconds: number): string => {
    if (seconds <= 0) return '计算中...';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (mins > 60) {
      const hours = Math.floor(mins / 60);
      const remainMins = mins % 60;
      return `约 ${hours} 小时 ${remainMins} 分`;
    }
    if (mins > 0) return `约 ${mins} 分 ${secs} 秒`;
    return `${secs} 秒`;
  };

  const renderTodayTab = () => {
    if (isLoadingPicks) {
      return (
        <div className="flex flex-col items-center justify-center h-64">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
          <p className="mt-3 text-secondary-text text-sm">加载选股结果...</p>
        </div>
      );
    }

    if (todayPicks.length === 0) {
      return (
        <EmptyState
          title="暂无选股结果"
          description="点击「开始选股」从全市场A股中筛选优质标的"
          className="border-dashed"
          icon={<Crosshair className="h-6 w-6" />}
          action={
            <button type="button" onClick={handleRun} className="btn-primary">
              开始选股
            </button>
          }
        />
      );
    }

    const sortedPicks = [...todayPicks].sort((a, b) => (b.score ?? 0) - (a.score ?? 0));

    return (
      <div className="animate-fade-in">
        <div className="mb-3 flex items-center gap-3 flex-wrap">
          <span className="label-uppercase">选股日期</span>
          <span className="text-sm font-mono text-foreground">{todayDate}</span>
          <span className="text-xs text-secondary-text">共 {sortedPicks.length} 只</span>
          {sortedPicks.length > 0 && (() => {
            const first = sortedPicks[0] as unknown as Record<string, unknown>;
            const regime = first.marketRegime as string | undefined;
            const regimeLabel = first.marketRegimeLabel as string | undefined;
            if (regime) {
              return (
                <>
                  <span className="text-border">|</span>
                  <span className="text-xs text-secondary-text">市场状态</span>
                  <Badge variant={regime === 'trending_up' ? 'success' : regime === 'trending_down' ? 'danger' : 'info'}>
                    {regimeLabel || regime}
                  </Badge>
                </>
              );
            }
            return null;
          })()}
          {qualitySummary && Object.keys(qualitySummary).length > 0 && (
            <>
              <span className="text-border">|</span>
              <span className="text-xs text-secondary-text">质量分布</span>
              {qualitySummary.premium > 0 && <Badge variant="success">优质 {qualitySummary.premium}</Badge>}
              {qualitySummary.standard > 0 && <Badge variant="info">标准 {qualitySummary.standard}</Badge>}
              {qualitySummary.marginal > 0 && <Badge variant="warning">边缘 {qualitySummary.marginal}</Badge>}
              {qualitySummary.excluded > 0 && <Badge variant="danger">排除 {qualitySummary.excluded}</Badge>}
            </>
          )}
        </div>
        {dataFailures.length > 0 && (
          <div className="mb-3 rounded-lg border border-warning/40 bg-warning/5 p-3">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-4 w-4 text-warning" />
              <span className="text-sm font-medium text-warning">
                {dataFailures.length} 只股票历史数据获取失败，已降级为基础因子评分
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {dataFailures.slice(0, 10).map((f) => (
                <Tooltip key={f.code} content={`${f.name}(${f.code}): ${f.reason}`}>
                  <Badge variant="warning">{f.name || f.code}</Badge>
                </Tooltip>
              ))}
              {dataFailures.length > 10 && (
                <Badge variant="default">+{dataFailures.length - 10} 更多</Badge>
              )}
            </div>
          </div>
        )}
        <div className="screener-table-wrapper overflow-x-auto rounded-xl border border-border/40">
          <table className="w-full min-w-[780px] text-sm">
            <thead className="screener-table-head">
              <tr className="text-left">
                <th className="screener-table-head-cell">排名</th>
                <th className="screener-table-head-cell">股票</th>
                <th className="screener-table-head-cell">综合评分</th>
                <th className="screener-table-head-cell">质量</th>
                <th className="screener-table-head-cell">策略信号</th>
                <th className="screener-table-head-cell">价格</th>
                <th className="screener-table-head-cell">市值</th>
                <th className="screener-table-head-cell">换手率</th>
                <th className="screener-table-head-cell">PE</th>
                <th className="screener-table-head-cell">状态</th>
              </tr>
            </thead>
            <tbody>
              {sortedPicks.map((item, idx) => {
                const itemAny = item as unknown as Record<string, unknown>;
                const ss = itemAny.strategyScores as StrategyScores | undefined;
                const triggered = ss?.triggeredStrategies ?? [];
                const qualityTier = itemAny.qualityTier as string | undefined;
                const qualityTierLabel = itemAny.qualityTierLabel as string | undefined;
                const dataFetchFailed = itemAny.dataFetchFailed === true;
                const hasStrategyData = ss != null;
                const displayRank = idx + 1;
                const rankColor = displayRank <= 3 ? 'bg-cyan/20 text-cyan border border-cyan/30' : 'bg-white/5 text-secondary-text border border-white/10';
                return (
                  <tr key={item.id} className={`screener-table-row${dataFetchFailed && hasStrategyData ? ' opacity-70' : ''}`}>
                    <td className="screener-table-cell">
                      <span className={`inline-flex h-7 w-7 items-center justify-center rounded-lg text-xs font-bold ${rankColor}`}>
                        {displayRank}
                      </span>
                    </td>
                    <td className="screener-table-cell">
                      <div>
                        <span className="font-medium text-foreground">{item.name || item.code}</span>
                        <span className="ml-2 text-xs text-secondary-text">{item.code}</span>
                        {dataFetchFailed && hasStrategyData && (
                          <Tooltip content={(itemAny.dataFetchReason as string) || '历史数据获取失败'}>
                            <AlertTriangle className="ml-1 inline h-3 w-3 text-warning" />
                          </Tooltip>
                        )}
                      </div>
                    </td>
                    <td className="screener-table-cell">{scoreBar(item.score)}</td>
                    <td className="screener-table-cell">
                      {qualityTierLabel ? (
                        <Badge variant={qualityTier === 'premium' ? 'success' : qualityTier === 'standard' ? 'info' : 'warning'}>
                          {qualityTierLabel}
                        </Badge>
                      ) : (
                        <span className="text-xs text-muted-text">--</span>
                      )}
                    </td>
                    <td className="screener-table-cell">
                      <div className="flex flex-wrap gap-1">
                        {triggered.length > 0 ? triggered.slice(0, 3).map((s) => (
                          <Tooltip key={s.name} content={`${s.displayName}: ${s.score}分 (权重${s.weight})`}>
                            <Badge variant={s.score >= 60 ? 'success' : s.score >= 40 ? 'info' : 'default'}>
                              {s.displayName}
                            </Badge>
                          </Tooltip>
                        )) : (
                          <span className="text-xs text-muted-text">{dataFetchFailed && hasStrategyData ? '数据缺失' : '--'}</span>
                        )}
                        {triggered.length > 3 && (
                          <Tooltip content={triggered.slice(3).map((s) => s.displayName).join(', ')}>
                            <Badge variant="default">+{triggered.length - 3}</Badge>
                          </Tooltip>
                        )}
                      </div>
                    </td>
                    <td className="screener-table-cell font-mono tabular-nums">
                      {item.priceAtScreen != null ? `¥${item.priceAtScreen.toFixed(2)}` : '--'}
                    </td>
                    <td className="screener-table-cell font-mono tabular-nums text-secondary-text">
                      {item.marketCap != null ? capYi(item.marketCap / 1e8) : '--'}
                    </td>
                    <td className="screener-table-cell font-mono tabular-nums">
                      {item.turnoverRate != null ? `${item.turnoverRate.toFixed(2)}%` : '--'}
                    </td>
                    <td className="screener-table-cell font-mono tabular-nums">
                      {item.peRatio != null ? item.peRatio.toFixed(1) : '--'}
                    </td>
                    <td className="screener-table-cell">{statusBadge(item.status)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const renderWatchTab = () => {
    if (isLoadingWatch) {
      return (
        <div className="flex flex-col items-center justify-center h-64">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
          <p className="mt-3 text-secondary-text text-sm">加载观察池...</p>
        </div>
      );
    }

    if (watchList.length === 0) {
      return (
        <EmptyState
          title="观察池为空"
          description="运行选股后，选出的股票将自动进入观察池跟踪"
          className="border-dashed"
          icon={<Eye className="h-6 w-6" />}
        />
      );
    }

    const watching = watchList.filter((w) => w.status === 'watch');
    const closed = watchList.filter((w) => w.status === 'closed');

    return (
      <div className="animate-fade-in space-y-4">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="label-uppercase">观察池</span>
          <span className="text-xs text-secondary-text">
            观察中 {watching.length} 只 · 已关闭 {closed.length} 只
          </span>
          <div className="flex-1" />
          <button
            type="button"
            onClick={handleUpdateTracking}
            disabled={isUpdatingTracking}
            className="btn-secondary flex items-center gap-1.5 text-xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isUpdatingTracking ? 'animate-spin' : ''}`} />
            更新追踪
          </button>
          <button
            type="button"
            onClick={handleBacktestFeedback}
            disabled={isFeedbacking}
            className="btn-secondary flex items-center gap-1.5 text-xs"
          >
            <Target className={`h-3.5 w-3.5 ${isFeedbacking ? 'animate-spin' : ''}`} />
            回测反馈
          </button>
        </div>

        {watching.length > 0 && (
          <div>
            <h3 className="mb-2 text-sm font-medium text-foreground flex items-center gap-2">
              <Eye className="h-4 w-4 text-cyan" />
              观察中
            </h3>
            <div className="screener-table-wrapper overflow-x-auto rounded-xl border border-border/40">
              <table className="w-full min-w-[900px] text-sm">
                <thead className="screener-table-head">
                  <tr className="text-left">
                    <th className="screener-table-head-cell">排名</th>
                    <th className="screener-table-head-cell">股票</th>
                    <th className="screener-table-head-cell">入选日</th>
                    <th className="screener-table-head-cell">入选价</th>
                    <th className="screener-table-head-cell">持有天数</th>
                    <th className="screener-table-head-cell">收益率</th>
                    <th className="screener-table-head-cell">最大收益</th>
                    <th className="screener-table-head-cell">最大回撤</th>
                    <th className="screener-table-head-cell">回测验证</th>
                  </tr>
                </thead>
                <tbody>
                  {watching.map((item, idx) => {
                    const watchRank = idx + 1;
                    const rankColor = watchRank <= 3 ? 'bg-cyan/20 text-cyan border border-cyan/30' : 'bg-white/5 text-secondary-text border border-white/10';
                    return (
                    <tr key={item.id} className="screener-table-row">
                      <td className="screener-table-cell">
                        <span className={`inline-flex h-7 w-7 items-center justify-center rounded-lg text-xs font-bold ${rankColor}`}>
                          {watchRank}
                        </span>
                      </td>
                      <td className="screener-table-cell">
                        <div>
                          <span className="font-medium text-foreground">{item.name || item.code}</span>
                          <span className="ml-2 text-xs text-secondary-text">{item.code}</span>
                        </div>
                      </td>
                      <td className="screener-table-cell font-mono tabular-nums text-secondary-text">
                        {item.screenDate}
                      </td>
                      <td className="screener-table-cell font-mono tabular-nums">
                        {item.priceAtScreen != null ? `¥${item.priceAtScreen.toFixed(2)}` : '--'}
                      </td>
                      <td className="screener-table-cell font-mono tabular-nums text-secondary-text">
                        {item.daysHeld}天
                      </td>
                      <td className="screener-table-cell">{returnCell(item.returnPct)}</td>
                      <td className="screener-table-cell">{returnCell(item.maxReturnPct)}</td>
                      <td className="screener-table-cell">
                        {item.maxDrawdownPct != null ? (
                          <span className="font-mono tabular-nums text-danger">
                            {pct(item.maxDrawdownPct)}
                          </span>
                        ) : (
                          <span className="text-secondary-text">--</span>
                        )}
                      </td>
                      <td className="screener-table-cell">
                        {item.backtestVerified ? (
                          <Tooltip content={item.backtestOutcome || '已验证'}>
                            <span>
                              {item.backtestOutcome === 'win' ? (
                                <CheckCircle2 className="h-4 w-4 text-success" />
                              ) : item.backtestOutcome === 'loss' ? (
                                <XCircle className="h-4 w-4 text-danger" />
                              ) : (
                                <AlertTriangle className="h-4 w-4 text-warning" />
                              )}
                            </span>
                          </Tooltip>
                        ) : (
                          <span className="text-xs text-muted-text">未验证</span>
                        )}
                      </td>
                    </tr>
                  )})}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {closed.length > 0 && (
          <div>
            <h3 className="mb-2 text-sm font-medium text-foreground flex items-center gap-2">
              <Clock className="h-4 w-4 text-secondary-text" />
              已关闭
            </h3>
            <div className="screener-table-wrapper overflow-x-auto rounded-xl border border-border/40">
              <table className="w-full min-w-[900px] text-sm">
                <thead className="screener-table-head">
                  <tr className="text-left">
                    <th className="screener-table-head-cell">股票</th>
                    <th className="screener-table-head-cell">入选日</th>
                    <th className="screener-table-head-cell">入选价</th>
                    <th className="screener-table-head-cell">退出价</th>
                    <th className="screener-table-head-cell">收益率</th>
                    <th className="screener-table-head-cell">退出原因</th>
                    <th className="screener-table-head-cell">回测验证</th>
                  </tr>
                </thead>
                <tbody>
                  {closed.map((item) => (
                    <tr key={item.id} className="screener-table-row opacity-70">
                      <td className="screener-table-cell">
                        <div>
                          <span className="font-medium text-foreground">{item.name || item.code}</span>
                          <span className="ml-2 text-xs text-secondary-text">{item.code}</span>
                        </div>
                      </td>
                      <td className="screener-table-cell font-mono tabular-nums text-secondary-text">
                        {item.screenDate}
                      </td>
                      <td className="screener-table-cell font-mono tabular-nums">
                        {item.priceAtScreen != null ? `¥${item.priceAtScreen.toFixed(2)}` : '--'}
                      </td>
                      <td className="screener-table-cell font-mono tabular-nums">
                        {item.exitPrice != null ? `¥${item.exitPrice.toFixed(2)}` : '--'}
                      </td>
                      <td className="screener-table-cell">{returnCell(item.returnPct)}</td>
                      <td className="screener-table-cell">{exitReasonBadge(item.exitReason)}</td>
                      <td className="screener-table-cell">
                        {item.backtestVerified ? (
                          <Tooltip content={item.backtestOutcome || '已验证'}>
                            <span>
                              {item.backtestOutcome === 'win' ? (
                                <CheckCircle2 className="h-4 w-4 text-success" />
                              ) : item.backtestOutcome === 'loss' ? (
                                <XCircle className="h-4 w-4 text-danger" />
                              ) : (
                                <AlertTriangle className="h-4 w-4 text-warning" />
                              )}
                            </span>
                          </Tooltip>
                        ) : (
                          <span className="text-xs text-muted-text">未验证</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderPerformanceTab = () => {
    if (isLoadingPerf) {
      return (
        <div className="flex flex-col items-center justify-center h-64">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
          <p className="mt-3 text-secondary-text text-sm">加载统计数据...</p>
        </div>
      );
    }

    if (!perf || perf.total === 0) {
      return (
        <EmptyState
          title="暂无统计数据"
          description="选股观察池中有股票关闭后，将生成表现统计"
          className="border-dashed"
          icon={<BarChart3 className="h-6 w-6" />}
        />
      );
    }

    const winRate = perf.winRate;
    const isProfitable = perf.avgReturn > 0;

    return (
      <div className="animate-fade-in space-y-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard
            label="总选股数"
            value={perf.total}
            icon={<Crosshair className="h-5 w-5" />}
            tone="primary"
          />
          <StatCard
            label="胜率"
            value={`${winRate.toFixed(1)}%`}
            icon={<Target className="h-5 w-5" />}
            tone={winRate >= 50 ? 'success' : 'danger'}
            hint={`${perf.winCount} 胜 / ${perf.lossCount} 负`}
          />
          <StatCard
            label="平均收益"
            value={pct(perf.avgReturn)}
            icon={isProfitable ? <TrendingUp className="h-5 w-5" /> : <TrendingDown className="h-5 w-5" />}
            tone={isProfitable ? 'success' : 'danger'}
          />
          <StatCard
            label="最大收益"
            value={pct(perf.maxReturn)}
            icon={<TrendingUp className="h-5 w-5" />}
            tone="success"
          />
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard
            label="最大亏损"
            value={pct(perf.minReturn)}
            icon={<TrendingDown className="h-5 w-5" />}
            tone="danger"
          />
          <StatCard
            label="盈利次数"
            value={perf.winCount}
            tone="success"
          />
          <StatCard
            label="亏损次数"
            value={perf.lossCount}
            tone="danger"
          />
          <StatCard
            label="盈亏比"
            value={
              perf.lossCount > 0
                ? (perf.winCount / perf.lossCount).toFixed(2)
                : perf.winCount > 0
                  ? '∞'
                  : '--'
            }
            tone={perf.winCount > perf.lossCount ? 'success' : 'warning'}
          />
        </div>

        <Card variant="gradient" padding="md">
          <div className="mb-3">
            <span className="label-uppercase">收益分布</span>
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="w-16 text-xs text-secondary-text">盈利</span>
              <div className="h-3 flex-1 rounded-full bg-elevated/75">
                <div
                  className="h-full rounded-full bg-success transition-all"
                  style={{
                    width: `${perf.total > 0 ? (perf.winCount / perf.total) * 100 : 0}%`,
                  }}
                />
              </div>
              <span className="w-12 text-right text-xs font-mono tabular-nums text-success">
                {perf.winCount}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="w-16 text-xs text-secondary-text">亏损</span>
              <div className="h-3 flex-1 rounded-full bg-elevated/75">
                <div
                  className="h-full rounded-full bg-danger transition-all"
                  style={{
                    width: `${perf.total > 0 ? (perf.lossCount / perf.total) * 100 : 0}%`,
                  }}
                />
              </div>
              <span className="w-12 text-right text-xs font-mono tabular-nums text-danger">
                {perf.lossCount}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="w-16 text-xs text-secondary-text">持平</span>
              <div className="h-3 flex-1 rounded-full bg-elevated/75">
                <div
                  className="h-full rounded-full bg-warning transition-all"
                  style={{
                    width: `${perf.total > 0 ? ((perf.total - perf.winCount - perf.lossCount) / perf.total) * 100 : 0}%`,
                  }}
                />
              </div>
              <span className="w-12 text-right text-xs font-mono tabular-nums text-warning">
                {perf.total - perf.winCount - perf.lossCount}
              </span>
            </div>
          </div>
        </Card>
      </div>
    );
  };

  return (
    <div className="min-h-full flex flex-col rounded-[1.5rem] bg-transparent">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-white/5 px-3 py-3 sm:px-4">
        <div className="flex max-w-5xl flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 whitespace-nowrap">
            <span className="text-xs text-muted-text">选股数量</span>
            <input
              type="number"
              min={1}
              max={50}
              value={topN}
              onChange={(e) => setTopN(parseInt(e.target.value, 10) || 10)}
              disabled={isRunning}
              className="input-surface input-focus-glow h-10 w-20 rounded-xl border bg-transparent px-3 py-2 text-center text-xs tabular-nums transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
            />
          </div>
          <div className="flex items-center gap-2 whitespace-nowrap">
            <span className="text-xs text-muted-text">扫描模式</span>
            <select
              value={scanMode}
              onChange={(e) => setScanMode(e.target.value)}
              disabled={isRunning}
              className="input-surface input-focus-glow h-10 rounded-xl border bg-transparent px-3 py-2 text-xs transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
            >
              <option value="premium">仅优质股</option>
              <option value="quality_only">优质+标准</option>
              <option value="standard">标准及以上</option>
              <option value="full">全市场</option>
            </select>
          </div>
          <button
            type="button"
            onClick={handleRun}
            disabled={isRunning}
            className="btn-primary flex items-center gap-1.5 whitespace-nowrap"
          >
            {isRunning ? (
              <>
                <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                选股中...
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" />
                开始选股
              </>
            )}
          </button>
          <div className="flex-1" />
          <div className="flex items-center gap-2">
            {!poolStatus && (
              <span className="flex items-center gap-1.5 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2 text-xs text-muted-text">
                <Database className="h-3 w-3" />
                加载中...
              </span>
            )}
            {poolStatus?.status === 'running' && (
              <button
                type="button"
                onClick={() => setShowPoolPanel(!showPoolPanel)}
                className="flex items-center gap-1.5 rounded-xl border border-cyan/30 bg-cyan/10 px-3 py-2 text-xs text-cyan transition-all hover:bg-cyan/20"
              >
                <svg className="h-3 w-3 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                初始化中 {poolStatus.progressPct.toFixed(0)}%
              </button>
            )}
            {poolStatus?.status === 'completed' && poolStatus.daysRemaining != null && poolStatus.daysRemaining > 0 && (
              <>
                <button
                  type="button"
                  onClick={() => setShowPoolPanel(!showPoolPanel)}
                  className={"flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs transition-all hover:bg-white/5 " + (poolStatus.daysRemaining <= 7 ? "border-warning/30 bg-warning/10 text-warning" : "border-white/10 bg-white/5 text-secondary-text")}
                >
                  <Timer className="h-3 w-3" />
                  剩余 {poolStatus.daysRemaining} 天
                </button>
                <button
                  type="button"
                  onClick={() => setShowPoolPanel(!showPoolPanel)}
                  className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-secondary-text transition-all hover:bg-white/10 hover:text-foreground"
                >
                  <Layers className="h-3 w-3" />
                  股票池详情
                </button>
              </>
            )}
            {poolStatus?.status === 'completed' && poolStatus.daysRemaining != null && poolStatus.daysRemaining <= 0 && (
              <button
                type="button"
                onClick={handleInitPool}
                disabled={isInitingPool}
                className="flex items-center gap-1.5 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning transition-all hover:bg-warning/20"
              >
                <Database className="h-3 w-3" />
                股票池已过期，点击重新初始化
              </button>
            )}
            {poolStatus?.status === 'completed' && poolStatus.daysRemaining == null && (
              <button
                type="button"
                onClick={() => setShowPoolPanel(!showPoolPanel)}
                className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-secondary-text transition-all hover:bg-white/10 hover:text-foreground"
              >
                <Layers className="h-3 w-3" />
                股票池详情
              </button>
            )}
            {!poolStatus?.hasPool && poolStatus?.status !== 'running' && poolStatus?.status !== 'completed' && (
              <button
                type="button"
                onClick={handleInitPool}
                disabled={isInitingPool}
                className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-secondary-text transition-all hover:bg-white/10 hover:text-foreground disabled:opacity-50"
              >
                <Database className="h-3 w-3" />
                {isInitingPool ? '启动中...' : '初始化股票池'}
              </button>
            )}
            {poolStatus?.hasPool && poolStatus?.status !== 'running' && poolStatus?.status !== 'completed' && (
              <button
                type="button"
                onClick={() => setShowPoolPanel(!showPoolPanel)}
                className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-secondary-text transition-all hover:bg-white/10 hover:text-foreground"
              >
                <Layers className="h-3 w-3" />
                股票池
              </button>
            )}
          </div>
        </div>
        {runError && (
          <ApiErrorAlert error={runError} className="mt-2 max-w-4xl" />
        )}
        <p className="mt-2 text-xs text-muted-text">
          从全市场A股中多因子筛选优质标的，自动跟踪观察池收益并支持回测验证
        </p>

        {showPoolPanel && poolStatus && (
          <div className="mt-3 rounded-xl border border-white/10 bg-elevated/50 p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-cyan" />
                <span className="text-sm font-medium text-foreground">股票池管理</span>
                {poolStatus.poolVersion && (
                  <span className="text-xs text-secondary-text font-mono">{poolStatus.poolVersion}</span>
                )}
              </div>
              <button
                type="button"
                onClick={() => setShowPoolPanel(false)}
                className="rounded-lg p-1 text-secondary-text hover:text-foreground hover:bg-white/5 transition-all"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {poolStatus.status === 'running' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-secondary-text">初始化进度</span>
                  <span className="font-mono text-cyan">{poolStatus.progressPct.toFixed(1)}%</span>
                </div>
                <div className="h-2 w-full rounded-full bg-white/5">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-cyan to-blue-500 transition-all duration-500"
                    style={{ width: Math.min(100, poolStatus.progressPct) + '%' }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-secondary-text">
                  <span>已扫描 {poolStatus.totalStocks} 只 | 过滤 {poolStatus.filteredStocks} | 打标 {poolStatus.taggedStocks} | 排除 {poolStatus.excludedStocks}</span>
                  <span>预计剩余 {formatEta(poolStatus.etaSeconds)}</span>
                </div>
                <div className="flex gap-2 pt-1">
                  <button
                    type="button"
                    onClick={handleCancelPool}
                    className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-1.5 text-xs text-danger hover:bg-danger/20 transition-all"
                  >
                    取消初始化
                  </button>
                </div>
              </div>
            )}

            {poolStatus.status === 'completed' && (
              <div className="space-y-3">
                <div className="grid grid-cols-4 gap-3">
                  <div className="rounded-lg bg-white/5 p-2.5 text-center">
                    <div className="text-lg font-mono text-foreground">{poolStatus.taggedStocks}</div>
                    <div className="text-xs text-secondary-text">活跃股票</div>
                  </div>
                  <div className="rounded-lg bg-white/5 p-2.5 text-center">
                    <div className="text-lg font-mono text-foreground">{poolStatus.excludedStocks}</div>
                    <div className="text-xs text-secondary-text">已排除</div>
                  </div>
                  <div className="rounded-lg bg-white/5 p-2.5 text-center">
                    <div className="text-lg font-mono text-foreground">{poolStatus.totalStocks}</div>
                    <div className="text-xs text-secondary-text">总扫描</div>
                  </div>
                  <div className="rounded-lg bg-white/5 p-2.5 text-center">
                    <div className={"text-lg font-mono " + (poolStatus.daysRemaining != null && poolStatus.daysRemaining <= 7 ? "text-warning" : "text-foreground")}>
                      {poolStatus.daysRemaining ?? '--'}
                    </div>
                    <div className="text-xs text-secondary-text">剩余天数</div>
                  </div>
                </div>
                {poolSummary && (
                  <div className="grid grid-cols-3 gap-3 pt-1">
                    <div>
                      <div className="text-xs text-secondary-text mb-1.5">板块分布</div>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(poolSummary.boards).map(([board, count]) => (
                          <span key={board} className="inline-flex items-center gap-1 rounded-md bg-cyan/10 px-2 py-0.5 text-xs text-cyan">
                            {board} <span className="text-secondary-text">{count}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-secondary-text mb-1.5">行业分布</div>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(poolSummary.industries).slice(0, 8).map(([ind, count]) => (
                          <span key={ind} className="inline-flex items-center gap-1 rounded-md bg-blue-500/10 px-2 py-0.5 text-xs text-blue-400">
                            {ind} <span className="text-secondary-text">{count}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-secondary-text mb-1.5">质量分布</div>
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(poolSummary.qualities).map(([q, count]) => {
                          const qLabel = q === 'premium' ? '优质' : q === 'standard' ? '标准' : '边缘';
                          const qClass = q === 'premium' ? 'bg-success/10 text-success' : q === 'standard' ? 'bg-cyan/10 text-cyan' : 'bg-warning/10 text-warning';
                          return (
                            <span key={q} className={"inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs " + qClass}>
                              {qLabel} <span className="text-secondary-text">{count}</span>
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}
                <div className="flex gap-2 pt-1">
                  <button
                    type="button"
                    onClick={handleInitPool}
                    disabled={isInitingPool}
                    className="rounded-lg border border-cyan/30 bg-cyan/10 px-3 py-1.5 text-xs text-cyan hover:bg-cyan/20 transition-all disabled:opacity-50"
                  >
                    重新初始化
                  </button>
                </div>
              </div>
            )}

            {poolStatus.status === 'failed' && (
              <div className="space-y-2">
                <div className="text-xs text-danger">初始化失败：{poolStatus.errorMessage || '未知错误'}</div>
                <button
                  type="button"
                  onClick={handleInitPool}
                  disabled={isInitingPool}
                  className="rounded-lg border border-cyan/30 bg-cyan/10 px-3 py-1.5 text-xs text-cyan hover:bg-cyan/20 transition-all disabled:opacity-50"
                >
                  重新初始化
                </button>
              </div>
            )}

            {poolStatus.status === 'none' && (
              <div className="space-y-2">
                <div className="text-xs text-secondary-text">尚未初始化股票池。初始化将全量扫描A股并分类打标签，后续选股可基于标签快速筛选。</div>
                <button
                  type="button"
                  onClick={handleInitPool}
                  disabled={isInitingPool}
                  className="rounded-lg border border-cyan/30 bg-cyan/10 px-3 py-1.5 text-xs text-cyan hover:bg-cyan/20 transition-all disabled:opacity-50"
                >
                  {isInitingPool ? '启动中...' : '开始初始化'}
                </button>
              </div>
            )}
          </div>
        )}
      </header>

      {/* Tab navigation */}
      <div className="flex-shrink-0 border-b border-white/5 px-3">
        <div className="flex gap-1">
          {TAB_ITEMS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              type="button"
              onClick={() => setActiveTab(key)}
              className={`flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm transition-all ${
                activeTab === key
                  ? 'border-cyan text-cyan font-medium'
                  : 'border-transparent text-secondary-text hover:text-foreground'
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto p-3">
        {pageError ? <ApiErrorAlert error={pageError} className="mb-3" /> : null}
        {activeTab === 'today' && renderTodayTab()}
        {activeTab === 'watch' && renderWatchTab()}
        {activeTab === 'performance' && renderPerformanceTab()}
      </main>
    </div>
  );
};

export default ScreenerPage;
