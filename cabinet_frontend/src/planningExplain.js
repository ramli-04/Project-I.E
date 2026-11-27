// Plain-French reading of the planner's stored assignment_explanation (no new computation).
export function explainAssignment(task) {
  const explanation = task?.assignment_explanation || {};
  if (explanation.reason) return explanation.reason;
  const c = explanation.components;
  if (!c) return task?.assignment_mode === 'MANUAL' ? 'Affectation choisie manuellement par le responsable.' : '';
  const parts = [];
  if (typeof c.qualification === 'number') parts.push(`qualification ${Math.max(1, Math.round(c.qualification * 5))}/5`);
  if (typeof c.workload === 'number') parts.push(`charge déjà planifiée ${Math.round((1 - c.workload) * 100)} % de sa capacité`);
  if (typeof c.availability === 'number') parts.push(c.availability >= 0.99 ? 'disponible au plus tôt' : 'premier créneau compatible');
  if (c.continuity) parts.push('même personne qu’à l’étape précédente');
  return parts.length ? `Choix du planning : ${parts.join(' · ')}.` : '';
}
