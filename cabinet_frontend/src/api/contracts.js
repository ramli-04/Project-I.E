import { errorMessage } from './messages.js';
import { cents, decimal } from '../paymentHelpers.js';

export function rowsOf(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.results)) return data.results;
  throw new Error('Réponse du serveur inattendue.');
}

// Keep the original endpoint and credentials; only consume the next page number.
export async function allRows(client, path, params = {}, signal) {
  const rows = []; const visited = new Set();
  let page = 1;
  while (page) {
    if (visited.has(page)) throw new Error('Pagination invalide.');
    visited.add(page);
    const { data } = await client.get(path, { params: { ...params, page }, signal });
    rows.push(...rowsOf(data));
    if (Array.isArray(data) || !data.next) break;
    const next = Number(new URL(data.next, 'http://pagination.local').searchParams.get('page'));
    if (!Number.isInteger(next) || next <= page) throw new Error('Pagination invalide.');
    page = next;
  }
  return rows;
}

export function errorText(error) {
  return errorMessage(error);
}

const moneyFormat = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export function money(value) {
  if (value == null) return 'Devis laboratoire requis';
  if (typeof value === 'number') return Number.isFinite(value) ? moneyFormat.format(value) + ' MAD' : 'Montant indisponible';
  const match = String(value).trim().match(/^([+-]?)(\d+)(?:\.(\d*))?$/);
  if (!match) return String(value).trim() === '' ? '0,00 MAD' : 'Montant indisponible';
  const fraction = match[3] || '';
  let amount = BigInt(match[2]) * 100n + BigInt(fraction.slice(0, 2).padEnd(2, '0'));
  if (fraction[2] >= '5') amount += 1n;
  const result = moneyFormat.formatToParts(amount / 100n).map(part => part.type === 'fraction'
    ? String(amount % 100n).padStart(2, '0') : part.value).join('');
  return (match[1] === '-' ? '-' : '') + result + ' MAD';
}
export function sumAmounts(values) {
  return decimal(values.reduce((total, value) => {
    const text = String(value ?? 0).trim() || '0';
    return total + (text.startsWith('-') ? -cents(text.slice(1)) : cents(text));
  }, 0n));
}
export const quantityText = value => value == null || value === '' ? '—' : Number(value).toLocaleString('fr-FR', { maximumFractionDigits: 2 });
export const acceptsQuantity = value => /^\d*(?:[.,]\d{0,2})?$/.test(value);
// Existing precise server values remain untouched until the user edits them.
export const quantityInput = value => value == null || value === '' ? '' : acceptsQuantity(String(value)) ? String(value).replace(',', '.') : String(Number(Number(value).toFixed(2)));
export const completed = status => ['LIVRE', 'ESSAYAGE', 'CLOTURE'].includes(status);
export function workstation() {
  try { return JSON.parse(sessionStorage.getItem('demo_user') || '{}').workstation_role || ''; } catch { return ''; }
}

export function retryableRequest({ idempotencyKey } = {}) {
  let previous;
  return async (client, path, payload, config = {}) => {
    const fingerprint = JSON.stringify([path, payload]);
    if (previous?.fingerprint !== fingerprint) previous = { fingerprint, key: idempotencyKey || crypto.randomUUID() };
    try {
      const response = await client.post(path, payload, { ...config, headers: { ...config.headers, 'Idempotency-Key': previous.key } });
      previous = undefined;
      return response;
    } catch (error) {
      // A rejected PIN attempt is recorded by the server; a new attempt needs a new key.
      if (error.response && error.response.status < 500) previous = undefined;
      throw error;
    }
  };
}

export async function download(client, path, filename) {
  let response;
  try { response = await client.get(path, { responseType: 'blob' }); }
  catch (error) {
    if (error.response?.data instanceof Blob) {
      try { error.response.data = JSON.parse(await error.response.data.text()); } catch { /* Keep the transport error. */ }
    }
    throw error;
  }
  if (response.status === 202) throw new Error('Document en préparation. Réessayez après traitement.');
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename;
  anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
