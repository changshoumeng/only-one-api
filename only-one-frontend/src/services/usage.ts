import { requestData } from './http';
import type { EChartLinePayload, UsageSummary } from './types';

export interface UsageQuery {
  before_num: number | string;
  unit_type: 'day' | 'month' | 'year';
}

export function getUsageSummary() {
  return requestData<UsageSummary>(
    {
      method: 'GET',
      url: '/backend/llm-usage/total-usage',
    },
    {
      total_request: '0',
      total_tokens: '0',
      total_price: '0.00',
    },
  );
}

export function getRequestChart(params: UsageQuery) {
  return requestData<EChartLinePayload>(
    {
      method: 'GET',
      url: '/backend/llm-usage/chart-request',
      params,
    },
    {},
  );
}

export function getTokenChart(params: UsageQuery) {
  return requestData<EChartLinePayload>(
    {
      method: 'GET',
      url: '/backend/llm-usage/chart-token',
      params,
    },
    {},
  );
}

export function getMoneyChart(params: UsageQuery) {
  return requestData<EChartLinePayload>(
    {
      method: 'GET',
      url: '/backend/llm-usage/chart-money',
      params,
    },
    {},
  );
}
