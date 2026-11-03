import axios, { AxiosError } from 'axios';
import { Meter, MeterUpdateData, AdvancePaymentDiffByCategory, ConsumptionTimeseriesItem, MeterType, BackupInfo, BackupRestoreResult, AppMeta, AuthUser, TotpStatus, AdminUser, AdminUserUpdateData, UserRole } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Session-cookie auth: the HttpOnly cookie must travel with requests in
  // the cross-origin dev setup (vite :3000 -> backend :8000). In prod the
  // same-origin nginx /api proxy makes this a no-op.
  withCredentials: true,
});

// Endpoints that may legitimately return 401 without the session being
// broken: the login flow itself (wrong password), the idempotent logout
// and the initial /me check (no session yet). Everything else returning
// 401 means the session expired or was revoked -> notify the app so the
// AuthContext drops the user and the route guard redirects to /login.
const AUTH_EXEMPT_URLS = ['/api/auth/login', '/api/auth/logout', '/api/auth/me'];

export function isAuthExemptUrl(url: string | undefined): boolean {
  if (!url) return false;
  return AUTH_EXEMPT_URLS.some((exempt) => url.startsWith(exempt));
}

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401 && !isAuthExemptUrl(error.config?.url)) {
      window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    }
    return Promise.reject(error);
  },
);

export const authApi = {
  login: async (username: string, password: string, totpCode?: string): Promise<AuthUser> => {
    const payload: Record<string, string> = { username, password };
    if (totpCode) {
      payload.totp_code = totpCode;
    }
    const response = await apiClient.post('/api/auth/login', payload);
    return response.data as AuthUser;
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/api/auth/logout');
  },

  me: async (): Promise<AuthUser> => {
    const response = await apiClient.get('/api/auth/me');
    return response.data as AuthUser;
  },

  changePassword: async (
    currentPassword: string,
    newPassword: string,
    logoutOtherSessions = false,
  ): Promise<void> => {
    await apiClient.post('/api/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
      logout_other_sessions: logoutOtherSessions,
    });
  },

  getTotpStatus: async (): Promise<TotpStatus> => {
    const response = await apiClient.get('/api/auth/totp');
    return response.data as TotpStatus;
  },

  startTotpSetup: async (): Promise<{ secret: string; otpauth_url: string }> => {
    const response = await apiClient.post('/api/auth/totp/setup');
    return response.data as { secret: string; otpauth_url: string };
  },

  enableTotp: async (code: string): Promise<TotpStatus> => {
    const response = await apiClient.post('/api/auth/totp/enable', { code });
    return response.data as TotpStatus;
  },

  disableTotp: async (password: string, code: string): Promise<TotpStatus> => {
    const response = await apiClient.post('/api/auth/totp/disable', {
      password,
      code,
    });
    return response.data as TotpStatus;
  },
};

export const adminApi = {
  listUsers: async (): Promise<AdminUser[]> => {
    const response = await apiClient.get('/api/admin/users');
    return response.data as AdminUser[];
  },

  createUser: async (username: string, password: string, role: UserRole): Promise<AdminUser> => {
    const response = await apiClient.post('/api/admin/users', {
      username,
      password,
      role,
    });
    return response.data as AdminUser;
  },

  updateUser: async (id: number, data: AdminUserUpdateData): Promise<AdminUser> => {
    const response = await apiClient.patch(`/api/admin/users/${id}`, data);
    return response.data as AdminUser;
  },
};

export const metersApi = {
  getTypes: async () => {
    const response = await apiClient.get('/api/meters/types');
    return response.data;
  },

  getAll: async () => {
    const response = await apiClient.get('/api/meters/');
    return response.data;
  },

  getCurrent: async () => {
    const response = await apiClient.get('/api/meters/current');
    return response.data;
  },

  getById: async (id: number) => {
    const response = await apiClient.get(`/api/meters/${id}`);
    return response.data;
  },

  create: async (meterData: any): Promise<Meter> => {
    const response = await apiClient.post('/api/meters/', meterData);
    return response.data;
  },

  update: async (id: number, meterData: MeterUpdateData): Promise<Meter> => {
    const response = await apiClient.put(`/api/meters/${id}`, meterData);
    return response.data;
  },

  delete: async (id: number) => {
    const response = await apiClient.delete(`/api/meters/${id}`);
    return response.data;
  },

  getReadings: async (meterId: number) => {
    const response = await apiClient.get(`/api/meters/${meterId}/readings`);
    return response.data;
  },

  getLastReading: async (meterId: number) => {
    const response = await apiClient.get(`/api/meters/${meterId}/readings`);
    const readings = response.data;
    return readings.length > 0 ? readings[readings.length - 1] : null;
  },
};

export const readingsApi = {
  getAll: async () => {
    const response = await apiClient.get('/api/readings/');
    return response.data;
  },
  
  getById: async (id: number) => {
    const response = await apiClient.get(`/api/readings/${id}`);
    return response.data;
  },
  
  create: async (readingData: any) => {
    const response = await apiClient.post('/api/readings/', readingData);
    return response.data;
  },
  
  update: async (id: number, readingData: any) => {
    const response = await apiClient.put(`/api/readings/${id}`, readingData);
    return response.data;
  },
  
  delete: async (id: number) => {
    const response = await apiClient.delete(`/api/readings/${id}`);
    return response.data;
  },
};

export const tariffsApi = {
  getAll: async () => {
    const response = await apiClient.get('/api/tariffs/');
    return response.data;
  },

  getById: async (id: number) => {
    const response = await apiClient.get(`/api/tariffs/${id}`);
    return response.data;
  },

  create: async (tariffData: any) => {
    const response = await apiClient.post('/api/tariffs/', tariffData);
    return response.data;
  },

  update: async (id: number, tariffData: any) => {
    const response = await apiClient.put(`/api/tariffs/${id}`, tariffData);
    return response.data;
  },

  delete: async (id: number) => {
    const response = await apiClient.delete(`/api/tariffs/${id}`);
    return response.data;
  },

  getUsage: async (id: number) => {
    const response = await apiClient.get(`/api/tariffs/${id}/usage`);
    return response.data;
  },
};

export const costsApi = {
  getYearsOverview: async () => {
    const response = await apiClient.get('/api/costs/years-overview');
    return response.data;
  },

  getYearlyProjection: async (meterId: number, year: number) => {
    const response = await apiClient.get('/api/costs/yearly-projection', {
      params: { meter_id: meterId, year },
    });
    return response.data;
  },

  getWastewaterCosts: async (
    waterColdMeterId: number,
    from: string,
    to: string,
    waterGardenMeterId?: number,
  ) => {
    const params: Record<string, string | number> = {
      water_cold_meter_id: waterColdMeterId,
      from,
      to,
    };
    if (waterGardenMeterId !== undefined) {
      params.water_garden_meter_id = waterGardenMeterId;
    }
    const response = await apiClient.get('/api/costs/wastewater/', { params });
    return response.data;
  },

  getAdvancePaymentDiffByCategory: async (
    category: 'gas' | 'cold_water' | 'wastewater' | 'power_import',
    year: number,
    meterId?: number,
    waterColdMeterId?: number,
    waterGardenMeterId?: number,
    asOfDate?: string,
  ): Promise<AdvancePaymentDiffByCategory | null> => {
    const params: Record<string, string | number | undefined> = {
      category,
      year,
    };
    if (category === 'wastewater') {
      if (waterColdMeterId !== undefined) {
        params.water_cold_meter_id = waterColdMeterId;
      }
      if (waterGardenMeterId !== undefined) {
        params.water_garden_meter_id = waterGardenMeterId;
      }
    } else {
      if (meterId !== undefined) {
        params.meter_id = meterId;
      }
    }
    if (asOfDate !== undefined) {
      params.as_of_date = asOfDate;
    }
    try {
      const response = await apiClient.get('/api/costs/advance-payment-diff-by-category', { params });
      return response.data;
    } catch (error) {
      if (error instanceof AxiosError && error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  },

  getConsumptionTimeseries: async (
    from: string,
    to: string,
    meterType?: MeterType,
  ): Promise<ConsumptionTimeseriesItem[]> => {
    const params: Record<string, string> = { from, to };
    if (meterType !== undefined) {
      params.meter_type = meterType;
    }
    const response = await apiClient.get('/api/costs/consumption-timeseries', { params });
    return response.data;
  },
};

export const electricityApi = {
  getFeedInCompensation: async (
    productionMeterId: number,
    exportMeterId: number,
    from: string,
    to: string,
  ) => {
    const response = await apiClient.get('/api/electricity/feed-in-compensation', {
      params: {
        production_meter_id: productionMeterId,
        export_meter_id: exportMeterId,
        from,
        to,
      },
    });
    return response.data;
  },
  getFeedInCompensationProjection: async (
    productionMeterId: number,
    exportMeterId: number,
    year: number,
  ) => {
    const response = await apiClient.get('/api/electricity/feed-in-compensation-projection', {
      params: {
        production_meter_id: productionMeterId,
        export_meter_id: exportMeterId,
        year,
      },
    });
    return response.data;
  },
};

export const metaApi = {
  getMeta: async (): Promise<AppMeta> => {
    const response = await apiClient.get('/api/meta');
    return response.data;
  },
};

export const backupApi = {
  getInfo: async (): Promise<BackupInfo> => {
    const response = await apiClient.get('/api/backup/info');
    return response.data;
  },

  downloadDump: async (): Promise<{ blob: Blob; filename: string }> => {
    const response = await apiClient.get('/api/backup/dump', {
      responseType: 'blob',
      timeout: 300000,
    });
    const disposition = String(response.headers['content-disposition'] ?? '');
    const match = /filename="?([^";]+)"?/i.exec(disposition);
    return {
      blob: response.data as Blob,
      filename: match ? match[1] : 'energy_data_backup.sql',
    };
  },

  restore: async (file: File): Promise<BackupRestoreResult> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('confirm', 'true');
    const response = await apiClient.post('/api/backup/restore', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    });
    return response.data;
  },
};

export default apiClient;