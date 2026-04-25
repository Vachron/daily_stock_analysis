import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  ScreenerRunRequest,
  ScreenerRunResponse,
  ScreenerPicksResponse,
  ScreenerWatchListResponse,
  ScreenerPerformanceResponse,
  ScreenerTrackingUpdateResponse,
  ScreenerBacktestFeedbackResponse,
} from '../types/screener';

export const screenerApi = {
  run: async (params: ScreenerRunRequest = {}): Promise<ScreenerRunResponse> => {
    const requestData: Record<string, unknown> = {};
    if (params.topN) requestData.top_n = params.topN;
    if (params.strategyTag) requestData.strategy_tag = params.strategyTag;
    if (params.minMarketCap) requestData.min_market_cap = params.minMarketCap;
    if (params.maxMarketCap) requestData.max_market_cap = params.maxMarketCap;
    if (params.minPrice) requestData.min_price = params.minPrice;
    if (params.maxPrice) requestData.max_price = params.maxPrice;
    if (params.minTurnoverRate) requestData.min_turnover_rate = params.minTurnoverRate;
    if (params.maxTurnoverRate) requestData.max_turnover_rate = params.maxTurnoverRate;
    if (params.scanMode) requestData.scan_mode = params.scanMode;
    if (params.useOptimizedWeights !== undefined) requestData.use_optimized_weights = params.useOptimizedWeights;

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/screener/run',
      requestData,
    );
    return toCamelCase<ScreenerRunResponse>(response.data);
  },

  getTodayPicks: async (strategyTag?: string): Promise<ScreenerPicksResponse> => {
    const params: Record<string, string> = {};
    if (strategyTag) params.strategy_tag = strategyTag;
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/screener/today',
      { params },
    );
    return toCamelCase<ScreenerPicksResponse>(response.data);
  },

  getPicksByDate: async (screenDate: string, strategyTag?: string): Promise<ScreenerPicksResponse> => {
    const params: Record<string, string> = {};
    if (strategyTag) params.strategy_tag = strategyTag;
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/screener/picks/${screenDate}`,
      { params },
    );
    return toCamelCase<ScreenerPicksResponse>(response.data);
  },

  getWatchList: async (days?: number): Promise<ScreenerWatchListResponse> => {
    const params: Record<string, number> = {};
    if (days) params.days = days;
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/screener/watch',
      { params },
    );
    return toCamelCase<ScreenerWatchListResponse>(response.data);
  },

  updateTracking: async (): Promise<ScreenerTrackingUpdateResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/screener/tracking/update',
    );
    return toCamelCase<ScreenerTrackingUpdateResponse>(response.data);
  },

  applyBacktestFeedback: async (): Promise<ScreenerBacktestFeedbackResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/screener/backtest-feedback',
    );
    return toCamelCase<ScreenerBacktestFeedbackResponse>(response.data);
  },

  getPerformance: async (): Promise<ScreenerPerformanceResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/screener/performance',
    );
    return toCamelCase<ScreenerPerformanceResponse>(response.data);
  },
};
