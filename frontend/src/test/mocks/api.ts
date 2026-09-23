import { vi } from 'vitest';

// Module-level API mocks used by the smoke tests. Every function that a route
// component can call is mocked here so that no network request is ever
// attempted during tests. The default implementations resolve to empty or
// minimal data, which lets the route components render their "empty" state.
// Tests can override a specific function via `vi.mocked(...)` before rendering.

export const METER_TYPE_INFO = [
  { value: 'gas', label: 'Gas', unit: 'm³' },
  { value: 'water_cold', label: 'Kaltwasser', unit: 'm³' },
  { value: 'water_garden', label: 'Gartenwasser', unit: 'm³' },
  { value: 'electricity_import', label: 'Strom Bezug', unit: 'kWh' },
  { value: 'electricity_export', label: 'Strom Einspeisung', unit: 'kWh' },
  { value: 'electricity_production', label: 'Strom Erzeugung', unit: 'kWh' },
];

export const metersApi = {
  getTypes: vi.fn(),
  getAll: vi.fn(),
  getCurrent: vi.fn(),
  getById: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  delete: vi.fn(),
  getReadings: vi.fn(),
  getLastReading: vi.fn(),
};

export const readingsApi = {
  getAll: vi.fn(),
  getById: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  delete: vi.fn(),
};

export const tariffsApi = {
  getAll: vi.fn(),
  getById: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  delete: vi.fn(),
  getUsage: vi.fn(),
};

export const costsApi = {
  getYearsOverview: vi.fn(),
  getYearlyProjection: vi.fn(),
  getWastewaterCosts: vi.fn(),
  getAdvancePaymentDiffByCategory: vi.fn(),
};

export const electricityApi = {
  getFeedInCompensation: vi.fn(),
  getFeedInCompensationProjection: vi.fn(),
};

export const advancePaymentsApi = {
  getAll: vi.fn(),
  getById: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  delete: vi.fn(),
};

// Resets all mocks to their default implementations. Called in a global
// beforeEach (see setup.ts) so tests are isolated from each other.
export function resetApiMocks(): void {
  metersApi.getTypes.mockResolvedValue(METER_TYPE_INFO);
  metersApi.getAll.mockResolvedValue([]);
  metersApi.getCurrent.mockResolvedValue(null);
  metersApi.getById.mockResolvedValue({
    id: 1,
    meter_type: 'gas',
    label: 'Test Zähler',
    meter_number: null,
    unit: 'm³',
    created_at: '2024-01-01T00:00:00Z',
    replaces_meter_id: null,
  });
  metersApi.create.mockResolvedValue({});
  metersApi.update.mockResolvedValue({});
  metersApi.delete.mockResolvedValue({});
  metersApi.getReadings.mockResolvedValue([]);
  metersApi.getLastReading.mockResolvedValue(null);

  readingsApi.getAll.mockResolvedValue([]);
  readingsApi.getById.mockResolvedValue(null);
  readingsApi.create.mockResolvedValue({});
  readingsApi.update.mockResolvedValue({});
  readingsApi.delete.mockResolvedValue({});

  tariffsApi.getAll.mockResolvedValue([]);
  tariffsApi.getById.mockResolvedValue(null);
  tariffsApi.create.mockResolvedValue({});
  tariffsApi.update.mockResolvedValue({});
  tariffsApi.delete.mockResolvedValue({});
  tariffsApi.getUsage.mockResolvedValue({
    tariff_id: 1,
    meter_id: 1,
    reading_count: 0,
    first_reading_date: null,
    last_reading_date: null,
    in_use: false,
  });

  costsApi.getYearsOverview.mockResolvedValue([]);
  costsApi.getYearlyProjection.mockResolvedValue(null);
  costsApi.getWastewaterCosts.mockResolvedValue(null);
  costsApi.getAdvancePaymentDiffByCategory.mockResolvedValue(null);

  electricityApi.getFeedInCompensation.mockResolvedValue(null);
  electricityApi.getFeedInCompensationProjection.mockResolvedValue(null);

  advancePaymentsApi.getAll.mockResolvedValue([]);
  advancePaymentsApi.getById.mockResolvedValue(null);
  advancePaymentsApi.create.mockResolvedValue({});
  advancePaymentsApi.update.mockResolvedValue({});
  advancePaymentsApi.delete.mockResolvedValue({});
}