import type { AnalysisReport } from '../types/analysis';
import { historyApi } from '../api/history';
import { validateStockCode } from './validation';

export interface ChatFollowUpContext {
  stock_code: string;
  stock_name: string | null;
  previous_analysis_summary?: unknown;
  previous_strategy?: unknown;
  previous_price?: number;
  previous_change_pct?: number;
  signals?: Record<string, unknown>;
}

type ResolveChatFollowUpContextParams = {
  stockCode: string;
  stockName: string | null;
  recordId?: number;
};

const MAX_FOLLOW_UP_NAME_LENGTH = 80;

function hasInvalidFollowUpNameCharacter(value: string): boolean {
  return Array.from(value).some((character) => {
    const code = character.charCodeAt(0);
    return code < 32 || code === 127;
  });
}

export function sanitizeFollowUpStockCode(stockCode: string | null): string | null {
  if (!stockCode) {
    return null;
  }

  const { valid, normalized } = validateStockCode(stockCode);
  return valid ? normalized : null;
}

export function sanitizeFollowUpStockName(stockName: string | null): string | null {
  const normalized = stockName?.trim().replace(/\s+/g, ' ') ?? '';
  if (!normalized) {
    return null;
  }

  if (
    normalized.length > MAX_FOLLOW_UP_NAME_LENGTH
    || hasInvalidFollowUpNameCharacter(normalized)
  ) {
    return null;
  }

  return normalized;
}

export function parseFollowUpRecordId(recordId: string | null): number | undefined {
  if (!recordId || !/^\d+$/.test(recordId)) {
    return undefined;
  }

  const parsed = Number(recordId);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    return undefined;
  }

  return parsed;
}

export function buildFollowUpPrompt(
  stockCode: string,
  stockName: string | null,
  signals?: Record<string, unknown> | null,
): string {
  const displayName = stockName ? `${stockName}(${stockCode})` : stockCode;
  let prompt = `请深入分析 ${displayName}`;

  if (signals) {
    const strategies = signals.strategies as Array<{ n: string; s: number; w: number }> | undefined;
    const fusionScore = signals.fusionScore as number | undefined;
    if (strategies && strategies.length > 0) {
      const topStrategies = strategies
        .sort((a, b) => b.s - a.s)
        .map(s => `${s.n}(得分${s.s},权重${s.w?.toFixed(2)})`)
        .join('、');
      prompt += `\n该股票在选股系统中综合评分为${fusionScore?.toFixed(1) ?? '未知'}分，触发策略: ${topStrategies}。请结合这些策略信号进行解读。`;
    }
  }

  return prompt;
}

export function buildChatFollowUpContext(
  stockCode: string,
  stockName: string | null,
  report?: AnalysisReport | null,
): ChatFollowUpContext {
  const context: ChatFollowUpContext = {
    stock_code: stockCode,
    stock_name: stockName,
  };

  if (!report) {
    return context;
  }

  if (report.summary) {
    context.previous_analysis_summary = report.summary;
  }

  if (report.strategy) {
    context.previous_strategy = report.strategy;
  }

  if (report.meta) {
    context.previous_price = report.meta.currentPrice;
    context.previous_change_pct = report.meta.changePct;
  }

  return context;
}

export async function resolveChatFollowUpContext({
  stockCode,
  stockName,
  recordId,
}: ResolveChatFollowUpContextParams): Promise<ChatFollowUpContext> {
  if (!recordId) {
    return buildChatFollowUpContext(stockCode, stockName);
  }

  try {
    const report = await historyApi.getDetail(recordId);
    return buildChatFollowUpContext(stockCode, stockName, report);
  } catch {
    return buildChatFollowUpContext(stockCode, stockName);
  }
}
