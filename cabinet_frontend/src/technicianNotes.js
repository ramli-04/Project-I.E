const options = rows => rows.map(([id, label, text]) => ({ id, label, text }));

const waiting = options([
  ['instructions', 'Attente de précisions', 'En attente de précisions ou d’instructions.'],
  ['material', 'Matière indisponible', 'Matière nécessaire indisponible.'],
  ['equipment', 'Incident technique', 'Incident technique : intervention nécessaire.'],
  ['check', 'Contrôle complémentaire', 'Contrôle complémentaire nécessaire avant de poursuivre.'],
]);

export function clinicalNotePresets(order, stage, dentist = false) {
  let specific = [];
  if (dentist) {
    specific = ['LIVRE', 'ESSAYAGE', 'CLOTURE'].includes(order.status)
      ? options([['fitting', 'Essayage conforme', 'Essayage clinique conforme.'], ['fit-correction', 'Ajustement nécessaire', 'Ajustement nécessaire après essayage clinique.']])
      : ['SALLE_CAO', 'VALIDATION_CAO'].includes(order.status)
        ? options([['approved', 'Design approuvé', 'Design vérifié et approuvé.'], ['changes', 'Corrections du design', 'Corrections du design nécessaires avant approbation.']])
        : [];
  } else if (stage) {
    const titles = { PHYSICAL: 'Empreinte physique', DIGITAL: 'Dossier numérique', MODEL: 'Modèle et scan', QUALITY: 'Contrôle qualité' };
    specific = options([['conform', 'Contrôle conforme', `${titles[stage]} : critères contrôlés et conformes.`], ['nonconform', 'Écart constaté', `${titles[stage]} : écart constaté, correction nécessaire.`]]);
  } else if (['SALLE_CAO', 'VALIDATION_CAO'].includes(order.status)) {
    specific = options([['design', 'Design prêt à soumettre', 'Design terminé, validation du dentiste demandée.'], ['design-correction', 'Design corrigé', 'Design corrigé selon les indications du dentiste.']]);
  }
  return [...specific, ...waiting];
}

export function progressNotePresets(task = {}) {
  let specific;
  if (['READY', 'SCHEDULED'].includes(task.status)) {
    specific = options([['early-start', 'Démarrage anticipé', 'Démarrage anticipé pour respecter le délai de livraison.']]);
  } else {
    const phase = {
      SETUP: ['loaded', 'Chargement terminé', 'Chargement et réglages terminés.'],
      CYCLE: ['cycle-finished', 'Cycle terminé', 'Cycle terminé, pièce encore dans l’équipement.'],
      AWAITING_UNLOAD: ['unloading', 'Déchargement en cours', 'Déchargement de l’équipement en cours.'],
      UNLOADING: ['unloaded', 'Déchargement terminé', 'Pièce retirée, déchargement terminé.'],
    }[task.resource_phase];
    const manual = task.workflow_step === 'CONDITIONNEMENT'
      ? ['packed', 'Conditionnement terminé', 'Pièce emballée, étiquette et bon de livraison prêts.']
      : task.workflow_step === 'FINITION'
        ? ['finished', 'Finition terminée', 'Finition et caractérisation terminées.']
        : ['completed', 'Travail terminé', 'Travail de l’étape terminé.'];
    specific = options([phase || manual]);
  }
  return [...specific, ...waiting, ...options([['resume', 'Problème résolu', 'Problème résolu, reprise du travail.']])];
}

export const supervisionNotePresets = options([
  ['priority', 'Priorité de livraison', 'Réaffectation pour respecter la priorité de livraison.'],
  ['absence', 'Collaborateur indisponible', 'Réaffectation en raison de l’indisponibilité du collaborateur.'],
  ['maintenance', 'Équipement indisponible', 'Réaffectation en raison de l’indisponibilité de l’équipement.'],
  ['schedule', 'Organisation du planning', 'Ajustement du planning après vérification des disponibilités.'],
]);

// Keep the existing plain-text audit contract; an optional detail follows the chosen reason.
export function splitReasonNote(value, presets) {
  const preset = presets.find(row => value === row.text || value.startsWith(`${row.text}\n`));
  return { preset, detail: preset ? value.slice(preset.text.length + 1) : value };
}

export function composeReasonNote(preset, detail) {
  return preset ? preset.text + (detail ? `\n${detail}` : '') : detail;
}
