import apiClient from './client';

export const advancePaymentsApi = {
  getAll: async (params?: { meter_id?: number; category?: string }) => {
    const response = await apiClient.get('/api/advance-payments/', { params });
    return response.data;
  },

  getById: async (id: number) => {
    const response = await apiClient.get(`/api/advance-payments/${id}`);
    return response.data;
  },

  create: async (payload: Record<string, unknown>) => {
    const response = await apiClient.post('/api/advance-payments/', payload);
    return response.data;
  },

  update: async (id: number, payload: Record<string, unknown>) => {
    const response = await apiClient.put(`/api/advance-payments/${id}`, payload);
    return response.data;
  },

  delete: async (id: number) => {
    const response = await apiClient.delete(`/api/advance-payments/${id}`);
    return response.data;
  },
};