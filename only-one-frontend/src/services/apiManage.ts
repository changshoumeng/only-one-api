import { requestData, requestEnvelope } from './http';
import type {
  BillingUnit,
  KeyItem,
  ModelItem,
  ModelTestResult,
  PageRows,
  ProviderItem,
  SelectOption,
} from './types';

export interface PageQuery {
  page: number;
  perPage: number;
}

export interface ProviderPayload {
  id?: string;
  provider_name: string;
  provider_english_name: string;
  api_key: string;
  base_url: string;
}

export interface ModelPayload {
  id?: string;
  status?: boolean;
  provider_english_name: string;
  model_name: string;
  model_id: string;
  billing_unit: BillingUnit;
  input_unit_price: number | string;
  output_unit_price: number | string;
  default_params?: string | null;
}

export function listProviders(params: PageQuery) {
  return requestData<PageRows<ProviderItem>>(
    {
      method: 'GET',
      url: '/backend/api-manage/provider/list',
      params,
    },
    { count: 0, rows: [] },
  );
}

export function listProviderOptions() {
  return requestData<SelectOption[]>(
    {
      method: 'GET',
      url: '/backend/api-manage/provider/select',
    },
    [],
  );
}

export function createProvider(data: ProviderPayload) {
  return requestEnvelope({
    method: 'POST',
    url: '/backend/api-manage/provider/create',
    data,
  });
}

export function updateProvider(data: ProviderPayload) {
  return requestEnvelope({
    method: 'POST',
    url: '/backend/api-manage/provider/update',
    data,
  });
}

export function deleteProvider(id: string) {
  return requestEnvelope({
    method: 'GET',
    url: '/backend/api-manage/provider/delete',
    params: { id },
  });
}

export function listModels(params: PageQuery) {
  return requestData<PageRows<ModelItem>>(
    {
      method: 'GET',
      url: '/backend/api-manage/model/list',
      params,
    },
    { count: 0, rows: [] },
  );
}

export function createModel(data: ModelPayload) {
  return requestEnvelope({
    method: 'POST',
    url: '/backend/api-manage/model/create',
    data,
  });
}

export function updateModel(data: ModelPayload) {
  return requestEnvelope({
    method: 'POST',
    url: '/backend/api-manage/model/update',
    data,
  });
}

export function toggleModelStatus(id: string) {
  return requestEnvelope({
    method: 'GET',
    url: '/backend/api-manage/model/update-status',
    params: { id },
  });
}

export function deleteModel(id: string) {
  return requestEnvelope({
    method: 'GET',
    url: '/backend/api-manage/model/delete',
    params: { id },
  });
}

export function testModel(id: string) {
  return requestData<ModelTestResult>(
    {
      method: 'POST',
      url: '/backend/api-manage/model/test',
      data: { id },
    },
    {
      test_status: 'upstream_failed',
      available: false,
      request: {
        url: '',
        method: 'POST',
        body: {},
        curl: '',
        curl_display: '',
      },
      error: {
        code: 'EMPTY_RESPONSE',
        message: '模型测试接口返回为空',
      },
    },
  );
}

export function listKeys(params: PageQuery) {
  return requestData<PageRows<KeyItem>>(
    {
      method: 'GET',
      url: '/backend/api-manage/key/list',
      params,
    },
    { count: 0, rows: [] },
  );
}

export function createKey() {
  return requestEnvelope({
    method: 'GET',
    url: '/backend/api-manage/key/create',
  });
}

export function toggleKeyStatus(id: string) {
  return requestEnvelope({
    method: 'GET',
    url: '/backend/api-manage/key/update-status',
    params: { id },
  });
}

export function updateKeyRemark(id: string, remark: string) {
  return requestEnvelope({
    method: 'POST',
    url: '/backend/api-manage/key/update-remark',
    data: { id, remark },
  });
}

export function deleteKey(id: string) {
  return requestEnvelope({
    method: 'GET',
    url: '/backend/api-manage/key/delete',
    params: { id },
  });
}
