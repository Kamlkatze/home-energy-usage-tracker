import axios, { AxiosError } from 'axios';
import { Meter, MeterUpdateData, AdvancePaymentDiffByCategory } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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

export default apiClient;