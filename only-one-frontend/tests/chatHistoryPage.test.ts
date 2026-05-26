import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ChatHistoryPage from '@/pages/chat/ChatHistoryPage.vue';

const serviceMocks = vi.hoisted(() => ({
  listChatHistory: vi.fn(),
  getChatHistoryDetail: vi.fn(),
  getChatHistoryRaw: vi.fn(),
}));

vi.mock('@/services/chatHistory', () => serviceMocks);

function summary() {
  return {
    history_id: '200',
    id: '200',
    row_id: 1,
    request_id: 'req-200',
    model_name: 'deepseek-v4-flash',
    provider_name: 'DeepSeek',
    model_id: 'deepseek-v4',
    prompt_preview: 'worker 服务好像有问题',
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
  };
}

function rawExchange() {
  return {
    history_id: '200',
    request_id: 'req-200',
    request_stage: 'provider_outbound',
    response_stage: 'provider_response',
    request_json: {
      model: 'provider-model',
      messages: [{ role: 'user', content: 'worker 服务好像有问题' }],
    },
    response_json: {
      choices: [{ message: { role: 'assistant', content: 'ok' } }],
    },
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
      payload_bytes: 200,
      truncated: false,
      truncated_fields: [],
      notes: [],
    },
    snapshots: [],
    persisted_records: [
      {
        id: 'raw-1',
        kind: 'message',
        label: 'message: user/user_text',
        source_table: 'llm_chat_message',
        source_id: '1',
        seq: 0,
        created_at: '2026-05-22 10:00:00',
        raw_json: {
          role: 'user',
          content: 'hello',
          authorization: 'Bearer sk-secret',
        },
      },
    ],
  };
}

function detail() {
  return {
    summary: {
      ...summary(),
      prompt_full: 'worker 服务好像有问题',
    },
    messages: [
      {
        id: '1',
        history_id: '200',
        seq: 0,
        role: 'user',
        message_type: 'user_text',
        content: 'worker 服务好像有问题',
        received_at: '2026-05-22 10:00:00',
        token_count: null,
        token_source: 'legacy_unknown',
      },
      {
        id: '2',
        history_id: '200',
        seq: 1,
        role: 'assistant',
        message_type: 'assistant_tool_call',
        content: '',
        received_at: '2026-05-22 10:00:01',
        token_count: 22,
        token_source: 'provider',
        tool_calls: [
          {
            id: 'call_1',
            type: 'function',
            function: {
              name: 'check_service_health',
              arguments: '{"service":"worker"}',
            },
          },
        ],
      },
      {
        id: '3',
        history_id: '200',
        seq: 2,
        role: 'assistant',
        message_type: 'assistant_text',
        content: 'worker 服务状态为 degraded，建议继续排查队列积压。',
        received_at: '2026-05-22 10:00:02',
        token_count: 22,
        token_source: 'provider',
      },
      {
        id: '4',
        history_id: '200',
        seq: 3,
        role: 'tool',
        message_type: 'tool_result',
        content: '{"status":"degraded"}',
        received_at: '2026-05-22 10:00:03',
        token_count: null,
        token_source: 'legacy_unknown',
        tool_call_id: 'call_1',
        tool_name: 'check_service_health',
      },
    ],
    tool_definitions: [
      {
        id: '4',
        history_id: '200',
        seq: 3,
        tool_type: 'function',
        tool_name: 'check_service_health',
        description: '检查服务健康状态',
        parameters_json: { type: 'object' },
        raw_json: {
          type: 'function',
          function: { name: 'check_service_health' },
        },
        received_at: '2026-05-22 10:00:00',
        source: 'llm_chat_message',
      },
    ],
    tool_calls: [],
    events: [
      {
        id: 'event-1',
        history_id: '200',
        event_type: 'request_completed',
        provider_name: 'DeepSeek',
        payload_json: { usage_source: 'provider' },
        created_at: '2026-05-22 10:00:02',
      },
    ],
    raw_records: [
      {
        id: 'raw-1',
        kind: 'message',
        label: 'message: user/user_text',
        source_table: 'llm_chat_message',
        source_id: '1',
        seq: 0,
        created_at: '2026-05-22 10:00:00',
        raw_json: {
          role: 'user',
          content: 'hello',
          authorization: 'Bearer sk-secret',
        },
      },
    ],
    raw_available: {
      persisted_records: true,
      inbound_request: false,
      normalized_request: false,
      provider_outbound: false,
      provider_response: false,
      stream_chunks: false,
    },
  };
}

describe('ChatHistoryPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    serviceMocks.listChatHistory.mockResolvedValue({
      count: 1,
      rows: [summary()],
    });
    serviceMocks.getChatHistoryDetail.mockResolvedValue(detail());
    serviceMocks.getChatHistoryRaw.mockResolvedValue(rawExchange());
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it('loads detail lazily and renders semantic message roles', async () => {
    const wrapper = mount(ChatHistoryPage);
    await flushPromises();

    const detailButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('查看对话'));
    expect(detailButton).toBeTruthy();

    await detailButton?.trigger('click');
    await flushPromises();

    expect(serviceMocks.getChatHistoryDetail).toHaveBeenCalledWith('200');
    expect(wrapper.text()).toContain('AI 生成 · 请求调用工具');
    expect(wrapper.text()).toContain('AI 生成 · 模型回复');
    expect(wrapper.text()).toContain('工具返回结果');
    const messageText = wrapper.find('.message-list').text();
    expect(messageText).not.toContain('function');
    expect(messageText).not.toContain('AI 生成 · 工具返回结果');
  });

  it('renders raw availability and copies redacted raw JSON', async () => {
    const wrapper = mount(ChatHistoryPage);
    await flushPromises();

    const detailButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('查看对话'));
    await detailButton?.trigger('click');
    await flushPromises();

    const rawTab = wrapper
      .findAll('button')
      .find((button) => button.text().includes('原始数据'));
    await rawTab?.trigger('click');
    await flushPromises();

    expect(serviceMocks.getChatHistoryRaw).toHaveBeenCalledWith('200');
    expect(wrapper.text()).toContain('请求');
    expect(wrapper.text()).toContain('响应');
    expect(wrapper.text()).toContain('provider-model');
    expect(wrapper.text()).toContain('持久化记录');
    expect(wrapper.text()).not.toContain('Bearer sk-secret');
    expect(wrapper.text()).toContain('[REDACTED]');

    const copyButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('复制'));
    await copyButton?.trigger('click');

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.not.stringContaining('Bearer sk-secret'),
    );
  });

  it('shows unavailable raw exchange without reconstructing legacy data', async () => {
    serviceMocks.getChatHistoryRaw.mockResolvedValueOnce({
      ...rawExchange(),
      request_stage: 'unavailable',
      response_stage: 'unavailable',
      request_json: null,
      response_json: null,
      availability: {
        persisted_records: true,
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
        notes: ['raw exchange was not captured for this history'],
      },
    });
    const wrapper = mount(ChatHistoryPage);
    await flushPromises();

    const detailButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('查看对话'));
    await detailButton?.trigger('click');
    await flushPromises();

    const rawTab = wrapper
      .findAll('button')
      .find((button) => button.text().includes('原始数据'));
    await rawTab?.trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('Raw Exchange 未捕获');
    expect(wrapper.text()).toContain('raw exchange was not captured for this history');
    expect(wrapper.find('.raw-exchange-grid').text()).not.toContain('worker 服务好像有问题');
  });

  it('renders stream summary as a stream stage instead of provider response', async () => {
    serviceMocks.getChatHistoryRaw.mockResolvedValueOnce({
      ...rawExchange(),
      response_stage: 'stream_summary',
      response_json: {
        stream: true,
        chunk_count: 1,
        truncated: false,
        chunks: [{ seq: 1, has_usage: true, finish_reason: 'stop' }],
      },
      availability: {
        persisted_records: true,
        inbound_request: true,
        normalized_request: true,
        provider_outbound: true,
        provider_response: false,
        stream_chunks: true,
      },
    });
    const wrapper = mount(ChatHistoryPage);
    await flushPromises();

    const detailButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('查看对话'));
    await detailButton?.trigger('click');
    await flushPromises();

    const rawTab = wrapper
      .findAll('button')
      .find((button) => button.text().includes('原始数据'));
    await rawTab?.trigger('click');
    await flushPromises();

    const rawGridText = wrapper.find('.raw-exchange-grid').text();
    expect(rawGridText).toContain('Stream Summary');
    expect(rawGridText).toContain('"chunk_count": 1');
    expect(rawGridText).not.toContain('Provider Response');
  });
});
