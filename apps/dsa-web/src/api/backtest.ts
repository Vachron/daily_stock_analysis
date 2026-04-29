import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  BacktestRunRequest,
  BacktestRunResponse,
  BacktestResultsResponse,
  BacktestResultItem,
  EquityCurveResponse,
  PerformanceMetrics,
  StrategyBacktestRequest,
  StrategyBacktestResult,
  StrategyInfo,
  PresetInfo,
  OptimizeRequest,
  OptimizeResult,
} from '../types/backtest';

export const backtestApi = {
  run: async (params: BacktestRunRequest = {}): Promise<BacktestRunResponse> => {
    const requestData: Record<string, unknown> = {};
    if (params.code) requestData.code = params.code;
    if (params.codes && params.codes.length > 0) requestData.codes = params.codes;
    if (params.force) requestData.force = params.force;
    if (params.evalWindowDays) requestData.eval_window_days = params.evalWindowDays;
    if (params.minAgeDays != null) requestData.min_age_days = params.minAgeDays;
    if (params.limit) requestData.limit = params.limit;
    if (params.autoAnalyze) requestData.auto_analyze = params.autoAnalyze;

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/backtest/run',
      requestData,
      { timeout: params.autoAnalyze ? 600000 : 120000 },
    );
    return toCamelCase<BacktestRunResponse>(response.data);
  },

  getResults: async (params: {
    code?: string;
    evalWindowDays?: number;
    analysisDateFrom?: string;
    analysisDateTo?: string;
    page?: number;
    limit?: number;
  } = {}): Promise<BacktestResultsResponse> => {
    const { code, evalWindowDays, analysisDateFrom, analysisDateTo, page = 1, limit = 20 } = params;

    const queryParams: Record<string, string | number> = { page, limit };
    if (code) queryParams.code = code;
    if (evalWindowDays) queryParams.eval_window_days = evalWindowDays;
    if (analysisDateFrom) queryParams.analysis_date_from = analysisDateFrom;
    if (analysisDateTo) queryParams.analysis_date_to = analysisDateTo;

    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/backtest/results',
      { params: queryParams },
    );

    const data = toCamelCase<BacktestResultsResponse>(response.data);
    return {
      total: data.total,
      page: data.page,
      limit: data.limit,
      items: (data.items || []).map(item => toCamelCase<BacktestResultItem>(item)),
    };
  },

  getOverallPerformance: async (params: {
    evalWindowDays?: number;
    analysisDateFrom?: string;
    analysisDateTo?: string;
  } = {}): Promise<PerformanceMetrics | null> => {
    try {
      const queryParams: Record<string, string | number> = {};
      if (params.evalWindowDays) queryParams.eval_window_days = params.evalWindowDays;
      if (params.analysisDateFrom) queryParams.analysis_date_from = params.analysisDateFrom;
      if (params.analysisDateTo) queryParams.analysis_date_to = params.analysisDateTo;
      const response = await apiClient.get<Record<string, unknown>>(
        '/api/v1/backtest/performance',
        { params: queryParams },
      );
      return toCamelCase<PerformanceMetrics>(response.data);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number } };
        if (axiosErr.response?.status === 404) return null;
      }
      throw err;
    }
  },

  getStockPerformance: async (code: string, params: {
    evalWindowDays?: number;
    analysisDateFrom?: string;
    analysisDateTo?: string;
  } = {}): Promise<PerformanceMetrics | null> => {
    try {
      const queryParams: Record<string, string | number> = {};
      if (params.evalWindowDays) queryParams.eval_window_days = params.evalWindowDays;
      if (params.analysisDateFrom) queryParams.analysis_date_from = params.analysisDateFrom;
      if (params.analysisDateTo) queryParams.analysis_date_to = params.analysisDateTo;
      const response = await apiClient.get<Record<string, unknown>>(
        `/api/v1/backtest/performance/${encodeURIComponent(code)}`,
        { params: queryParams },
      );
      return toCamelCase<PerformanceMetrics>(response.data);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number } };
        if (axiosErr.response?.status === 404) return null;
      }
      throw err;
    }
  },

  getEquityCurve: async (params: {
    code?: string;
    evalWindowDays?: number;
    analysisDateFrom?: string;
    analysisDateTo?: string;
  } = {}): Promise<EquityCurveResponse> => {
    const queryParams: Record<string, string | number> = {};
    if (params.code) queryParams.code = params.code;
    if (params.evalWindowDays) queryParams.eval_window_days = params.evalWindowDays;
    if (params.analysisDateFrom) queryParams.analysis_date_from = params.analysisDateFrom;
    if (params.analysisDateTo) queryParams.analysis_date_to = params.analysisDateTo;

    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/backtest/equity-curve',
      { params: queryParams },
    );
    return toCamelCase<EquityCurveResponse>(response.data);
  },

  // ===== v2 Strategy Backtest =====

  runStrategy: async (params: StrategyBacktestRequest): Promise<StrategyBacktestResult> => {
    const requestData: Record<string, unknown> = {
      strategy: params.strategy,
      codes: params.codes,
    };
    if (params.cash != null) requestData.cash = params.cash;
    if (params.commission != null) requestData.commission = params.commission;
    if (params.slippage != null) requestData.slippage = params.slippage;
    if (params.stampDuty != null) requestData.stamp_duty = params.stampDuty;
    if (params.startDate) requestData.start_date = params.startDate;
    if (params.endDate) requestData.end_date = params.endDate;
    if (params.factors) requestData.factors = params.factors;
    if (params.preset) requestData.preset = params.preset;
    if (params.exitRules) {
      requestData.exit_rules = {
        trailing_stop_pct: params.exitRules?.trailingStopPct,
        take_profit_pct: params.exitRules?.takeProfitPct,
        stop_loss_pct: params.exitRules?.stopLossPct,
        max_hold_days: params.exitRules?.maxHoldDays,
        partial_exit_enabled: params.exitRules?.partialExitEnabled,
        partial_exit_pct: params.exitRules?.partialExitPct,
      };
    }

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/backtest/strategy',
      requestData,
      { timeout: 120000 },
    );
    return toCamelCase<StrategyBacktestResult>(response.data);
  },

  getStrategies: async (): Promise<{ total: number; items: StrategyInfo[] }> => {
    const response = await apiClient.get<{ total: number; items: Record<string, unknown>[] }>(
      '/api/v1/backtest/strategies',
    );
    return {
      total: response.data.total,
      items: (response.data.items || []).map(item => toCamelCase<StrategyInfo>(item)),
    };
  },

  getPresets: async (): Promise<{ total: number; items: PresetInfo[] }> => {
    const response = await apiClient.get<{ total: number; items: Record<string, unknown>[] }>(
      '/api/v1/backtest/presets',
    );
    return {
      total: response.data.total,
      items: (response.data.items || []).map(item => toCamelCase<PresetInfo>(item)),
    };
  },

  getPresetForStock: async (stockCode: string): Promise<PresetInfo> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/backtest/presets/${encodeURIComponent(stockCode)}`,
    );
    return toCamelCase<PresetInfo>(response.data);
  },

  runOptimize: async (params: OptimizeRequest): Promise<OptimizeResult> => {
    const requestData: Record<string, unknown> = {
      strategy: params.strategy,
      codes: params.codes,
      factor_ranges: params.factorRanges,
    };
    if (params.startDate) requestData.start_date = params.startDate;
    if (params.endDate) requestData.end_date = params.endDate;
    if (params.maximize) requestData.maximize = params.maximize;
    if (params.method) requestData.method = params.method;
    if (params.maxTries) requestData.max_tries = params.maxTries;
    if (params.constraint) requestData.constraint = params.constraint;

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/backtest/optimize',
      requestData,
      { timeout: 600000 },
    );
    return toCamelCase<OptimizeResult>(response.data);
  },
};
