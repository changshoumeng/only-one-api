export interface PageRows<T> {
  count: number;
  rows: T[];
}

export interface SelectOption {
  label: string;
  value: string;
}

export interface ProviderItem {
  id: string;
  row_id: number;
  provider_name: string;
  provider_english_name: string;
  api_key?: string;
  base_url: string;
  create_time: string;
}

export interface ModelItem {
  id: string;
  row_id: number;
  status: boolean;
  provider_english_name: string;
  model_name: string;
  model_id: string;
  billing_unit: BillingUnit;
  input_unit_price: number;
  output_unit_price: number;
  input_unit_price_thousand: number;
  output_unit_price_thousand: number;
  input_unit_price_million: number;
  output_unit_price_million: number;
  default_params?: string | null;
  create_time: string;
}

export type BillingUnit = 'per_thousand_tokens' | 'per_million_tokens' | 'per_image';

export type ModelTestStatus =
  | 'success'
  | 'auth_failed'
  | 'model_disabled'
  | 'model_not_found'
  | 'upstream_failed'
  | 'invalid_response'
  | 'timeout';

export interface ModelTestModel {
  id: string;
  provider_english_name?: string;
  model_name?: string;
  model_id?: string;
}

export interface ModelTestRequestInfo {
  url: string;
  method: 'POST';
  body: unknown;
  curl: string;
  curl_display?: string;
}

export interface ModelTestResponseInfo {
  http_status?: number | null;
  request_id?: string;
  duration_ms?: number;
  content?: string;
  raw?: unknown;
}

export interface ModelTestErrorInfo {
  code: string;
  message: string;
}

export interface ModelTestResult {
  test_status: ModelTestStatus;
  available: boolean;
  stage?: string;
  model?: ModelTestModel;
  request: ModelTestRequestInfo;
  response?: ModelTestResponseInfo;
  error?: ModelTestErrorInfo | null;
  tested_at?: string;
}

export interface KeyItem {
  id: string;
  row_id: number;
  api_key: string;
  remark?: string;
  status: boolean;
  create_time: string;
}

export interface UsageSummary {
  total_request: string;
  total_tokens: string;
  total_price: string;
}

export interface EChartLinePayload {
  xAxis?: {
    data?: string[];
  };
  series?: Array<{
    data?: Array<number | string | null>;
  }>;
}

export interface ChatContextItem {
  id?: string | null;
  history_id?: string;
  seq?: number | null;
  role: string;
  message_type: string;
  content: string;
  content_json?: unknown;
  received_at: string;
  token_count: number | null;
  token_source: string;
  tool_name?: string | null;
  tool_call_id?: string | null;
  tool_calls?: unknown[];
  raw_record_id?: string | null;
}

export interface RawAvailability {
  persisted_records: boolean;
  inbound_request: boolean;
  normalized_request: boolean;
  provider_outbound: boolean;
  provider_response: boolean;
  stream_chunks: boolean;
}

export type RawRequestStage =
  | 'provider_outbound'
  | 'normalized'
  | 'inbound'
  | 'unavailable';

export type RawResponseStage =
  | 'provider_response'
  | 'stream_summary'
  | 'provider_error'
  | 'unavailable';

export type SnapshotStatus =
  | 'captured'
  | 'partial'
  | 'failed'
  | 'redacted'
  | 'truncated'
  | 'unavailable';

export interface RawExchangeRedaction {
  redaction_version: string;
  payload_bytes: number;
  truncated: boolean;
  truncated_fields: string[];
  notes: string[];
}

export interface ChatHistorySummary {
  history_id: string;
  id: string;
  row_id: number | null;
  request_id: string | null;
  model_name: string | null;
  provider_name: string | null;
  model_id: string | null;
  prompt_preview: string;
  prompt?: string;
  prompt_full?: string;
  finish_status: string;
  usage_source: string;
  prompt_tokens: number;
  completion_tokens: number;
  input_price: number;
  output_price: number;
  total_price: number;
  input_price_display: string;
  output_price_display: string;
  total_price_display: string;
  duration_seconds: number | null;
  duration: string;
  create_time: string;
  update_time: string;
  error_message?: string | null;
}

export interface ChatMessageView extends ChatContextItem {
  id: string | null;
  history_id: string;
  seq: number | null;
}

export interface ToolDefinitionView {
  id: string | null;
  history_id: string;
  seq: number | null;
  tool_type: string;
  tool_name: string | null;
  description: string;
  parameters_json: unknown;
  raw_json: unknown;
  received_at: string;
  source: 'llm_chat_message' | 'legacy_context' | string;
  raw_record_id?: string | null;
}

export interface ToolCallView {
  id: string;
  history_id: string;
  message_id: string | null;
  tool_call_id: string | null;
  tool_name: string | null;
  arguments_json: unknown;
  result_json: unknown;
  status: string;
  created_at: string;
  completed_at: string;
  raw_record_id?: string | null;
}

export interface RequestEventView {
  id: string;
  history_id: string;
  event_type: string;
  provider_name: string | null;
  payload_json: unknown;
  created_at: string;
  raw_record_id?: string | null;
}

export interface RawRecordView {
  id: string;
  kind: string;
  label: string;
  source_table: string;
  source_id: string | null;
  seq: number | null;
  created_at: string;
  raw_json: unknown;
}

export interface RawSnapshotView {
  id: string;
  history_id: string;
  request_id: string | null;
  snapshot_status: SnapshotStatus;
  redaction_version: string;
  created_at: string;
  updated_at: string;
}

export interface ChatRawExchange {
  history_id: string;
  request_id: string | null;
  request_stage: RawRequestStage;
  response_stage: RawResponseStage;
  request_json: unknown | null;
  response_json: unknown | null;
  availability: RawAvailability;
  redaction: RawExchangeRedaction;
  snapshots: RawSnapshotView[];
  persisted_records: RawRecordView[];
}

export interface ChatHistoryDetail {
  summary: ChatHistorySummary;
  messages: ChatMessageView[];
  tool_definitions: ToolDefinitionView[];
  tool_calls: ToolCallView[];
  events: RequestEventView[];
  raw_records: RawRecordView[];
  raw_available: RawAvailability;
}

export type ChatHistoryItem = ChatHistorySummary;
