import test from 'node:test';
import assert from 'node:assert/strict';
import { dentistAction, groupQueue, riskLabels, serviceLabels } from './workQueueHelpers.js';

test('queue groups retain server risk order and French labels', () => {
  const groups = groupQueue([{ id: 1, group: 'WAITING' }, { id: 2, group: 'TODO' }, { id: 3, group: 'TODO' }]);
  assert.deepEqual(groups.map(group => group.rows.map(row => row.id)), [[2, 3], [1], [], []]);
  assert.equal(groups[2].label, 'En pause');
  assert.equal(riskLabels.LATE, 'En retard');
  assert.equal(serviceLabels.NEXT_DAY, 'Urgent J+1');
});
test('dentist actions require clinical ownership except the delivery PIN handoff', () => {
  for (const status of ['VALIDATION_CAO', 'LIVRE', 'ESSAYAGE', 'RETOUR_DEMANDE']) {
    assert.ok(dentistAction({ status, current_step: { kind: 'CLINIC' } }));
    assert.equal(dentistAction({ status, current_step: { kind: 'WORK' } }), null);
  }
  assert.equal(dentistAction({ status: 'EN_ROUTE_CABINET', current_step: { kind: 'CUSTODY' } }).focus, 'delivery');
  assert.equal(dentistAction({ status: 'CLOTURE', current_step: { kind: 'DONE' } }), null);
  assert.equal(dentistAction({ status: 'VALIDATION_CAO' }), null);
});
