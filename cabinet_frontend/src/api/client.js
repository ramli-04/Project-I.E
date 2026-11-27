import axios from "axios";
import { previewAdapter, previewMode } from './preview';
import { installFeedback } from '../notifications';

const api = axios.create(previewMode ? { adapter: previewAdapter } : {});
const tenantIdPattern = /^[a-z0-9][a-z0-9-]*$/;

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('demo_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  const tenantId = sessionStorage.getItem("tenant_id");
  if (!tenantId || !tenantIdPattern.test(tenantId)) {
    throw new Error("Sélectionnez un laboratoire valide avant de continuer.");
  }

  const apiOrigin = new URL(import.meta.env.VITE_API_ORIGIN || "http://localhost:8000");
  apiOrigin.hostname =
    apiOrigin.hostname === "localhost" || apiOrigin.hostname === "127.0.0.1"
      ? `${tenantId}.localhost`
      : `${tenantId}.${apiOrigin.hostname}`;

  config.baseURL = new URL("/api/", apiOrigin).toString();
  return config;
});

export default api;
installFeedback(api);
api.interceptors.response.use(response => response, error => {
  if (error.response?.status === 401) {
    sessionStorage.removeItem('demo_token'); sessionStorage.removeItem('demo_user');
    window.dispatchEvent(new Event('cabinet-session-expired'));
  }
  return Promise.reject(error);
});
