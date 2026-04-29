import { create } from 'zustand';
import type { StrategyInfo } from '../types/backtest';

interface BacktestState {
  strategies: StrategyInfo[];
  setStrategies: (items: StrategyInfo[]) => void;

  selectedCodes: string[];
  setSelectedCodes: (codes: string[]) => void;

  dateFrom: string;
  setDateFrom: (d: string) => void;
  dateTo: string;
  setDateTo: (d: string) => void;
}

export const useBacktestStore = create<BacktestState>((set) => ({
  strategies: [],
  setStrategies: (items) => set({ strategies: items }),

  selectedCodes: [],
  setSelectedCodes: (codes) => set({ selectedCodes: codes }),

  dateFrom: '',
  setDateFrom: (d) => set({ dateFrom: d }),
  dateTo: '',
  setDateTo: (d) => set({ dateTo: d }),
}));
