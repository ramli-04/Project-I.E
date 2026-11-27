import test from 'node:test';
import assert from 'node:assert/strict';
import { explainAssignment } from './planningExplain.js';

test('stored planner components become one plain French sentence', () => {
  const task = { assignment_explanation: { components: { qualification: 0.8, workload: 0.75, availability: 1, urgency: 0.33, continuity: 1 } } };
  assert.equal(explainAssignment(task), 'Choix du planning : qualification 4/5 · charge déjà planifiée 25 % de sa capacité · disponible au plus tôt · même personne qu’à l’étape précédente.');
});

test('blocked reasons, manual choices and missing data stay explicit', () => {
  assert.equal(explainAssignment({ assignment_explanation: { reason: 'Aucun créneau compatible.' } }), 'Aucun créneau compatible.');
  assert.equal(explainAssignment({ assignment_mode: 'MANUAL', assignment_explanation: {} }), 'Affectation choisie manuellement par le responsable.');
  assert.equal(explainAssignment({}), '');
});
