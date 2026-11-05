import test from 'node:test';
import assert from 'node:assert/strict';
import { addDays, addMonths, configurePlanningTime, labDate, labInput, labISO } from './planningTime.js';

test('planning timestamps use Casablanca independently of the browser/host zone',()=>{
  assert.equal(labISO('2026-11-09T08:00'),'2026-11-09T07:00:00.000Z');
  assert.equal(labInput('2026-11-09T07:00:00Z'),'2026-11-09T08:00');
  assert.equal(labDate('2026-11-08T23:30:00Z'),'2026-11-09');
});
test('planning date navigation handles month boundaries',()=>{
  assert.equal(addDays('2026-11-30',1),'2026-12-01');
  assert.equal(addDays('2026-01-01',-1),'2025-12-31');
  assert.equal(addMonths('2026-03-31',-1),'2026-02-01');
  assert.equal(addMonths('2026-12-31',1),'2027-01-01');
});
test('scheduler timezone rules take precedence over browser tzdata',()=>{
  configurePlanningTime({zone:'Africa/Casablanca',until:'2027-01-01T00:00:00Z',transitions:[{at:'2026-01-01T00:00:00Z',offset:120}]});
  try {
    assert.equal(labInput('2026-11-09T07:00:00Z'),'2026-11-09T09:00');
    assert.equal(labISO('2026-11-09T09:00'),'2026-11-09T07:00:00.000Z');
  } finally {configurePlanningTime(null);}
});
