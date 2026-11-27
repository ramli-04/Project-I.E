export const queueGroups = [['TODO', 'À faire'], ['WAITING', 'En attente'], ['PAUSED', 'En pause'], ['TEAM', 'Travail de l’équipe']];
export const riskLabels = { LATE: 'En retard', AT_RISK: 'À risque', ON_TRACK: 'Dans les délais' };
export const roleLabels = { RECEPTION: 'Réception', CAO: 'Conception CAO', FAO: 'Fabrication', QUALITE: 'Qualité', COMPTABILITE: 'Comptabilité' };
export const serviceLabels = { NEXT_DAY: 'Urgent J+1', EXPRESS: 'Express J+2', STANDARD: 'Standard J+4' };
export function groupQueue(rows) {
  return queueGroups.map(([key, label]) => ({ key, label, rows: rows.filter(row => row.group === key) }));
}
export function dentistAction(order) {
  if (order.status === 'EN_ROUTE_CABINET') return { label: 'Saisir le PIN de livraison', focus: 'delivery' };
  if (order.current_step?.kind !== 'CLINIC') return null;
  if (order.status === 'VALIDATION_CAO') return { label: 'Examiner le design', focus: 'design' };
  if (['LIVRE', 'ESSAYAGE'].includes(order.status)) return { label: 'Valider l’essayage clinique', focus: 'fitting' };
  if (order.status === 'RETOUR_DEMANDE') return { label: 'Corriger et soumettre à nouveau', focus: 'resubmit' };
  return null;
}
