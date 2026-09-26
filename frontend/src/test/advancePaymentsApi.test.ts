import { describe, expect, it, vi } from 'vitest';
import { AxiosError } from 'axios';
import type { AxiosResponse } from 'axios';
import { advancePaymentsApi } from '../api/advancePaymentsApi';

// setup.ts globally mocks both ../api/client and ../api/advancePaymentsApi so
// route components never hit the network. These unit tests exercise the REAL
// advancePaymentsApi implementation, so the global mocks are disabled and the
// axios module is mocked instead: the real client module's apiClient then
// calls the shared instance below.
vi.unmock('../api/client');
vi.unmock('../api/advancePaymentsApi');

const { mockAxiosInstance } = vi.hoisted(() => ({
  mockAxiosInstance: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('axios', async () => {
  const actual = await vi.importActual<typeof import('axios')>('axios');
  return {
    ...actual,
    default: {
      ...actual.default,
      create: vi.fn(() => mockAxiosInstance),
    },
  };
});

const httpError = (status: number): AxiosError =>
  new AxiosError(
    `Request failed with status code ${status}`,
    AxiosError.ERR_BAD_RESPONSE,
    undefined,
    undefined,
    {
      data: { detail: 'boom' },
      status,
      statusText: 'Error',
      headers: {},
      config: { headers: {} },
    } as unknown as AxiosResponse,
  );

const PAYMENT = {
  id: 1,
  category: 'gas',
  meter_id: 1,
  water_cold_meter_id: null,
  water_garden_meter_id: null,
  valid_from: '2024-01-01',
  valid_to: null,
  monthly_amount: '80.00',
  comment: null,
  created_at: '2024-01-01T00:00:00Z',
};

describe('advancePaymentsApi', () => {
  it('getAll returns the response data and forwards the filter params', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: [PAYMENT] });

    await expect(
      advancePaymentsApi.getAll({ meter_id: 1, category: 'gas' }),
    ).resolves.toEqual([PAYMENT]);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/advance-payments/', {
      params: { meter_id: 1, category: 'gas' },
    });
  });

  it('getAll works without params', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: [] });

    await expect(advancePaymentsApi.getAll()).resolves.toEqual([]);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/advance-payments/', {
      params: undefined,
    });
  });

  it('getById requests the payment-specific endpoint', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: PAYMENT });

    await expect(advancePaymentsApi.getById(1)).resolves.toEqual(PAYMENT);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/advance-payments/1');
  });

  it('create posts the payload and resolves with the created payment', async () => {
    const payload = { category: 'gas', meter_id: 1, monthly_amount: '80.00' };
    mockAxiosInstance.post.mockResolvedValue({ data: PAYMENT });

    await expect(advancePaymentsApi.create(payload)).resolves.toEqual(PAYMENT);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      '/api/advance-payments/',
      payload,
    );
  });

  it('update puts the payload to the payment-specific endpoint', async () => {
    const payload = { monthly_amount: '90.00' };
    mockAxiosInstance.put.mockResolvedValue({ data: { ...PAYMENT, ...payload } });

    await expect(advancePaymentsApi.update(1, payload)).resolves.toEqual({
      ...PAYMENT,
      ...payload,
    });
    expect(mockAxiosInstance.put).toHaveBeenCalledWith(
      '/api/advance-payments/1',
      payload,
    );
  });

  it('delete calls the payment-specific endpoint', async () => {
    mockAxiosInstance.delete.mockResolvedValue({ data: null });

    await expect(advancePaymentsApi.delete(1)).resolves.toBeNull();
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/api/advance-payments/1');
  });

  it('propagates a 500 HTTP error from getAll', async () => {
    mockAxiosInstance.get.mockRejectedValue(httpError(500));

    await expect(advancePaymentsApi.getAll()).rejects.toMatchObject({
      response: { status: 500 },
    });
  });

  it('propagates a 400 HTTP error from create', async () => {
    mockAxiosInstance.post.mockRejectedValue(httpError(400));

    await expect(advancePaymentsApi.create({})).rejects.toMatchObject({
      response: { status: 400 },
    });
  });

  it('propagates a network error (non-Axios error) from update', async () => {
    mockAxiosInstance.put.mockRejectedValue(new Error('Network Error'));

    await expect(advancePaymentsApi.update(1, {})).rejects.toThrow(
      'Network Error',
    );
  });

  it('passes through an unexpected response shape unchanged', async () => {
    const unexpected = { not: 'an array' };
    mockAxiosInstance.get.mockResolvedValue({ data: unexpected });

    await expect(advancePaymentsApi.getAll()).resolves.toEqual(unexpected);
  });
});
