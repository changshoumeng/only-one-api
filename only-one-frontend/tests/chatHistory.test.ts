import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getChatHistoryDetail, getChatHistoryRaw, listChatHistory } from '@/services/chatHistory';
import { httpClient } from '@/services/http';

describe('chat history service', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('loads lightweight history summaries', async () => {
    const request = vi.spyOn(httpClient, 'request').mockResolvedValueOnce({
      data: {
        status: 0,
        msg: '',
        data: {
          count: 1,
          rows: [
            {
              history_id: '200',
              id: '200',
              row_id: 1,
              request_id: 'req-200',
              model_name: 'deepseek-v4-flash',
              provider_name: 'DeepSeek',
              model_id: 'deepseek-v4',
              prompt_preview: 'hello',
              finish_status: 'completed',
              usage_source: 'provider',
              prompt_tokens: 11,
              completion_tokens: 22,
              input_price: 0.01,
              output_price: 0.02,
              total_price: 0.03,
              input_price_display: '0.01',
              output_price_display: '0.02',
              total_price_display: '0.03 元',
              duration_seconds: 2,
              duration: '2 s',
              create_time: '2026-05-22 10:00:00',
              update_time: '2026-05-22 10:00:02',
            },
          ],
        },
      },
    } as never);

    const result = await listChatHistory({ page: 2, perPage: 5 });

    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/backend/chat/chat-history',
      params: { page: 2, perPage: 5 },
    });
    expect(result.rows[0].history_id).toBe('200');
    expect(result.rows[0].row_id).toBe(1);
  });

  it('loads detail by real history id', async () => {
    const request = vi.spyOn(httpClient, 'request').mockResolvedValueOnce({
      data: {
        status: 0,
        msg: '',
        data: {
          summary: {
            history_id: '200',
            id: '200',
            row_id: null,
            request_id: 'req-200',
            model_name: 'deepseek-v4-flash',
            provider_name: 'DeepSeek',
            model_id: 'deepseek-v4',
            prompt_preview: 'hello',
            prompt_full: 'hello',
            finish_status: 'completed',
            usage_source: 'provider',
            prompt_tokens: 11,
            completion_tokens: 22,
            input_price: 0.01,
            output_price: 0.02,
            total_price: 0.03,
            input_price_display: '0.01',
            output_price_display: '0.02',
            total_price_display: '0.03 元',
            duration_seconds: 2,
            duration: '2 s',
            create_time: '2026-05-22 10:00:00',
            update_time: '2026-05-22 10:00:02',
          },
          messages: [],
          tool_definitions: [],
          tool_calls: [],
          events: [],
          raw_records: [],
          raw_available: {
            persisted_records: true,
            inbound_request: false,
            normalized_request: false,
            provider_outbound: false,
            provider_response: false,
            stream_chunks: false,
          },
        },
      },
    } as never);

    const result = await getChatHistoryDetail('200');

    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/backend/chat/chat-history/200',
    });
    expect(result.summary.history_id).toBe('200');
    expect(result.raw_available.provider_response).toBe(false);
  });

  it('loads raw exchange lazily by history id', async () => {
    const request = vi.spyOn(httpClient, 'request').mockResolvedValueOnce({
      data: {
        status: 0,
        msg: '',
        data: {
          history_id: '200',
          request_id: 'req-200',
          request_stage: 'provider_outbound',
          response_stage: 'provider_response',
          request_json: { model: 'provider-model' },
          response_json: { choices: [{ message: { content: 'ok' } }] },
          availability: {
            persisted_records: true,
            inbound_request: true,
            normalized_request: true,
            provider_outbound: true,
            provider_response: true,
            stream_chunks: false,
          },
          redaction: {
            redaction_version: 'v1',
            payload_bytes: 100,
            truncated: false,
            truncated_fields: [],
            notes: [],
          },
          snapshots: [],
          persisted_records: [],
        },
      },
    } as never);

    const result = await getChatHistoryRaw('200');

    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/backend/chat/chat-history/200/raw',
    });
    expect(result.request_stage).toBe('provider_outbound');
    expect(result.response_json).toEqual({ choices: [{ message: { content: 'ok' } }] });
  });
});
