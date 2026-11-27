import test from 'node:test';
import assert from 'node:assert/strict';
import { ARCHIVE_NOTE, isAutomatedTestCase, splitTestCases, TEST_PAUSE_NOTE } from './testCases.js';

const now = Date.parse('2026-11-27T12:00:00Z');
const sim = { now, simulation: true };

test('only paused-with-note or long-closed BROWSER cases are hidden, and only in simulation', () => {
  const paused = { patient_ref: 'BROWSER-1', status: 'SALLE_CAO', is_paused: true, pause_reason: TEST_PAUSE_NOTE };
  const oldClosed = { patient_ref: 'BROWSER-2', status: 'CLOTURE', updated_at: '2026-11-20T10:00:00Z' };
  const fresh = { patient_ref: 'BROWSER-3', status: 'SALLE_CAO', is_paused: false, updated_at: '2026-11-27T11:00:00Z' };
  const freshClosed = { patient_ref: 'BROWSER-4', status: 'CLOTURE', updated_at: '2026-11-27T11:00:00Z' };
  const otherPause = { patient_ref: 'BROWSER-5', status: 'SALLE_CAO', is_paused: true, pause_reason: 'Matière indisponible' };
  assert.equal(isAutomatedTestCase(paused, sim), true);
  assert.equal(isAutomatedTestCase(oldClosed, sim), true);
  assert.equal(isAutomatedTestCase(fresh, sim), false);
  assert.equal(isAutomatedTestCase(freshClosed, sim), false);
  assert.equal(isAutomatedTestCase(otherPause, sim), false);
  assert.equal(isAutomatedTestCase(paused, { now, simulation: false }), false);
  for (const reference of ['MY-TEST-001', 'TEST-2611-01', 'V1-RETARD-1'])
    assert.equal(isAutomatedTestCase({ ...paused, patient_ref: reference }, sim), false);
  const archived = { patient_ref: 'DEMO-PRINT-STANDARD', status: 'PREPARATION_3D', is_paused: true, pause_reason: ARCHIVE_NOTE };
  assert.equal(isAutomatedTestCase(archived, sim), true);
  assert.equal(isAutomatedTestCase({ ...archived, is_paused: false }, sim), false);
  assert.equal(isAutomatedTestCase(archived, { now, simulation: false }), false);
});

test('the toggle restores every row and reports the hidden count', () => {
  const rows = [{ patient_ref: 'BROWSER-1', status: 'CLOTURE', updated_at: '2026-11-01T00:00:00Z' }, { patient_ref: 'DEMO-1', status: 'SALLE_CAO' }];
  assert.deepEqual(splitTestCases(rows, false, sim), { visible: [rows[1]], hiddenCount: 1 });
  assert.deepEqual(splitTestCases(rows, true, sim), { visible: rows, hiddenCount: 1 });
});
