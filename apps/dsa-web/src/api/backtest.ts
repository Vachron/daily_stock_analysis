import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  BacktestRunRequest,
  BacktestRunResponse,
  BacktestResultsResponse,
  BacktestResultItem,
  EquityCurveResponse,
  PerformanceMetrics,
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

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/backtest/run',
      requestData,
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
};
