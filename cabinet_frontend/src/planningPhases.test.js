import test from 'node:test';
import assert from 'node:assert/strict';
import { employeeReservations } from './planningPhases.js';
import { labISO } from './planningTime.js';

const task={id:'job',title:'CNC',resource_phase:'PLANNED',setup_minutes:10,unload_minutes:10,
  planned_start:labISO('2026-11-09T08:00'),planned_end:labISO('2026-11-09T09:00')};

test('employee calendar releases unattended interval and preserves original task identity',()=>{
  const rows=employeeReservations(task,'2026-11-09','2026-11-10');
  assert.equal(rows.length,2);
  assert.equal((Date.parse(rows[0].planned_end)-Date.parse(rows[0].planned_start))/60000,10);
  assert.equal((Date.parse(rows[1].planned_end)-Date.parse(rows[1].planned_start))/60000,10);
  assert.equal(rows[0].original_task,task);
  assert.notEqual(rows[0].id,rows[1].id);
  for (const phase of ['CYCLE','AWAITING_UNLOAD','FINISHED']) {
    assert.deepEqual(employeeReservations({...task,resource_phase:phase},'2026-11-09','2026-11-10'),[]);
  }
});

test('ongoing attended phase remains occupied beyond the estimated job end',()=>{
  const rows=employeeReservations({...task,resource_phase:'UNLOADING',phase_started_at:labISO('2026-11-09T10:00')},'2026-11-09','2026-11-10');
  assert.equal(rows.length,1);
  assert.ok(Date.parse(rows[0].planned_end)>Date.parse(task.planned_end));
});
