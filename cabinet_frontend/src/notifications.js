import { errorMessage, frenchMessage } from './api/messages';

let current = null;
let sequence = 0;
const listeners = new Set();
export const subscribe = listener => { listeners.add(listener); return () => listeners.delete(listener); };
export const snapshot = () => current;
export function notify(message, type = 'success') {
  const translated = type === 'error' ? frenchMessage(message) : message;
  const at = Date.now();
  if (current?.message === translated && current.type === type && at - current.at < 300) return;
  current = { id: ++sequence, message: translated, type, at };
  listeners.forEach(listener => listener());
}
export function dismissNotification(id) {
  if (current?.id !== id) return;
  current = null;
  listeners.forEach(listener => listener());
}
export function installFeedback(client) {
  client.interceptors.response.use(response => {
    // Signing in or out is not a recorded business action: no "Action enregistrée." toast.
    const authentication = /(^|\/)(login|logout)\/?$/.test(String(response.config?.url || ''));
    if (['post', 'put', 'patch', 'delete'].includes(response.config?.method) && response.config?.feedback !== false && !authentication)
      notify('Action enregistrée.');
    return response;
  }, error => {
    if (error.code !== 'ERR_CANCELED' && error.config?.feedback !== false && error.config?.responseType !== 'blob')
      notify(errorMessage(error), 'error');
    return Promise.reject(error);
  });
}
