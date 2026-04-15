import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('laboral_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401) {
      localStorage.removeItem('laboral_token');
      localStorage.removeItem('laboral_user');
      window.location.reload();
      return Promise.reject(error);
    }
    if (
      [502, 503, 504].includes(error.response?.status) &&
      !originalRequest._retry &&
      ['get', 'head'].includes(originalRequest.method)
    ) {
      originalRequest._retry = true;
      await new Promise((r) => setTimeout(r, 1000));
      return api(originalRequest);
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: (data: { username: string; password: string }) =>
    api.post('/api/auth/login', data),
  me: () => api.get('/api/auth/me'),
  register: (data: Record<string, unknown>) =>
    api.post('/api/auth/register', data),
};

export const employeesAPI = {
  list: (params?: Record<string, unknown>) =>
    api.get('/api/employees', { params }),
  get: (id: number) => api.get(`/api/employees/${id}`),
  create: (data: Record<string, unknown>) =>
    api.post('/api/employees', data),
  update: (id: number, data: Record<string, unknown>) =>
    api.put(`/api/employees/${id}`, data),
  deactivate: (id: number) => api.delete(`/api/employees/${id}`),
};

export const simulationAPI = {
  run: (data: Record<string, unknown>) => api.post('/api/simulate', data),
};

export const referenceAPI = {
  categories: () => api.get('/api/reference/categories'),
  contractTypes: () => api.get('/api/reference/contract-types'),
  regions: () => api.get('/api/reference/regions'),
  tiposDespido: () => api.get('/api/reference/tipos-despido'),
};

export const chatAPI = {
  send: (data: { message: string; convenio_id?: string }) =>
    api.post('/api/chat', data),
};

export const payrollAPI = {
  generate: (data: Record<string, unknown>) => api.post('/api/nomina', data),
  bulk: (data: Record<string, unknown>) => api.post('/api/nomina/bulk', data),
  get: (employeeId: number, periodo: string) =>
    api.get(`/api/nomina/${employeeId}/${periodo}`),
};

export const dismissalAPI = {
  calculate: (data: Record<string, unknown>) => api.post('/api/despido', data),
};

export const conveniosAPI = {
  list: () => api.get('/api/convenios'),
  get: (id: string) => api.get(`/api/convenios/${id}`),
};

export const alertsAPI = {
  list: (params?: Record<string, unknown>) =>
    api.get('/api/alerts', { params }),
  create: (data: Record<string, unknown>) => api.post('/api/alerts', data),
  dismiss: (id: number) => api.put(`/api/alerts/${id}/dismiss`),
};

export const consultationsAPI = {
  list: (params?: Record<string, unknown>) =>
    api.get('/api/consultations', { params }),
};

export const healthAPI = {
  check: () => api.get('/api/health'),
};

export default api;
