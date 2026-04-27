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
  PoolStatusResponse,
  PoolSummaryResponse,
  PoolCodesResponse,
  PoolInitResponse,
  PoolCancelResponse,
  ScreenerInsightItem,
  WatchBatchCloseResponse,
  WatchBatchRemoveResponse,
  WatchCloseRequest,
  WatchCloseResponse,
  WatchRemoveRequest,
  WatchRemoveResponse,
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
    if (params.poolBoards) requestData.pool_boards = params.poolBoards;
    if (params.poolIndustries) requestData.pool_industries = params.poolIndustries;
    if (params.poolQualities) requestData.pool_qualities = params.poolQualities;
    if (params.poolTags) requestData.pool_tags = params.poolTags;
    if (params.poolMinBaseScore !== undefined) requestData.pool_min_base_score = params.poolMinBaseScore;

    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/screener/run',
      requestData,
      { timeout: 10000 },
    );
    return toCamelCase<ScreenerRunResponse>(response.data);
  },

  getRunStatus: async (): Promise<ScreenerRunResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/screener/run/status',
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

  closeWatch: async (request: WatchCloseRequest): Promise<WatchCloseResponse> => {
    const requestData: Record<string, unknown> = {
      code: request.code,
      exit_reason: request.exitReason || 'manual',
    };
    if (request.strategyTag) requestData.strategy_tag = request.strategyTag;
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/screener/watch/close',
      requestData,
    );
    return toCamelCase<WatchCloseResponse>(response.data);
  },

  removeWatch: async (request: WatchRemoveRequest): Promise<WatchRemoveResponse> => {
    const requestData: Record<string, unknown> = { code: request.code };
    if (request.strategyTag) requestData.strategy_tag = request.strategyTag;
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/screener/watch/remove',
      requestData,
    );
    return toCamelCase<WatchRemoveResponse>(response.data);
  },

  batchCloseWatch: async (codes: string[]): Promise<WatchBatchCloseResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/screener/watch/batch-close',
      { codes, exit_reason: 'manual' },
    );
    return toCamelCase<WatchBatchCloseResponse>(response.data);
  },

  batchRemoveWatch: async (codes: string[]): Promise<WatchBatchRemoveResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/screener/watch/batch-remove',
      { codes },
    );
    return toCamelCase<WatchBatchRemoveResponse>(response.data);
  },

  updateTracking: async (): Promise<ScreenerTrackingUpdateResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/screener/tracking/update',
    );
    return toCamelCase<ScreenerTrackingUpdateResponse>(response.data);
  },

  getTrackingStatus: async (): Promise<{ status: string; result: Record<string, unknown> | null }> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/screener/tracking/status',
    );
    return toCamelCase<{ status: string; result: Record<string, unknown> | null }>(response.data);
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

  initPool: async (expireDays?: number): Promise<PoolInitResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/screener/pool/init',
      { expire_days: expireDays || 45 },
    );
    return toCamelCase<PoolInitResponse>(response.data);
  },

  getPoolStatus: async (): Promise<PoolStatusResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/screener/pool/status',
    );
    return toCamelCase<PoolStatusResponse>(response.data);
  },

  getPoolSummary: async (): Promise<PoolSummaryResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/screener/pool/summary',
    );
    return toCamelCase<PoolSummaryResponse>(response.data);
  },

  getPoolCodes: async (params?: {
    boards?: string;
    industries?: string;
    qualities?: string;
    tags?: string;
    minBaseScore?: number;
    limit?: number;
  }): Promise<PoolCodesResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/screener/pool/codes',
      { params },
    );
    return toCamelCase<PoolCodesResponse>(response.data);
  },

  cancelPoolInit: async (): Promise<PoolCancelResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/screener/pool/cancel',
    );
    return toCamelCase<PoolCancelResponse>(response.data);
  },

  getInsights: async (screenDate?: string): Promise<{ insights: ScreenerInsightItem[]; total: number }> => {
    const params: Record<string, string> = {};
    if (screenDate) params.screen_date = screenDate;
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/screener/insight',
      { params },
    );
    return toCamelCase<{ insights: ScreenerInsightItem[]; total: number }>(response.data);
  },

  getInsightByCode: async (code: string, screenDate?: string): Promise<{ insight: ScreenerInsightItem | null }> => {
    const params: Record<string, string> = {};
    if (screenDate) params.screen_date = screenDate;
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/screener/insight/${code}`,
      { params },
    );
    return toCamelCase<{ insight: ScreenerInsightItem | null }>(response.data);
  },

  generateInsights: async (): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post<Record<string, unknown>>(
      '/api/v1/screener/insight/generate',
    );
    return toCamelCase<{ status: string; message: string }>(response.data);
  },
};
