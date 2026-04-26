export interface ScreenerRunRequest {
  topN?: number;
  strategyTag?: string;
  minMarketCap?: number;
  maxMarketCap?: number;
  minPrice?: number;
  maxPrice?: number;
  minTurnoverRate?: number;
  maxTurnoverRate?: number;
  demo?: boolean;
  scanMode?: string;
  useOptimizedWeights?: boolean;
  poolBoards?: string[];
  poolIndustries?: string[];
  poolQualities?: string[];
  poolTags?: string[];
  poolMinBaseScore?: number;
}

export interface StrategySignalDetail {
  name: string;
  displayName: string;
  score: number;
  weight: number;
  category: string;
  details?: Record<string, unknown>;
}

export interface CategoryBreakdown {
  avgScore: number;
  weight: number;
  topStrategies: { name: string; score: number; weight: number }[];
}

export interface StrategyScores {
  fusionScore: number;
  strategyAvg: number;
  baseFactorScore: number;
  regime: string;
  regimeLabel: string;
  categoryBreakdown?: Record<string, CategoryBreakdown>;
  triggeredStrategies?: StrategySignalDetail[];
  note?: string;
}

export interface DataFetchFailure {
  code: string;
  name: string;
  reason: string;
  fallback: string;
}

export interface ScreenerCandidateItem {
  rank: number;
  code: string;
  name: string;
  score: number;
  price: number;
  marketCapYi: number;
  turnoverRate: number;
  peRatio: number;
  signals?: Record<string, unknown>;
  strategyScores?: StrategyScores;
  marketRegime?: string;
  marketRegimeLabel?: string;
  qualityTier?: string;
  qualityTierLabel?: string;
  dataFetchFailed?: boolean;
  dataFetchReason?: string;
}

export interface ScreenerRunResponse {
  screened: number;
  saved: number;
  screenDate: string;
  candidates: ScreenerCandidateItem[];
  dataFailures?: DataFetchFailure[];
  qualitySummary?: Record<string, number>;
  marketRegime?: string;
  marketRegimeLabel?: string;
  optimizedWeightsApplied?: boolean;
}

export interface ScreenerPickItem {
  id: number;
  screenDate: string;
  code: string;
  name?: string;
  score: number;
  rank: number;
  strategyTag?: string;
  priceAtScreen?: number;
  marketCap?: number;
  turnoverRate?: number;
  peRatio?: number;
  pbRatio?: number;
  signals?: Record<string, unknown>;
  strategyScores?: StrategyScores;
  marketRegime?: string;
  marketRegimeLabel?: string;
  qualityTier?: string;
  qualityTierLabel?: string;
  dataFetchFailed?: boolean;
  dataFetchReason?: string;
  status: string;
  daysHeld: number;
  returnPct?: number;
  maxReturnPct?: number;
  maxDrawdownPct?: number;
  exitPrice?: number;
  exitDate?: string;
  exitReason?: string;
  backtestVerified: boolean;
  backtestOutcome?: string;
}

export interface ScreenerPicksResponse {
  date: string;
  total: number;
  picks: ScreenerPickItem[];
}

export interface ScreenerWatchListResponse {
  total: number;
  watchList: ScreenerPickItem[];
}

export interface ScreenerPerformanceResponse {
  total: number;
  winCount: number;
  lossCount: number;
  winRate: number;
  avgReturn: number;
  maxReturn: number;
  minReturn: number;
}

export interface ScreenerTrackingUpdateResponse {
  updated: number;
  closed: number;
}

export interface ScreenerBacktestFeedbackResponse {
  verified: number;
  totalChecked: number;
}

export interface PoolStatusResponse {
  hasPool: boolean;
  status: string;
  poolVersion?: string;
  expiresAt?: string;
  daysRemaining?: number;
  totalStocks: number;
  filteredStocks: number;
  taggedStocks: number;
  excludedStocks: number;
  progressPct: number;
  etaSeconds: number;
  errorMessage?: string;
}

export interface PoolSummaryResponse {
  boards: Record<string, number>;
  industries: Record<string, number>;
  qualities: Record<string, number>;
  totalActive: number;
}

export interface PoolEntryItem {
  code: string;
  name: string;
  board: string;
  industry: string;
  qualityTier: string;
  baseScore: number;
  tags: string[];
  marketCap: number;
  peRatio: number;
  pbRatio: number;
  price: number;
  turnoverRate: number;
}

export interface PoolCodesResponse {
  total: number;
  entries: PoolEntryItem[];
}

export interface PoolInitResponse {
  poolVersion: string;
  message: string;
}

export interface PoolCancelResponse {
  cancelled: boolean;
  message: string;
}
