<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import {
  Bot,
  Braces,
  Clock,
  Copy,
  Eye,
  FileCode,
  RefreshCw,
  UserRound,
  Wrench,
  X,
} from '@lucide/vue';
import {
  getChatHistoryDetail,
  getChatHistoryRaw,
  listChatHistory,
} from '@/services/chatHistory';
import JsonViewer from '@/components/base/JsonViewer.vue';
import type {
  ChatHistoryDetail,
  ChatHistorySummary,
  ChatRawExchange,
  ChatMessageView,
  RawRecordView,
} from '@/services/types';
import { copyText, formatError, formatInteger } from '@/utils/format';

type DetailTab = 'visual' | 'raw' | 'tools' | 'events';

const page = reactive({ page: 1, perPage: 10 });
const rows = ref<ChatHistorySummary[]>([]);
const total = ref(0);
const isLoading = ref(false);
const errorMessage = ref('');
const selectedSummary = ref<ChatHistorySummary | null>(null);
const selectedDetail = ref<ChatHistoryDetail | null>(null);
const selectedRaw = ref<ChatRawExchange | null>(null);
const detailLoading = ref(false);
const detailError = ref('');
const rawLoading = ref(false);
const rawError = ref('');
const rawLoadedHistoryId = ref('');
const activeTab = ref<DetailTab>('visual');
const copiedRecordId = ref('');

const tabs: Array<{ key: DetailTab; label: string }> = [
  { key: 'visual', label: '可视化' },
  { key: 'raw', label: '原始数据' },
  { key: 'tools', label: '工具' },
  { key: 'events', label: '事件' },
];

const pageCount = computed(() =>
  Math.max(1, Math.ceil(total.value / page.perPage)),
);

const detailSummary = computed(
  () => selectedDetail.value?.summary ?? selectedSummary.value,
);

async function loadHistory() {
  isLoading.value = true;
  errorMessage.value = '';

  try {
    const result = await listChatHistory(page);
    rows.value = result.rows;
    total.value = result.count;
  } catch (error) {
    errorMessage.value = formatError(error, '对话历史加载失败');
  } finally {
    isLoading.value = false;
  }
}

async function changePage(nextPage: number) {
  page.page = Math.min(Math.max(1, nextPage), pageCount.value);
  await loadHistory();
}

async function openHistory(item: ChatHistorySummary) {
  selectedSummary.value = item;
  selectedDetail.value = null;
  selectedRaw.value = null;
  detailError.value = '';
  rawError.value = '';
  rawLoadedHistoryId.value = '';
  activeTab.value = 'visual';
  copiedRecordId.value = '';
  detailLoading.value = true;

  try {
    selectedDetail.value = await getChatHistoryDetail(item.history_id);
  } catch (error) {
    detailError.value = formatError(error, '对话详情加载失败');
  } finally {
    detailLoading.value = false;
  }
}

function closeHistory() {
  selectedSummary.value = null;
  selectedDetail.value = null;
  selectedRaw.value = null;
  detailError.value = '';
  rawError.value = '';
  rawLoadedHistoryId.value = '';
  copiedRecordId.value = '';
}

async function loadRawExchange() {
  const historyId = selectedSummary.value?.history_id;
  if (!historyId || rawLoadedHistoryId.value === historyId || rawLoading.value) {
    return;
  }

  rawLoading.value = true;
  rawError.value = '';
  try {
    selectedRaw.value = await getChatHistoryRaw(historyId);
    rawLoadedHistoryId.value = historyId;
  } catch (error) {
    rawError.value = formatError(error, '原始请求响应加载失败');
  } finally {
    rawLoading.value = false;
  }
}

function tokenPair(item: ChatHistorySummary) {
  return `${formatInteger(item.prompt_tokens)} / ${formatInteger(
    item.completion_tokens,
  )}`;
}

function messageMeta(item: ChatMessageView) {
  const token =
    item.token_count == null ? '--' : formatInteger(item.token_count);
  const source = item.token_source || 'unknown';
  return `${item.received_at || '--'} · ${item.message_type || item.role} · token: ${token} (${source})`;
}

function messageRoleLabel(message: ChatMessageView) {
  if (message.message_type === 'assistant_tool_call') {
    return 'AI 生成 · 请求调用工具';
  }
  if (message.message_type === 'tool_result' || message.role === 'tool') {
    return '工具返回结果';
  }
  if (message.role === 'system') {
    return '系统指令';
  }
  if (message.role === 'user') {
    return '用户消息';
  }
  if (message.role === 'assistant') {
    return 'AI 生成 · 模型回复';
  }
  return message.role || '未知消息';
}

function messageTone(message: ChatMessageView) {
  if (message.role === 'user') {
    return 'message-item-user';
  }
  if (message.role === 'system') {
    return 'message-item-system';
  }
  if (message.message_type === 'tool_result' || message.role === 'tool') {
    return 'message-item-tool';
  }
  if (message.message_type === 'assistant_tool_call') {
    return 'message-item-tool-call';
  }
  return 'message-item-assistant';
}

function messageContent(message: ChatMessageView) {
  if (message.message_type === 'assistant_tool_call' && !message.content) {
    return '模型请求调用工具';
  }
  return message.content || '暂无内容';
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function parseJsonString(value: unknown) {
  if (typeof value !== 'string') {
    return value;
  }

  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function toolCallId(call: unknown) {
  return String(asRecord(call).id ?? '--');
}

function toolCallName(call: unknown) {
  const functionInfo = asRecord(asRecord(call).function);
  return String(functionInfo.name ?? '--');
}

function toolCallArguments(call: unknown) {
  const functionInfo = asRecord(asRecord(call).function);
  return formatJson(parseJsonString(functionInfo.arguments));
}

function rawFlagLabel(key: string) {
  const labels: Record<string, string> = {
    persisted_records: 'Persisted Records',
    inbound_request: 'Inbound Request',
    normalized_request: 'Normalized Request',
    provider_outbound: 'Provider Outbound',
    provider_response: 'Provider Response',
    stream_chunks: 'Stream Chunks',
  };
  return labels[key] ?? key;
}

function stageLabel(stage: string) {
  const labels: Record<string, string> = {
    provider_outbound: 'Provider Outbound',
    provider_response: 'Provider Response',
    provider_error: 'Provider Error',
    stream_summary: 'Stream Summary',
    normalized: 'Normalized',
    inbound: 'Inbound',
    unavailable: 'Unavailable',
  };
  return labels[stage] ?? stage;
}

function redactedJson(value: unknown, key = ''): unknown {
  const secretKey = /(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|secret|password)/i;

  if (secretKey.test(key)) {
    return '[REDACTED]';
  }

  if (typeof value === 'string') {
    if (/^bearer\s+/i.test(value)) {
      return '[REDACTED]';
    }
    if (value.length > 5000) {
      return `${value.slice(0, 5000)}\n...[TRUNCATED ${value.length - 5000} chars]`;
    }
    return value;
  }

  if (Array.isArray(value)) {
    return value.map((item) => redactedJson(item));
  }

  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([entryKey, entryValue]) => [
        entryKey,
        redactedJson(entryValue, entryKey),
      ]),
    );
  }

  return value;
}

function formatJson(value: unknown) {
  const safeValue = redactedJson(value);
  if (safeValue === undefined || safeValue === null || safeValue === '') {
    return '';
  }

  if (typeof safeValue === 'string') {
    return safeValue;
  }

  try {
    return JSON.stringify(safeValue, null, 2);
  } catch {
    return String(safeValue);
  }
}

async function copyRawRecord(record: RawRecordView) {
  await copyText(formatJson(record.raw_json));
  copiedRecordId.value = record.id;
}

async function copyJsonBlock(id: string, value: unknown) {
  await copyText(formatJson(value));
  copiedRecordId.value = id;
}

watch(activeTab, (tab) => {
  if (tab === 'raw') {
    void loadRawExchange();
  }
});

onMounted(loadHistory);
</script>

<template>
  <section class="page page-grid">
    <div class=" page-shell--data page-grid">
      <p v-if="errorMessage" class="inline-error" role="alert">
        {{ errorMessage }}
      </p>

      <section class="surface data-section">
        <header class="section-toolbar">
          <div>
            <h2 class="section-title">历史记录</h2>
            <p class="subtle">
              对话详情按消息、工具、事件和持久化 raw 数据拆分展示。
            </p>
          </div>
          <button
            class="button button-muted button-inline"
            type="button"
            :disabled="isLoading"
            @click="loadHistory"
          >
            <RefreshCw aria-hidden="true" />
            <span>刷新</span>
          </button>
        </header>

        <div class="table-wrap">
          <table class="data-table chat-history-table">
            <thead>
              <tr>
                <th>行号</th>
                <th>History ID</th>
                <th>Request ID</th>
                <th>模型/供应商</th>
                <th>Prompt</th>
                <th>Token</th>
                <th>总费用</th>
                <th>时间</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in rows" :key="item.history_id">
                <td>{{ item.row_id ?? '--' }}</td>
                <td><code>{{ item.history_id }}</code></td>
                <td class="text-clip">
                  <code>{{ item.request_id || '--' }}</code>
                </td>
                <td>
                  <div class="stack-sm">
                    <strong>{{ item.model_name || '--' }}</strong>
                    <span class="subtle">{{ item.provider_name || '--' }}</span>
                  </div>
                </td>
                <td class="prompt-cell">
                  {{ item.prompt_preview || item.prompt || '--' }}
                </td>
                <td>{{ tokenPair(item) }}</td>
                <td>{{ item.total_price_display }}</td>
                <td>{{ item.create_time }}</td>
                <td>
                  <span class="status-pill status-neutral">{{
                    item.finish_status || 'unknown'
                  }}</span>
                </td>
                <td>
                  <button
                    class="button button-muted button-inline"
                    type="button"
                    @click="openHistory(item)"
                  >
                    <Eye aria-hidden="true" />
                    <span>查看对话</span>
                  </button>
                </td>
              </tr>
              <tr v-if="!rows.length">
                <td class="empty-table" colspan="10">暂无对话历史</td>
              </tr>
            </tbody>
          </table>
        </div>

        <footer class="pagination-bar">
          <span>共 {{ total }} 条</span>
          <button
            class="button button-muted button-inline"
            type="button"
            :disabled="page.page <= 1"
            @click="changePage(page.page - 1)"
          >
            上一页
          </button>
          <span>{{ page.page }} / {{ pageCount }}</span>
          <button
            class="button button-muted button-inline"
            type="button"
            :disabled="page.page >= pageCount"
            @click="changePage(page.page + 1)"
          >
            下一页
          </button>
        </footer>
      </section>
    </div>

    <div v-if="selectedSummary" class="modal-backdrop" role="presentation">
      <section
        class="surface modal-panel modal-panel-wide chat-detail-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="history-dialog-title"
      >
        <header class="section-toolbar chat-detail-header">
          <div>
            <h2 id="history-dialog-title" class="section-title">对话记录</h2>
            <p class="subtle">
              {{ detailSummary?.model_name || '--' }} ·
              {{ detailSummary?.provider_name || '--' }} ·
              {{ detailSummary?.create_time || '--' }}
            </p>
          </div>
          <button
            class="icon-button"
            type="button"
            aria-label="关闭"
            @click="closeHistory"
          >
            <X aria-hidden="true" />
          </button>
        </header>

        <section v-if="detailSummary" class="detail-summary-grid">
          <div>
            <span class="summary-label">History ID</span>
            <code>{{ detailSummary.history_id }}</code>
          </div>
          <div>
            <span class="summary-label">Request ID</span>
            <code>{{ detailSummary.request_id || '--' }}</code>
          </div>
          <div>
            <span class="summary-label">状态</span>
            <span class="status-pill status-neutral">{{
              detailSummary.finish_status
            }}</span>
          </div>
          <div>
            <span class="summary-label">耗时</span>
            <strong>{{ detailSummary.duration }}</strong>
          </div>
          <div>
            <span class="summary-label">Token</span>
            <strong>{{ tokenPair(detailSummary) }}</strong>
          </div>
          <div>
            <span class="summary-label">费用</span>
            <strong>{{ detailSummary.total_price_display }}</strong>
          </div>
          <div>
            <span class="summary-label">Usage</span>
            <strong>{{ detailSummary.usage_source }}</strong>
          </div>
        </section>

        <div class="detail-tabs" role="tablist" aria-label="对话详情视图">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            class="detail-tab"
            :class="{ 'detail-tab-active': activeTab === tab.key }"
            type="button"
            role="tab"
            :aria-selected="activeTab === tab.key"
            @click="activeTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>

        <p v-if="detailError" class="inline-error" role="alert">
          {{ detailError }}
        </p>
        <p v-else-if="detailLoading" class="empty-copy">加载中...</p>

        <template v-else-if="selectedDetail">
          <div v-if="activeTab === 'visual'" class="message-list">
            <article
              v-for="message in selectedDetail.messages"
              :key="`${message.id || message.seq}-${message.role}-${message.received_at}`"
              class="message-item"
              :class="messageTone(message)"
            >
              <header class="message-header">
                <span
                  class="message-avatar"
                  :class="
                    message.role === 'user'
                      ? 'message-avatar-user'
                      : message.role === 'tool' ||
                          message.message_type === 'tool_result' ||
                          message.message_type === 'assistant_tool_call'
                        ? 'message-avatar-tool'
                        : message.role === 'system'
                          ? 'message-avatar-system'
                          : 'message-avatar-bot'
                  "
                >
                  <UserRound v-if="message.role === 'user'" aria-hidden="true" />
                  <Wrench
                    v-else-if="
                      message.role === 'tool' ||
                      message.message_type === 'tool_result' ||
                      message.message_type === 'assistant_tool_call'
                    "
                    aria-hidden="true"
                  />
                  <FileCode v-else-if="message.role === 'system'" aria-hidden="true" />
                  <Bot v-else aria-hidden="true" />
                </span>
                <div>
                  <h3 class="message-role">{{ messageRoleLabel(message) }}</h3>
                  <p class="subtle">{{ messageMeta(message) }}</p>
                  <p
                    v-if="message.tool_name || message.tool_call_id"
                    class="subtle"
                  >
                    tool: {{ message.tool_name || '--' }}
                    <span v-if="message.tool_call_id"
                      >({{ message.tool_call_id }})</span
                    >
                  </p>
                </div>
              </header>

              <details
                v-if="message.role === 'system'"
                class="message-details"
              >
                <summary>系统指令</summary>
                <pre class="message-content">{{ messageContent(message) }}</pre>
              </details>

              <div
                v-else-if="message.message_type === 'assistant_tool_call'"
                class="tool-call-stack"
              >
                <p class="subtle">{{ messageContent(message) }}</p>
                <article
                  v-for="call in message.tool_calls || []"
                  :key="toolCallId(call)"
                  class="tool-inline-block"
                >
                  <header class="tool-inline-header">
                    <span>{{ toolCallName(call) }}</span>
                    <code>{{ toolCallId(call) }}</code>
                  </header>
                  <pre class="message-content code-like">{{
                    toolCallArguments(call)
                  }}</pre>
                </article>
              </div>

              <pre v-else class="message-content">{{
                messageContent(message)
              }}</pre>
            </article>
            <p v-if="!selectedDetail.messages.length" class="empty-copy">
              暂无消息明细
            </p>
          </div>

          <div v-else-if="activeTab === 'raw'" class="detail-pane stack">
            <div class="raw-availability">
              <span
                v-for="(available, key) in (selectedRaw?.availability ?? selectedDetail.raw_available)"
                :key="key"
                class="raw-flag"
                :class="{ 'raw-flag-on': available }"
              >
                {{ rawFlagLabel(String(key)) }}
                {{ available ? '可用' : '不可用' }}
              </span>
            </div>

            <p v-if="rawError" class="inline-error" role="alert">
              {{ rawError }}
            </p>
            <p v-else-if="rawLoading" class="empty-copy">原始请求响应加载中...</p>

            <section v-else class="raw-exchange-section">
              <p
                v-if="
                  selectedRaw &&
                    selectedRaw.request_stage === 'unavailable' &&
                    selectedRaw.response_stage === 'unavailable'
                "
                class="empty-copy"
              >
                Raw Exchange 未捕获
                <span v-if="selectedRaw.redaction.notes.length">
                  · {{ selectedRaw.redaction.notes.join('；') }}
                </span>
              </p>
              <div class="raw-exchange-grid">
                <JsonViewer
                  title="请求"
                  :stage="stageLabel(selectedRaw?.request_stage || 'unavailable')"
                  :value="selectedRaw?.request_json ?? null"
                  empty-text="请求 JSON 不可用"
                />
                <JsonViewer
                  title="响应"
                  :stage="stageLabel(selectedRaw?.response_stage || 'unavailable')"
                  :value="selectedRaw?.response_json ?? null"
                  empty-text="响应 JSON 不可用"
                />
              </div>
            </section>

            <section class="persisted-record-section stack">
              <h3 class="subsection-title">持久化记录</h3>
            <article
              v-for="record in selectedRaw?.persisted_records ?? selectedDetail.raw_records"
              :key="record.id"
              class="raw-record"
            >
              <header class="raw-record-header">
                <div>
                  <h3>{{ record.label }}</h3>
                  <p class="subtle">
                    {{ record.kind }} · {{ record.source_table }} ·
                    {{ record.created_at || '--' }}
                  </p>
                </div>
                <button
                  class="button button-muted button-inline"
                  type="button"
                  @click="copyRawRecord(record)"
                >
                  <Copy aria-hidden="true" />
                  <span>{{
                    copiedRecordId === record.id ? '已复制' : '复制'
                  }}</span>
                </button>
              </header>
              <pre class="raw-json-block">{{ formatJson(record.raw_json) }}</pre>
            </article>
            <p
              v-if="!(selectedRaw?.persisted_records ?? selectedDetail.raw_records).length"
              class="empty-copy"
            >
              暂无持久化 raw 记录
            </p>
            </section>
          </div>

          <div v-else-if="activeTab === 'tools'" class="detail-pane stack">
            <section class="tool-section">
              <header class="tool-section-header">
                <Wrench aria-hidden="true" />
                <h3>工具定义</h3>
              </header>
              <article
                v-for="tool in selectedDetail.tool_definitions"
                :key="`${tool.source}-${tool.id || tool.seq}`"
                class="tool-detail-block"
              >
                <header class="tool-inline-header">
                  <span>{{ tool.tool_name || '--' }}</span>
                  <code>{{ tool.source }}</code>
                </header>
                <p class="subtle">{{ tool.description || '--' }}</p>
                <pre class="raw-json-block">{{
                  formatJson(tool.parameters_json)
                }}</pre>
              </article>
              <p v-if="!selectedDetail.tool_definitions.length" class="empty-copy">
                暂无工具定义
              </p>
            </section>

            <section class="tool-section">
              <header class="tool-section-header">
                <Braces aria-hidden="true" />
                <h3>工具调用</h3>
              </header>
              <article
                v-for="toolCall in selectedDetail.tool_calls"
                :key="toolCall.id"
                class="tool-detail-block"
              >
                <header class="tool-inline-header">
                  <span>{{ toolCall.tool_name || '--' }}</span>
                  <code>{{ toolCall.tool_call_id || '--' }}</code>
                </header>
                <p class="subtle">
                  {{ toolCall.status }} · {{ toolCall.created_at || '--' }}
                  <span v-if="toolCall.completed_at">
                    -> {{ toolCall.completed_at }}</span
                  >
                </p>
                <div class="tool-json-grid">
                  <div>
                    <div class="json-block-title">
                      <span>Arguments</span>
                      <button
                        class="icon-button icon-button-compact"
                        type="button"
                        aria-label="复制工具参数"
                        @click="
                          copyJsonBlock(
                            `tool-arguments-${toolCall.id}`,
                            toolCall.arguments_json,
                          )
                        "
                      >
                        <Copy aria-hidden="true" />
                      </button>
                    </div>
                    <pre class="raw-json-block">{{
                      formatJson(toolCall.arguments_json)
                    }}</pre>
                  </div>
                  <div>
                    <div class="json-block-title">
                      <span>Result</span>
                      <button
                        class="icon-button icon-button-compact"
                        type="button"
                        aria-label="复制工具结果"
                        @click="
                          copyJsonBlock(
                            `tool-result-${toolCall.id}`,
                            toolCall.result_json,
                          )
                        "
                      >
                        <Copy aria-hidden="true" />
                      </button>
                    </div>
                    <pre class="raw-json-block">{{
                      formatJson(toolCall.result_json)
                    }}</pre>
                  </div>
                </div>
              </article>
              <p v-if="!selectedDetail.tool_calls.length" class="empty-copy">
                暂无工具调用
              </p>
            </section>
          </div>

          <div v-else class="detail-pane event-list">
            <article
              v-for="event in selectedDetail.events"
              :key="event.id"
              class="event-item"
            >
              <span class="event-icon">
                <Clock aria-hidden="true" />
              </span>
              <div class="stack-sm">
                <header class="event-header">
                  <h3>{{ event.event_type }}</h3>
                  <span class="subtle">{{ event.created_at || '--' }}</span>
                </header>
                <p class="subtle">{{ event.provider_name || '--' }}</p>
                <pre class="raw-json-block">{{
                  formatJson(event.payload_json)
                }}</pre>
              </div>
            </article>
            <p v-if="!selectedDetail.events.length" class="empty-copy">
              暂无请求事件
            </p>
          </div>
        </template>
      </section>
    </div>
  </section>
</template>
