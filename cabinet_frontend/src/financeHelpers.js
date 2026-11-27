import { sumAmounts } from './api/contracts.js';

const statusLabels = { IMPAYEE: 'Facturée · impayée', PARTIELLE: 'Facturée · partiellement payée', PAYEE: 'Payée', TROP_PERCU: 'Payée · trop-perçu à régulariser' };

export function currentLabMonth(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit' }).formatToParts(now);
  return `${parts.find(p => p.type === 'year').value}-${parts.find(p => p.type === 'month').value}`;
}

export function workSummary(items = []) {
  return items.map(item => `Dent ${item.tooth_number} · ${item.function} · ${item.material} · ${item.shade}`).join(' ; ') || '—';
}

// One row per delivered case, from immutable statement snapshots plus period/invoice status.
export function deliveredRows({ lines = [], periods = [], invoices = [], clinics = [] }) {
  return lines.map(line => {
    const period = periods.find(p => p.id === line.period) || {};
    const invoice = period.closed_at ? invoices.find(inv => inv.period === period.id) : null;
    const snapshot = line.snapshot || {};
    const status = line.excluded ? 'Exclue' : line.contested ? 'Contestée'
      : invoice ? (statusLabels[invoice.payment_status] || 'Facturée') : period.closed_at ? 'Facturée' : 'Dans le relevé';
    return {
      id: line.id, caseId: snapshot.case_id || line.prescription, patient_ref: snapshot.patient_ref, patientRef: snapshot.patient_ref || line.prescription,
      clinicId: period.clinic, clinicName: clinics.find(c => c.id === period.clinic)?.name || '—',
      month: String(period.month || '').slice(0, 7), delivered: snapshot.delivered_at,
      deliveredLabel: snapshot.delivered_at ? new Date(snapshot.delivered_at).toLocaleDateString('fr-FR', { timeZone: 'Africa/Casablanca' }) : 'Non renseignée',
      work: workSummary(snapshot.items), service: snapshot.delivery_service,
      amount: sumAmounts([line.base_amount, line.express_surcharge]), excluded: line.excluded, statusLabel: status,
      // Fields used by the presentation test-case filter.
      status: 'CLOTURE', updated_at: snapshot.delivered_at,
    };
  }).sort((a, b) => String(b.delivered || '').localeCompare(String(a.delivered || '')));
}
