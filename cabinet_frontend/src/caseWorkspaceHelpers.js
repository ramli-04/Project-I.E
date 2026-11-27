import { labDateTime, labLongDate } from './planningTime.js';

export const checksByStage = {
  PHYSICAL: { deformation: 'Absence de déformation', bubbles: 'Absence de bulles', limits: 'Limites lisibles', occlusion: 'Occlusion', hygiene: 'Hygiène' },
  DIGITAL: { margins: 'Marges', occlusion: 'Occlusion', space: 'Espace disponible', scan_quality: 'Qualité du scan' },
  MODEL: { model: 'Modèle', scan: 'Scan' },
  QUALITY: { margins: 'Marges', contacts: 'Contacts', shade: 'Teinte', occlusion: 'Occlusion', cosmetic: 'Esthétique', glazing: 'Glaçage', polishing: 'Polissage' },
};
export const phaseLabels = { PLANNED: 'Chargement → cycle autonome → déchargement', SETUP: 'Chargement / réglage · technicien occupé', CYCLE: 'Cycle autonome · technicien libéré', AWAITING_UNLOAD: 'Cycle terminé · machine occupée jusqu’au déchargement', UNLOADING: 'Déchargement · technicien occupé', FINISHED: 'Déchargement confirmé' };
export const terminalTasks = ['COMPLETED', 'CANCELLED'];
export function currentTask(order, tasks) {
  return tasks.filter(task => task.workflow_step === order.status && task.status !== 'CANCELLED'
    && task.production_attempt === order.production_attempt && task.intake_revision === order.intake_revision)
    .sort((a, b) => b.generation - a.generation)[0] || null;
}
export function latestInspection(order, evidence, stage) {
  const revision = stage === 'QUALITY' ? 'production_attempt' : 'intake_revision';
  return (evidence?.inspections || []).filter(row => row.stage === stage && row[revision] === order[revision])
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at) || Number(b.id) - Number(a.id))[0] || null;
}
export function taskWaitReason(order, task, tasks, now = Date.now()) {
  if (!task) return 'Aucune tâche disponible. Demandez au responsable de vérifier le Planning et l’affectation.';
  if (!task.can_operate) return task.employee_name ? `Tâche affectée à ${task.employee_name}. Contactez cette personne ou le responsable.` : 'Responsable à affecter dans le Planning.';
  if (!task.assigned_employee) return assignmentPending(task, tasks) ? 'Affectation en cours… Actualisez le dossier dans quelques secondes.' : 'Responsable à affecter dans le Planning avant de démarrer.';
  if (task.source_status !== order.status) return 'Le dossier a changé d’étape. Actualisez le dossier avant de poursuivre.';
  if (terminalTasks.includes(task.status)) return 'Cette tâche est terminée. Actualisez le dossier pour voir la suite.';
  if ((task.dependencies || []).some(id => tasks.find(row => row.id === id)?.status !== 'COMPLETED')) return 'Étape précédente à terminer : vérifiez le Planning avec le responsable.';
  if (task.status === 'PENDING') return task.blocking_reason || 'La tâche attend sa planification. Contactez le responsable.';
  if (['READY', 'SCHEDULED', 'PAUSED', 'BLOCKED'].includes(task.status) && task.planned_start && Date.parse(task.planned_start) > now) return `${plannedPrefix}${labDateTime(task.planned_start)}. Le responsable peut autoriser un démarrage supervisé dès maintenant.`;
  return '';
}
export const plannedPrefix = 'Prévu le ';
// The planner briefly blocks a successor until its asynchronous replan assigns it.
const transientReasons = ['Dépendance bloquée ou validation externe en attente.', 'Déchargement de l’équipement préalable non confirmé.'];
export function assignmentPending(task, tasks = []) {
  if (!task || task.assigned_employee || !['BLOCKED', 'PENDING'].includes(task.status)) return false;
  const done = (task.dependencies || []).every(id => tasks.find(row => row.id === id)?.status === 'COMPLETED');
  return done && (!task.blocking_reason || transientReasons.includes(task.blocking_reason));
}
export function ownsStep(order, role) {
  return role === 'MANAGER' || Boolean(order.current_step?.owner_roles?.includes(role));
}
const custodyTexts = {
  ATTENTE_RAMASSAGE: 'En attente du coursier pour la collecte au cabinet.',
  EN_ROUTE_LABO: 'En attente du coursier : acheminement vers le laboratoire.',
  PRET_EXPEDITION: 'En attente du coursier pour l’expédition vers le cabinet.',
  EN_ROUTE_CABINET: 'En attente du coursier : livraison au cabinet en cours.',
};
export function waitingText(order, dentist = false, evidence = null) {
  if (order.current_step?.kind === 'DONE') return 'Dossier clôturé après validation de l’essayage clinique.';
  if (dentist) return 'Les actions du cabinet sont disponibles pour cette étape.';
  if (order.status === 'VALIDATION_CAO') {
    const review = evidence?.design_reviews?.find(row => row.status === 'PENDING');
    return `En attente du dentiste : validation du design${review?.requested_at ? ` (version ${review.version} envoyée le ${labDateTime(review.requested_at)})` : ''}. Délai suspendu.`;
  }
  if (order.status === 'RETOUR_DEMANDE') return 'En attente du dentiste : documents à corriger avant une nouvelle soumission.';
  if (['LIVRE', 'ESSAYAGE'].includes(order.status)) return 'En attente du dentiste : essayage clinique de la prothèse livrée.';
  if (order.current_step?.kind === 'CUSTODY') return `${custodyTexts[order.status] || 'En attente du coursier.'} La remise se confirme depuis le portail coursier (QR ou PIN).`;
  return 'Cette étape est prise en charge par un autre poste. Consultez le responsable du laboratoire.';
}
// Dentist-facing status: no lab jargon or internal risk.
export function dentistProgressText(order) {
  const stage = order.stages?.find(row => row.state === 'current')?.label;
  const date = order.delivery_date || order.deadline_at;
  return `${stage ? `Votre dossier est à l’étape « ${stage} » au laboratoire.` : 'Votre dossier est en cours au laboratoire.'}${date ? ` Livraison prévue : ${labLongDate(date)}.` : ' Date de livraison à confirmer par le laboratoire.'}`;
}
