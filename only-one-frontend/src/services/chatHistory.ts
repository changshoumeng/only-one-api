import { requestData } from './http';
import type {
  ChatHistoryDetail,
  ChatHistorySummary,
  ChatRawExchange,
  PageRows,
} from './types';

export interface ChatHistoryQuery {
  page: number;
  perPage: number;
}

export function listChatHistory(params: ChatHistoryQuery) {
  return requestData<PageRows<ChatHistorySummary>>(
    {
      method: 'GET',
      url: '/backend/chat/chat-history',
      params,
    },
    { count: 0, rows: [] },
  );
}

export function getChatHistoryDetail(historyId: string | number) {
  return requestData<ChatHistoryDetail>(
    {
      method: 'GET',
      url: `/backend/chat/chat-history/${historyId}`,
    },
    {
      summary: {
        history_id: String(historyId),
        id: String(historyId),
        row_id: null,
        request_id: null,
        model_name: null,
        provider_name: null,
        model_id: null,
        prompt_preview: '',
        finish_status: 'unknown',
        usage_source: 'unknown',
        prompt_tokens: 0,
        completion_tokens: 0,
        input_price: 0,
        output_price: 0,
        total_price: 0,
        input_price_display: '0',
        output_price_display: '0',
        total_price_display: '0 元',
        duration_seconds: null,
        duration: '未完成',
        create_time: '',
        update_time: '',
      },
      messages: [],
      tool_definitions: [],
      tool_calls: [],
      events: [],
      raw_records: [],
      raw_available: {
        persisted_records: false,
        inbound_request: false,
        normalized_request: false,
        provider_outbound: false,
        provider_response: false,
        stream_chunks: false,
      },
    },
  );
}

export function getChatHistoryRaw(historyId: string | number) {
  return requestData<ChatRawExchange>(
    {
      method: 'GET',
      url: `/backend/chat/chat-history/${historyId}/raw`,
    },
    {
      history_id: String(historyId),
      request_id: null,
      request_stage: 'unavailable',
      response_stage: 'unavailable',
      request_json: null,
      response_json: null,
      availability: {
        persisted_records: false,
        inbound_request: false,
        normalized_request: false,
        provider_outbound: false,
        provider_response: false,
        stream_chunks: false,
      },
      redaction: {
        redaction_version: 'v1',
        payload_bytes: 0,
        truncated: false,
        truncated_fields: [],
        notes: ['raw exchange unavailable'],
      },
      snapshots: [],
      persisted_records: [],
    },
  );
}
