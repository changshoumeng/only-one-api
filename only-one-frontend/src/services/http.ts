import axios, { AxiosError, type AxiosRequestConfig } from 'axios';

export interface BackendEnvelope<T = unknown> {
  status: number;
  msg?: string;
  data?: T;
}

export class BackendApiError extends Error {
  statusCode?: number;
  backendStatus?: number;

  constructor(message: string, options: { statusCode?: number; backendStatus?: number } = {}) {
    super(message);
    this.name = 'BackendApiError';
    this.statusCode = options.statusCode;
    this.backendStatus = options.backendStatus;
  }
}

export const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
  withCredentials: true,
  timeout: 30000,
});

function normalizeTransportError(error: unknown): BackendApiError {
  if (error instanceof BackendApiError) {
    return error;
  }

  if (error instanceof AxiosError) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
    const message = detail || error.message || '请求失败，请稍后重试';
    return new BackendApiError(message, { statusCode: error.response?.status });
  }

  if (error instanceof Error) {
    return new BackendApiError(error.message);
  }

  return new BackendApiError('请求失败，请稍后重试');
}

export async function requestEnvelope<T = unknown>(
  config: AxiosRequestConfig,
): Promise<BackendEnvelope<T>> {
  try {
    const response = await httpClient.request<BackendEnvelope<T>>(config);
    const envelope = response.data;

    if (!envelope || typeof envelope.status !== 'number') {
      throw new BackendApiError('后端返回格式异常');
    }

    if (envelope.status !== 0) {
      throw new BackendApiError(envelope.msg || '操作失败', {
        backendStatus: envelope.status,
        statusCode: response.status,
      });
    }

    return envelope;
  } catch (error) {
    throw normalizeTransportError(error);
  }
}

export async function requestData<T = unknown>(
  config: AxiosRequestConfig,
  fallback: T,
): Promise<T> {
  const envelope = await requestEnvelope<T>(config);
  return envelope.data ?? fallback;
}

