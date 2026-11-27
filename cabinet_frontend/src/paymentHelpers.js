export function cents(value) {
  const text = String(value ?? '').trim().replace(',', '.');
  if (!/^\d+(?:\.\d{0,2})?$/.test(text)) throw new Error('Renseignez un montant positif avec au plus deux décimales.');
  const [whole, fraction = ''] = text.split('.');
  return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
}
export function decimal(value) {
  const sign = value < 0n ? '-' : ''; const absolute = value < 0n ? -value : value;
  return `${sign}${absolute / 100n}.${String(absolute % 100n).padStart(2, '0')}`;
}
export function allocateOldest(amount, invoices) {
  if (amount === '') return {};
  let remaining = cents(amount); const result = {};
  for (const invoice of [...invoices].sort((a, b) => `${a.due_date}:${a.issued_at}:${a.id}`.localeCompare(`${b.due_date}:${b.issued_at}:${b.id}`))) {
    if (String(invoice.balance).startsWith('-')) continue;
    const available = cents(invoice.balance);
    const allocated = remaining < available ? remaining : available;
    if (allocated > 0n) result[invoice.id] = decimal(allocated);
    remaining -= allocated;
  }
  return result;
}
export const allocationTotal = allocations => Object.values(allocations).reduce((sum, value) => sum + (value === '' ? 0n : cents(value)), 0n);
export const paymentStatusLabel = status => ({ PAYEE: 'Payée', PARTIELLE: 'Partiellement payée', IMPAYEE: 'Impayée', TROP_PERCU: 'Trop-perçu à régulariser' })[status] || 'Solde à actualiser';
export const paymentMethodLabel = method => ({ CHEQUE: 'Chèque', LCN: 'LCN', VIREMENT: 'Virement', ESPECES: 'Espèces' })[method] || method;
export const agingLabel = bucket => ({ '0_30': '0–30 jours', '31_60': '31–60 jours', '61_90': '61–90 jours', '90_plus': 'Plus de 90 jours' })[bucket];
