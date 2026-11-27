import test from 'node:test';
import assert from 'node:assert/strict';
import { currentLabMonth, deliveredRows, workSummary } from './financeHelpers.js';

test('the current month follows Africa/Casablanca, not UTC', () => {
  assert.equal(currentLabMonth(new Date('2026-11-30T23:30:00Z')), '2026-12');
  assert.equal(currentLabMonth(new Date('2026-11-30T22:30:00Z')), '2026-11');
});

test('delivered rows carry work, exact amounts and accounting status', () => {
  const data = {
    clinics: [{ id: 1, name: 'Cabinet A' }],
    periods: [{ id: 'p-open', clinic: 1, month: '2026-11-01', closed_at: null }, { id: 'p-closed', clinic: 1, month: '2026-10-01', closed_at: '2026-11-01T00:00:00Z' }],
    invoices: [{ id: 'inv', period: 'p-closed', payment_status: 'PARTIELLE' }],
    lines: [
      { id: 'l1', period: 'p-open', base_amount: '1500.00', express_surcharge: '450.00', contested: false, excluded: false, snapshot: { case_id: 'c1', patient_ref: 'REF-1', delivery_service: 'EXPRESS', delivered_at: '2026-11-21T20:11:19Z', items: [{ tooth_number: 11, function: 'Couronne', form: 'Anatomique', material: 'E-Max', shade: 'A1' }] } },
      { id: 'l2', period: 'p-open', base_amount: '300.00', express_surcharge: '0.00', contested: true, excluded: false, snapshot: { case_id: 'c2', patient_ref: 'REF-2', delivered_at: '2026-11-22T10:00:00Z', items: [] } },
      { id: 'l3', period: 'p-closed', base_amount: '100.00', express_surcharge: '0.00', contested: false, excluded: false, snapshot: { case_id: 'c3', patient_ref: 'REF-3', delivered_at: '2026-10-10T10:00:00Z', items: [] } },
    ],
  };
  const rows = deliveredRows(data);
  assert.deepEqual(rows.map(row => row.patientRef), ['REF-2', 'REF-1', 'REF-3']);
  const first = rows.find(row => row.id === 'l1');
  assert.equal(first.amount, '1950.00'); assert.equal(first.statusLabel, 'Dans le relevé'); assert.equal(first.clinicName, 'Cabinet A');
  assert.equal(first.work, 'Dent 11 · Couronne · E-Max · A1'); assert.equal(first.month, '2026-11');
  assert.equal(rows.find(row => row.id === 'l2').statusLabel, 'Contestée');
  assert.equal(rows.find(row => row.id === 'l3').statusLabel, 'Facturée · partiellement payée');
  assert.equal(workSummary([]), '—');
});
