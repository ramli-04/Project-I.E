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
  const flatten = value => typeof value === 'string' ? value : Array.isArray(value)
    ? value.map(flatten).join(' ') : value && typeof value === 'object'
      ? Object.entries(value).map(([key, val]) => `${key}: ${flatten(val)}`).join(' ') : String(value ?? '');
  return (error.response?.data ? flatten(error.response.data) : '') || error.message || 'Connexion impossible.';
}

export const money = value => value == null ? 'Devis laboratoire requis' : `${Number(value).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MAD`;
export const quantityText = value => value == null || value === '' ? '—' : Number(value).toLocaleString('fr-FR', { maximumFractionDigits: 2 });
export const acceptsQuantity = value => /^\d*(?:[.,]\d{0,2})?$/.test(value);
// Existing precise server values remain untouched until the user edits them.
export const quantityInput = value => value == null || value === '' ? '' : acceptsQuantity(String(value)) ? String(value).replace(',', '.') : String(Number(Number(value).toFixed(2)));
export const completed = status => ['LIVRE', 'ESSAYAGE', 'CLOTURE'].includes(status);
export function workstation() {
  try { return JSON.parse(sessionStorage.getItem('demo_user') || '{}').workstation_role || ''; } catch { return ''; }
}

export function retryableRequest() {
  let previous;
  return async (client, path, payload, config = {}) => {
    const fingerprint = JSON.stringify([path, payload]);
    if (previous?.fingerprint !== fingerprint) previous = { fingerprint, key: crypto.randomUUID() };
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
