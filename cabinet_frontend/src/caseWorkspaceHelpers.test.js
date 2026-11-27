import test from 'node:test';
import assert from 'node:assert/strict';
import { currentTask, latestInspection, ownsStep, taskWaitReason, waitingText } from './caseWorkspaceHelpers.js';

const order = { status: 'FINITION', production_attempt: 2, intake_revision: 3, current_step: { kind: 'WORK', owner_roles: ['FAO'] } };
const task = { id: 'current', workflow_step: 'FINITION', source_status: 'FINITION', production_attempt: 2, intake_revision: 3, generation: 1, status: 'READY', assigned_employee: 1, employee_name: 'Technicien', can_operate: true, dependencies: [] };
test('current work ignores earlier attempts/revisions and cancelled generations', () => {
  assert.equal(currentTask(order, [task, { ...task, generation: 5, status: 'CANCELLED' }, { ...task, generation: 6, production_attempt: 1 }, { ...task, generation: 7, intake_revision: 1 }]), task);
  assert.equal(currentTask(order, []), null);
});
test('inspection evidence is matched to its actual revision or production attempt', () => {
  const inspections = [{ id: 1, stage: 'MODEL', intake_revision: 2, passed: true, created_at: '2026-11-23T10:00Z' }, { id: 2, stage: 'QUALITY', production_attempt: 2, passed: true, created_at: '2026-11-23T10:00Z' }, { id: 3, stage: 'QUALITY', production_attempt: 2, passed: false, created_at: '2026-11-24T10:00Z' }];
  assert.equal(latestInspection(order, { inspections }, 'MODEL'), null);
  assert.equal(latestInspection(order, { inspections }, 'QUALITY').passed, false);
});
test('assignment, dependencies and future slots explain why a task cannot start', () => {
  assert.match(taskWaitReason(order, { ...task, can_operate: false }, []), /Tâche affectée à Technicien/);
  assert.match(taskWaitReason(order, { ...task, dependencies: ['prior'] }, []), /Étape précédente/);
  assert.match(taskWaitReason(order, { ...task, planned_start: '2026-12-01T10:00Z' }, [], Date.parse('2026-11-24T10:00Z')), /démarrage supervisé/);
  assert.match(taskWaitReason(order, { ...task, source_status: 'SALLE_CAO' }, []), /changé d’étape/);
  assert.equal(taskWaitReason(order, task, []), '');
});
test('step ownership stays descriptive and external waits name the responsible actor', () => {
  assert.equal(ownsStep(order, 'CAO'), false); assert.equal(ownsStep(order, 'FAO'), true); assert.equal(ownsStep(order, 'MANAGER'), true);
  assert.match(waitingText({ status: 'VALIDATION_CAO', current_step: { kind: 'CLINIC' } }), /En attente du dentiste/);
  assert.match(waitingText({ status: 'EN_ROUTE_LABO', current_step: { kind: 'CUSTODY' } }), /En attente du coursier/);
});
