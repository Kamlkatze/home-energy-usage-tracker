import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const metersApi = {
  getAll: async () => {
    const response = await apiClient.get('/api/meters/');
    return response.data;
  },
  
  getById: async (id: number) => {
    const response = await apiClient.get(`/api/meters/${id}`);
    return response.data;
  },
  
  create: async (meterData: any) => {
    const response = await apiClient.post('/api/meters/', meterData);
    return response.data;
  },
  
  update: async (id: number, meterData: any) => {
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
};

export const healthApi = {
  check: async () => {
    const response = await apiClient.get('/health');
    return response.data;
  },
};

export default apiClient;