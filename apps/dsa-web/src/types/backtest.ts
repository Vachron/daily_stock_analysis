/**
 * Backtest API type definitions
 * Mirrors api/v1/schemas/backtest.py
 */

// ============ Request / Response ============

export interface BacktestRunRequest {
  code?: string;
  codes?: string[];
  force?: boolean;
  evalWindowDays?: number;
  minAgeDays?: number;
  limit?: number;
  autoAnalyze?: boolean;
}

export interface BacktestRunResponse {
  processed: number;
  saved: number;
  completed: number;
  insufficient: number;
  errors: number;
  analyzed?: number;
}

// ============ Result Item ============

export interface BacktestResultItem {
  analysisHistoryId: number;
  code: string;
  stockName?: string;
  analysisDate?: string;
  evalWindowDays: number;
  engineVersion: string;
  evalStatus: string;
  evaluatedAt?: string;
  operationAdvice?: string;
  trendPrediction?: string;
  positionRecommendation?: string;
  startPrice?: number;
  endClose?: number;
  maxHigh?: number;
  minLow?: number;
  stockReturnPct?: number;
  actualReturnPct?: number;
  actualMovement?: string;
  directionExpected?: string;
  directionCorrect?: boolean;
  outcome?: string;
  stopLoss?: number;
  takeProfit?: number;
  hitStopLoss?: boolean;
  hitTakeProfit?: boolean;
  firstHit?: string;
  firstHitDate?: string;
  firstHitTradingDays?: number;
  simulatedEntryPrice?: number;
  simulatedExitPrice?: number;
  simulatedExitReason?: string;
  simulatedReturnPct?: number;
}

export interface BacktestResultsResponse {
  total: number;
  page: number;
  limit: number;
  items: BacktestResultItem[];
}

// ============ Performance Metrics ============

export interface PerformanceMetrics {
  scope: string;
  code?: string;
  evalWindowDays: number;
  engineVersion: string;
  computedAt?: string;

  totalEvaluations: number;
  completedCount: number;
  insufficientCount: number;
  longCount: number;
  cashCount: number;
  winCount: number;
  lossCount: number;
  neutralCount: number;

  directionAccuracyPct?: number;
  winRatePct?: number;
  neutralRatePct?: number;
  avgStockReturnPct?: number;
  avgSimulatedReturnPct?: number;

  stopLossTriggerRate?: number;
  takeProfitTriggerRate?: number;
  ambiguousRate?: number;
  avgDaysToFirstHit?: number;

  sharpeRatio?: number;
  maxDrawdownPct?: number;
  profitFactor?: number;
  avgWinPct?: number;
  avgLossPct?: number;

  adviceBreakdown: Record<string, unknown>;
  diagnostics: Record<string, unknown>;
}

// ============ Equity Curve ============

export interface EquityCurvePoint {
  date: string;
  cumulativeReturnPct: number;
  drawdownPct: number;
}

export interface EquityCurveResponse {
  code?: string;
  evalWindowDays: number;
  engineVersion: string;
  totalTrades: number;
  points: EquityCurvePoint[];
}

// ============ v2 Strategy Backtest ============

export interface ExitRuleConfig {
  trailingStopPct?: number;
  takeProfitPct?: number;
  stopLossPct?: number;
  maxHoldDays?: number;
  partialExitEnabled?: boolean;
  partialExitPct?: number;
  signalThreshold?: number;
  fixedDays?: number;
}

export interface StrategyBacktestRequest {
  strategy: string;
  codes: string[];
  cash?: number;
  commission?: number;
  slippage?: number;
  stampDuty?: number;
  startDate?: string;
  endDate?: string;
  factors?: Record<string, number>;
  preset?: string;
  exitRules?: ExitRuleConfig;
}

export interface StrategyBacktestStats {
  returnPct?: number;
  returnAnnPct?: number;
  cagrPct?: number;
  buyHoldReturnPct?: number;
  exposureTimePct?: number;
  equityFinal?: number;
  equityPeak?: number;
  volatilityAnnPct?: number;
  maxDrawdownPct?: number;
  avgDrawdownPct?: number;
  maxDrawdownDuration?: number;
  avgDrawdownDuration?: number;
  sharpeRatio?: number;
  sortinoRatio?: number;
  calmarRatio?: number;
  alphaPct?: number;
  beta?: number;
  tradeCount?: number;
  winRatePct?: number;
  bestTradePct?: number;
  worstTradePct?: number;
  avgTradePct?: number;
  profitFactor?: number;
  expectancyPct?: number;
  sqn?: number;
  kellyCriterion?: number;
  turnoverRate?: number;
  dayWinRate?: number;
  profitLossRatio?: number;
  totalCommission?: number;
  commissions?: number;
}

export interface StrategyBacktestTrade {
  size: number;
  entryBar: number;
  exitBar?: number;
  entryPrice: number;
  exitPrice?: number;
  sl?: number;
  tp?: number;
  pnl?: number;
  returnPct?: number;
  commission?: number;
  entryTime?: string;
  exitTime?: string;
  duration?: string;
  tag?: string;
  exitReason?: string;
  positionPct: number;
}

export interface StrategyBacktestResult {
  resultId: string;
  strategyName: string;
  symbol: string;
  startDate?: string;
  endDate?: string;
  initialCash: number;
  stats: StrategyBacktestStats;
  trades: StrategyBacktestTrade[];
  equityCurve: Array<{ date?: string; Date?: string; Equity: number; DrawdownPct: number; DrawdownDuration?: number }>;
  engineVersion: string;
  presetName?: string;
  elapsedSeconds: number;
}

export interface StrategyInfo {
  name: string;
  displayName: string;
  description: string;
  category: string;
  factors: StrategyFactor[];
  marketRegimes: string[];
}

export interface StrategyFactor {
  id: string;
  displayName: string;
  type: string;
  default: number;
  range: number[];
  step: number;
}

export interface PresetInfo {
  name: string;
  displayName: string;
  activityLevel: string;
  capSize: string;
  threshold: number;
  trailingStopPct?: number;
  takeProfitPct?: number;
  stopLossPct?: number;
  maxHoldDays?: number;
  positionSizing: string;
  feeRate: number;
}

export interface OptimizeRequest {
  strategy: string;
  codes: string[];
  startDate?: string;
  endDate?: string;
  maximize?: string;
  method?: string;
  factorRanges: Record<string, number[]>;
  constraint?: string;
  maxTries?: number;
}

export interface OptimizeResult {
  status: string;
  bestParams: Record<string, number>;
  bestValue: number;
  bestStats: StrategyBacktestStats;
  heatmap?: Record<string, unknown>;
  totalTrials: number;
  elapsedSeconds: number;
}

// ============ v2 Monte Carlo ============

export interface MontecarloRequest {
  strategy: string;
  codes: string[];
  startDate?: string;
  endDate?: string;
  nSimulations?: number;
  frac?: number;
}

export interface MontecarloResultItem {
  returnPct: number;
  sharpeRatio?: number;
  maxDrawdownPct?: number;
  tradeCount: number;
}

export interface MontecarloResult {
  status: string;
  nSimulations: number;
  originalStats: Record<string, number>;
  medianReturnPct: number;
  p5ReturnPct: number;
  p95ReturnPct: number;
  ruinProbability: number;
  results: MontecarloResultItem[];
  elapsedSeconds: number;
}
