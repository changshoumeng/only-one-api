import { describe, expect, it, vi, beforeEach } from 'vitest';
import { httpClient, requestEnvelope, BackendApiError } from '@/services/http';

describe('requestEnvelope', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns backend data for successful envelopes', async () => {
    vi.spyOn(httpClient, 'request').mockResolvedValueOnce({
      data: {
        status: 0,
        msg: 'ok',
        data: { hello: 'world' },
      },
    } as never);

    await expect(requestEnvelope({ url: '/test' })).resolves.toEqual({
      status: 0,
      msg: 'ok',
      data: { hello: 'world' },
    });
  });

  it('throws backend errors when the envelope status is non-zero', async () => {
    vi.spyOn(httpClient, 'request').mockResolvedValueOnce({
      data: {
        status: 1,
        msg: '拒绝',
        data: {},
      },
    } as never);

    await expect(requestEnvelope({ url: '/test' })).rejects.toBeInstanceOf(BackendApiError);
  });
});

