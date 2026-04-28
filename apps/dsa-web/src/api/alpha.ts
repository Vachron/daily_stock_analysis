import apiClient from './index';
import { toCamelCase } from './utils';

export interface AlphaRunRequest {
  startDate?: string;
  endDate?: string;
  strategyNames?: string[];
  benchmarkCode?: string;
  topN?: number;
  poolSize?: number;
}

export interface AlphaAutoRequest {
  startDate?: string;
  endDate?: string;
  strategyNames?: string[];
  benchmarkCode?: string;
  topN?: number;
  maxIterations?: number;
}

export interface AlphaMetrics {
  totalReturnPct: number;
  annualizedReturnPct: number;
  maxDrawdownPct: number;
  sharpeRatio: number;
  excessReturnPct: number;
  informationRatio: number;
  trackingErrorPct: number;
}

export interface AlphaHealthItem {
  strategy: string;
  factor: string;
  ic: number;
  icIr: number;
  status: 'healthy' | 'warning' | 'aged';
}

export interface AlphaHealthResponse {
  status: string;
  healthy: number;
  aged: number;
  totalFactors: number;
  factors: AlphaHealthItem[];
  rotations: Array<{ strategy: string; factor: string; action: string; message: string }>;
}

export const alphaApi = {
  run: async (params: AlphaRunRequest = {}): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post<{ status: string; message: string }>(
      '/api/v1/alpha/run',
      params,
    );
    return response.data;
  },

  auto: async (params: AlphaAutoRequest = {}): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post<{ status: string; message: string }>(
      '/api/v1/alpha/auto',
      params,
    );
    return response.data;
  },

  getHealth: async (): Promise<AlphaHealthResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/alpha/health');
    return toCamelCase<AlphaHealthResponse>(response.data);
  },

  getBestConfig: async (): Promise<{ status: string; path?: string; config?: Record<string, unknown> }> => {
    const response = await apiClient.get<{ status: string; path?: string; config?: Record<string, unknown> }>(
      '/api/v1/alpha/config/best',
    );
    return response.data;
  },
};
