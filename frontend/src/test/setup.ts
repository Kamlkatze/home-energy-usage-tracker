import '@testing-library/jest-dom/vitest';
import { beforeEach, vi } from 'vitest';

// Recharts' ResponsiveContainer needs ResizeObserver, which jsdom does not
// provide. Satisfy it with a no-op mock so charts can render in tests.
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof ResizeObserver;

// Mock the API client modules globally so no route component ever triggers a
// real network request during tests. The factories use a lazy dynamic import
// so the mock functions are shared with the imported reset helper.
vi.mock('../api/client', async () => {
  const api = await import('./mocks/api');
  return {
    metersApi: api.metersApi,
    readingsApi: api.readingsApi,
    tariffsApi: api.tariffsApi,
    costsApi: api.costsApi,
    electricityApi: api.electricityApi,
    backupApi: api.backupApi,
    default: {},
  };
});

vi.mock('../api/advancePaymentsApi', async () => {
  const api = await import('./mocks/api');
  return {
    advancePaymentsApi: api.advancePaymentsApi,
    default: {},
  };
});

import { resetApiMocks } from './mocks/api';

// Restore default mock implementations before every test for isolation.
beforeEach(() => {
  resetApiMocks();
  vi.clearAllMocks();
});