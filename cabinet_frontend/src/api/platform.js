import axios from 'axios';

const origin = new URL(import.meta.env.VITE_API_ORIGIN || 'http://localhost:8000');
const platform = axios.create({ baseURL: new URL('/platform/', origin).toString() });
platform.interceptors.request.use(config => {
  const token = sessionStorage.getItem('demo_token');
  if (token && config.url !== 'login/' && !(config.url === 'laboratories/' && (!config.method || config.method === 'get'))) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
export default platform;
platform.interceptors.response.use(response => response, error => {
  if (error.response?.status === 401 && error.config?.url !== 'login/') {
    sessionStorage.removeItem('demo_token'); sessionStorage.removeItem('demo_user');
    window.dispatchEvent(new Event('cabinet-session-expired'));
  }
  return Promise.reject(error);
});
