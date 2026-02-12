import axios from 'axios';

const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL, timeout: 15000 });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    if (err.response?.status === 401 && localStorage.getItem('refresh_token')) {
      const refresh = await axios.post(`${import.meta.env.VITE_API_BASE_URL}/api/v1/auth/refresh`, {
        refresh_token: localStorage.getItem('refresh_token'),
        device_fingerprint: localStorage.getItem('device_fingerprint') || 'web-client',
      });
      localStorage.setItem('access_token', refresh.data.access_token);
      localStorage.setItem('refresh_token', refresh.data.refresh_token);
      err.config.headers.Authorization = `Bearer ${refresh.data.access_token}`;
      return api.request(err.config);
    }
    return Promise.reject(err);
  }
);

export const AuthAPI = {
  register: (email: string, password: string) => api.post('/api/v1/auth/register', { email, password }),
  login: (email: string, password: string, device_fingerprint: string) =>
    api.post('/api/v1/auth/login', { email, password, device_fingerprint }),
  verify2FA: (code: string) => api.post('/api/v1/auth/2fa/verify', { code }),
};

export const TradingAPI = {
  testMT5: (payload: any) => api.post('/api/v1/mt5/test', payload),
  connectMT5: (payload: any) => api.post('/api/v1/mt5/connect', payload),
  switchAccount: (accountId: string) => api.post('/api/v1/mt5/switch', { account_id: accountId }),
  getAccounts: () => api.get('/api/v1/mt5/accounts'),
  getPositions: () => api.get('/api/v1/trades/positions'),
  closePosition: (id: string) => api.post(`/api/v1/trades/positions/${id}/close`),
  getStrategyPerformance: () => api.get('/api/v1/strategies/performance'),
  getModels: () => api.get('/api/v1/models'),
  promoteModel: (id: string, stage: 'staging' | 'production') => api.post(`/api/v1/models/${id}/promote`, { stage }),
  rollbackModel: (name: string) => api.post(`/api/v1/models/${name}/rollback`),
  runBacktest: (payload: any) => api.post('/api/v1/backtests/run', payload),
  getCalendar: (params: any) => api.get('/api/v1/calendar/events', { params }),
};

export default api;
