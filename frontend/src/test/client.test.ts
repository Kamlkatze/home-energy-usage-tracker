import { describe, expect, it, vi } from 'vitest';
import { AxiosError } from 'axios';
import type { AxiosResponse } from 'axios';
import {
  costsApi,
  electricityApi,
  metersApi,
  readingsApi,
  tariffsApi,
} from '../api/client';

// setup.ts globally mocks ../api/client so route components never hit the
// network. These unit tests exercise the REAL client implementation instead,
// so the global mock is disabled for this file and only the axios module is
// mocked (its create() factory returns a shared instance whose HTTP verbs are
// vi.fn()s the tests can drive).
vi.unmock('../api/client');

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

// Helper to build a realistic AxiosError for a given HTTP status code.
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

const MOCK_METER = {
  id: 1,
  meter_type: 'gas',
  label: 'Gas-Hauptzähler',
  meter_number: '123456789',
  unit: 'm³',
  created_at: '2024-01-01T00:00:00Z',
  replaces_meter_id: null,
};

describe('metersApi', () => {
  it('getTypes returns the response data on success', async () => {
    const types = [{ value: 'gas', label: 'Gas', unit: 'm³' }];
    mockAxiosInstance.get.mockResolvedValue({ data: types });

    await expect(metersApi.getTypes()).resolves.toEqual(types);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/meters/types');
  });

  it('getAll returns the response data on success', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: [MOCK_METER] });

    await expect(metersApi.getAll()).resolves.toEqual([MOCK_METER]);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/meters/');
  });

  it('getCurrent returns the response data on success', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: MOCK_METER });

    await expect(metersApi.getCurrent()).resolves.toEqual(MOCK_METER);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/meters/current');
  });

  it('getById requests the meter-specific endpoint', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: MOCK_METER });

    await expect(metersApi.getById(7)).resolves.toEqual(MOCK_METER);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/meters/7');
  });

  it('create posts the payload and resolves with the created meter', async () => {
    mockAxiosInstance.post.mockResolvedValue({ data: MOCK_METER });
    const payload = { meter_type: 'gas', label: 'Neuer Zähler' };

    await expect(metersApi.create(payload)).resolves.toEqual(MOCK_METER);
    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      '/api/meters/',
      payload,
    );
  });

  it('update puts the payload to the meter-specific endpoint', async () => {
    mockAxiosInstance.put.mockResolvedValue({ data: MOCK_METER });
    const payload = { label: 'Umbenannt' };

    await expect(metersApi.update(7, payload)).resolves.toEqual(MOCK_METER);
    expect(mockAxiosInstance.put).toHaveBeenCalledWith(
      '/api/meters/7',
      payload,
    );
  });

  it('delete calls the meter-specific endpoint', async () => {
    mockAxiosInstance.delete.mockResolvedValue({ data: null });

    await expect(metersApi.delete(7)).resolves.toBeNull();
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/api/meters/7');
  });

  it('getReadings requests the readings endpoint for the meter', async () => {
    const readings: Array<{ id: number }> = [{ id: 1 }];
    mockAxiosInstance.get.mockResolvedValue({ data: readings });

    await expect(metersApi.getReadings(7)).resolves.toEqual(readings);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/meters/7/readings');
  });

  it('getLastReading returns the last reading when readings exist', async () => {
    const readings = [
      { id: 1, meter_id: 7, value: '100', reading_date: '2024-01-01', note: null, created_at: '2024-01-01T00:00:00Z' },
      { id: 2, meter_id: 7, value: '150', reading_date: '2024-02-01', note: null, created_at: '2024-02-01T00:00:00Z' },
    ];
    mockAxiosInstance.get.mockResolvedValue({ data: readings });

    await expect(metersApi.getLastReading(7)).resolves.toEqual(readings[1]);
  });

  it('getLastReading returns null when no readings exist', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: [] });

    await expect(metersApi.getLastReading(7)).resolves.toBeNull();
  });

  it('propagates a 500 HTTP error from the server', async () => {
    mockAxiosInstance.get.mockRejectedValue(httpError(500));

    await expect(metersApi.getAll()).rejects.toMatchObject({
      response: { status: 500 },
    });
  });

  it('propagates a network error (non-Axios error)', async () => {
    mockAxiosInstance.get.mockRejectedValue(new Error('Network Error'));

    await expect(metersApi.getAll()).rejects.toThrow('Network Error');
  });
});

describe('readingsApi', () => {
  it('getAll returns the response data on success', async () => {
    const readings: Array<{ id: number }> = [];
    mockAxiosInstance.get.mockResolvedValue({ data: readings });

    await expect(readingsApi.getAll()).resolves.toEqual(readings);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/readings/');
  });

  it('getById requests the reading-specific endpoint', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: { id: 3 } });

    await expect(readingsApi.getById(3)).resolves.toEqual({ id: 3 });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/readings/3');
  });

  it('create posts the payload and resolves with the created reading', async () => {
    const payload = { meter_id: 1, value: 123.4, reading_date: '2024-01-01', note: null };
    mockAxiosInstance.post.mockResolvedValue({ data: { id: 9, ...payload } });

    await expect(readingsApi.create(payload)).resolves.toEqual({
      id: 9,
      ...payload,
    });
    expect(mockAxiosInstance.post).toHaveBeenCalledWith(
      '/api/readings/',
      payload,
    );
  });

  it('update puts the payload to the reading-specific endpoint', async () => {
    mockAxiosInstance.put.mockResolvedValue({ data: { id: 3, value: '200' } });

    await expect(
      readingsApi.update(3, { value: '200' }),
    ).resolves.toEqual({ id: 3, value: '200' });
    expect(mockAxiosInstance.put).toHaveBeenCalledWith('/api/readings/3', {
      value: '200',
    });
  });

  it('delete calls the reading-specific endpoint', async () => {
    mockAxiosInstance.delete.mockResolvedValue({ data: null });

    await expect(readingsApi.delete(3)).resolves.toBeNull();
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/api/readings/3');
  });

  it('propagates a 400 HTTP error from create', async () => {
    mockAxiosInstance.post.mockRejectedValue(httpError(400));

    await expect(readingsApi.create({})).rejects.toMatchObject({
      response: { status: 400 },
    });
  });
});

describe('tariffsApi', () => {
  it('getAll returns the response data on success', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: [] });

    await expect(tariffsApi.getAll()).resolves.toEqual([]);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/tariffs/');
  });

  it('getById requests the tariff-specific endpoint', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: { id: 4 } });

    await expect(tariffsApi.getById(4)).resolves.toEqual({ id: 4 });
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/tariffs/4');
  });

  it('create posts the payload and resolves with the created tariff', async () => {
    const payload = { meter_id: 1, price_per_unit: '0.30' };
    mockAxiosInstance.post.mockResolvedValue({ data: { id: 5, ...payload } });

    await expect(tariffsApi.create(payload)).resolves.toEqual({
      id: 5,
      ...payload,
    });
    expect(mockAxiosInstance.post).toHaveBeenCalledWith('/api/tariffs/', payload);
  });

  it('update puts the payload to the tariff-specific endpoint', async () => {
    mockAxiosInstance.put.mockResolvedValue({ data: { id: 5 } });

    await expect(tariffsApi.update(5, { comment: 'neu' })).resolves.toEqual({
      id: 5,
    });
    expect(mockAxiosInstance.put).toHaveBeenCalledWith('/api/tariffs/5', {
      comment: 'neu',
    });
  });

  it('delete calls the tariff-specific endpoint', async () => {
    mockAxiosInstance.delete.mockResolvedValue({ data: null });

    await expect(tariffsApi.delete(5)).resolves.toBeNull();
    expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/api/tariffs/5');
  });

  it('getUsage requests the usage endpoint for the tariff', async () => {
    const usage = { tariff_id: 5, reading_count: 2, in_use: true };
    mockAxiosInstance.get.mockResolvedValue({ data: usage });

    await expect(tariffsApi.getUsage(5)).resolves.toEqual(usage);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/tariffs/5/usage');
  });

  it('propagates a 500 HTTP error from delete', async () => {
    mockAxiosInstance.delete.mockRejectedValue(httpError(500));

    await expect(tariffsApi.delete(5)).rejects.toMatchObject({
      response: { status: 500 },
    });
  });
});

describe('costsApi', () => {
  it('getYearsOverview returns the response data on success', async () => {
    const overview: Array<{ year: number }> = [{ year: 2024 }];
    mockAxiosInstance.get.mockResolvedValue({ data: overview });

    await expect(costsApi.getYearsOverview()).resolves.toEqual(overview);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/costs/years-overview');
  });

  it('getYearlyProjection sends meter_id and year as query params', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: null });

    await expect(costsApi.getYearlyProjection(3, 2024)).resolves.toBeNull();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith(
      '/api/costs/yearly-projection',
      { params: { meter_id: 3, year: 2024 } },
    );
  });

  it('getWastewaterCosts sends the required params without a garden meter', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: null });

    await expect(
      costsApi.getWastewaterCosts(1, '2024-01-01', '2024-12-31'),
    ).resolves.toBeNull();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/costs/wastewater/', {
      params: {
        water_cold_meter_id: 1,
        from: '2024-01-01',
        to: '2024-12-31',
      },
    });
  });

  it('getWastewaterCosts includes the garden meter param when provided', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: null });

    await costsApi.getWastewaterCosts(1, '2024-01-01', '2024-12-31', 2);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith('/api/costs/wastewater/', {
      params: {
        water_cold_meter_id: 1,
        from: '2024-01-01',
        to: '2024-12-31',
        water_garden_meter_id: 2,
      },
    });
  });

  it('getAdvancePaymentDiffByCategory sends gas params with meter and as-of date', async () => {
    const diff = { meter_id: 3, year: 2024, category: 'gas' };
    mockAxiosInstance.get.mockResolvedValue({ data: diff });

    await expect(
      costsApi.getAdvancePaymentDiffByCategory('gas', 2024, 3, undefined, undefined, '2024-12-31'),
    ).resolves.toEqual(diff);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith(
      '/api/costs/advance-payment-diff-by-category',
      { params: { category: 'gas', year: 2024, meter_id: 3, as_of_date: '2024-12-31' } },
    );
  });

  it('getAdvancePaymentDiffByCategory sends both water meter params for wastewater', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: null });

    await costsApi.getAdvancePaymentDiffByCategory('wastewater', 2024, undefined, 1, 2);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith(
      '/api/costs/advance-payment-diff-by-category',
      {
        params: {
          category: 'wastewater',
          year: 2024,
          water_cold_meter_id: 1,
          water_garden_meter_id: 2,
        },
      },
    );
  });

  it('getAdvancePaymentDiffByCategory returns null on a 404 response', async () => {
    mockAxiosInstance.get.mockRejectedValue(httpError(404));

    await expect(
      costsApi.getAdvancePaymentDiffByCategory('gas', 2024),
    ).resolves.toBeNull();
  });

  it('getAdvancePaymentDiffByCategory propagates non-404 HTTP errors', async () => {
    mockAxiosInstance.get.mockRejectedValue(httpError(500));

    await expect(
      costsApi.getAdvancePaymentDiffByCategory('gas', 2024),
    ).rejects.toMatchObject({ response: { status: 500 } });
  });

  it('getAdvancePaymentDiffByCategory propagates network errors', async () => {
    mockAxiosInstance.get.mockRejectedValue(new Error('Network Error'));

    await expect(
      costsApi.getAdvancePaymentDiffByCategory('gas', 2024),
    ).rejects.toThrow('Network Error');
  });

  it('getConsumptionTimeseries sends from/to params and returns the data', async () => {
    const items = [{ meter_id: 1, points: [] }];
    mockAxiosInstance.get.mockResolvedValue({ data: items });

    await expect(
      costsApi.getConsumptionTimeseries('2024-01-01', '2024-12-31'),
    ).resolves.toEqual(items);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith(
      '/api/costs/consumption-timeseries',
      { params: { from: '2024-01-01', to: '2024-12-31' } },
    );
  });

  it('getConsumptionTimeseries includes meter_type when provided', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: [] });

    await costsApi.getConsumptionTimeseries('2024-01-01', '2024-12-31', 'gas');
    expect(mockAxiosInstance.get).toHaveBeenCalledWith(
      '/api/costs/consumption-timeseries',
      { params: { from: '2024-01-01', to: '2024-12-31', meter_type: 'gas' } },
    );
  });

  it('getConsumptionTimeseries passes through an unexpected response shape unchanged', async () => {
    const unexpected = { not: 'an array' };
    mockAxiosInstance.get.mockResolvedValue({ data: unexpected });

    await expect(
      costsApi.getConsumptionTimeseries('2024-01-01', '2024-12-31'),
    ).resolves.toEqual(unexpected);
  });
});

describe('electricityApi', () => {
  it('getFeedInCompensation sends the production/export meter ids and date range', async () => {
    const compensation = { total_compensation: '12.34' };
    mockAxiosInstance.get.mockResolvedValue({ data: compensation });

    await expect(
      electricityApi.getFeedInCompensation(1, 2, '2024-01-01', '2024-12-31'),
    ).resolves.toEqual(compensation);
    expect(mockAxiosInstance.get).toHaveBeenCalledWith(
      '/api/electricity/feed-in-compensation',
      {
        params: {
          production_meter_id: 1,
          export_meter_id: 2,
          from: '2024-01-01',
          to: '2024-12-31',
        },
      },
    );
  });

  it('getFeedInCompensationProjection sends the meter ids and year', async () => {
    mockAxiosInstance.get.mockResolvedValue({ data: null });

    await expect(
      electricityApi.getFeedInCompensationProjection(1, 2, 2024),
    ).resolves.toBeNull();
    expect(mockAxiosInstance.get).toHaveBeenCalledWith(
      '/api/electricity/feed-in-compensation-projection',
      {
        params: { production_meter_id: 1, export_meter_id: 2, year: 2024 },
      },
    );
  });

  it('propagates a 500 HTTP error from the server', async () => {
    mockAxiosInstance.get.mockRejectedValue(httpError(500));

    await expect(
      electricityApi.getFeedInCompensation(1, 2, '2024-01-01', '2024-12-31'),
    ).rejects.toMatchObject({ response: { status: 500 } });
  });
});
