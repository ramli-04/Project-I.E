import test from 'node:test';
import assert from 'node:assert/strict';
import { cents, decimal, allocateOldest, allocationTotal, paymentStatusLabel, agingLabel } from './paymentHelpers.js';

test('payment amounts retain exact cents, including the API maximum', () => {
  assert.equal(cents('99999999999999.99'), 9999999999999999n);
  assert.equal(decimal(cents('0,01')), '0.01');
  assert.equal(decimal(-10001n), '-100.01');
  for (const amount of ['NaN', '-1', '1.001', '1e3', '']) assert.throws(() => cents(amount));
});
test('allocation is oldest first and never spends a negative or paid balance', () => {
  const invoices = [
    { id: 'new', due_date: '2026-12-10', issued_at: '2026-11-10', balance: '100.00' },
    { id: 'old', due_date: '2026-12-01', issued_at: '2026-11-01', balance: '60.00' },
    { id: 'credit', due_date: '2026-11-01', issued_at: '2026-10-01', balance: '-10.00' },
    { id: 'paid', due_date: '2026-11-01', issued_at: '2026-10-01', balance: '0.00' },
  ];
  assert.deepEqual(allocateOldest('100', invoices), { old: '60.00', new: '40.00' });
  assert.equal(allocationTotal({ old: '60.00', new: '40.00' }), cents('100'));
  assert.deepEqual(allocateOldest('200', invoices), { old: '60.00', new: '100.00' });
  assert.deepEqual(allocateOldest('', invoices), {});
});
test('payment statuses and all aging boundary labels remain French', () => {
  assert.equal(paymentStatusLabel('TROP_PERCU'), 'Trop-perçu à régulariser');
  assert.equal(paymentStatusLabel('PARTIELLE'), 'Partiellement payée');
  assert.deepEqual(['0_30', '31_60', '61_90', '90_plus'].map(agingLabel), ['0–30 jours', '31–60 jours', '61–90 jours', 'Plus de 90 jours']);
});
