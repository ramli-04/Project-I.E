// Technical codes stay unchanged on the wire; users see French labels.
const protocolLabels = {
  PENDING: 'En attente', APPROVED: 'Approuvé', CHANGES_REQUESTED: 'Corrections demandées',
  PHYSICAL: 'Empreinte physique', DIGITAL: 'Fichier numérique', MODEL: 'Modèle et scan', QUALITY: 'Qualité',
  USAGE: 'Consommation', REWORK_LOSS: 'Perte de reprise', RESTOCK: 'Réapprovisionnement', REVERSAL: 'Correction',
  LAB: 'Laboratoire', CLINIC: 'Cabinet', DESIGN: 'Design', PHOTO: 'Photo', STL: 'STL',
  OPEN: 'Ouvert', ACCEPTED: 'Acceptée', REJECTED: 'Rejetée', RESOLVED: 'Résolu',
  SENDING: 'Envoi en cours', SENT: 'Envoyé', UNKNOWN: 'Résultat à vérifier', WAIT_CONFIGURATION: 'Configuration requise',
  FAILED: 'Échec', DISABLED: 'Désactivé', EMAIL: 'E-mail', WHATSAPP: 'WhatsApp',
  CALENDAR: 'Calcul du calendrier', INVOICE: 'Facture', CREDIT: 'Avoir', CACHE: 'Actualisation du cache',
  CATALOG: 'Actualisation des états', PLANNING: 'Planification',
};
export const labelFor = value => protocolLabels[value] || value;
export const caseStatusLabel = order => order?.current_step?.label || order?.status_label
  || order?.workflow_steps?.find(step => step.key === order.status)?.label || 'Étape non renseignée';

const translations = new Map([
  ['ICE must contain exactly 15 digits.', 'L\u2019ICE doit contenir exactement 15 chiffres. Ce champ peut rester vide.'],
  ['Enter a valid email address.', 'Saisissez une adresse e-mail valide.'],
  ["Payments require a positive cent-precise amount.", "Saisissez un montant positif avec au plus deux décimales."],
  ["Reference is required for this payment method.", "La référence est obligatoire pour ce moyen de paiement."],
  ["An LCN maturity date is required.", "Renseignez la date d’échéance de la LCN."],
  ["Choose an invoice from this laboratory.", "Choisissez une facture de ce laboratoire."],
  ["Choose a clinic from this laboratory.", "Choisissez un cabinet de ce laboratoire."],
  ["Choose distinct invoices for the payment.", "Chaque facture ne peut figurer qu’une fois dans la répartition."],
  ["Payment allocations must equal the payment amount.", "Le total réparti doit correspondre exactement au montant encaissé."],
  ["Allocate only invoices belonging to this clinic.", "Affectez le paiement uniquement aux factures de ce cabinet."],
  ["Payment allocation exceeds the invoice balance.", "Le montant affecté dépasse le solde restant de la facture."],
  ["Payment idempotency key belongs to a different submission.", "Cette demande correspond à un autre encaissement. Actualisez avant de réessayer."],
  ["Payment has already been reversed.", "Cet encaissement a déjà été annulé."],
  ["Only cheque or LCN payments can be marked unpaid.", "Seuls un chèque ou une LCN peuvent être signalés impayés."],
  ["Choose a payment reversal reason.", "Choisissez un motif d’annulation de l’encaissement."],
  ["Invalid payment payload.", "Vérifiez les informations de l’encaissement."],
  ["Payment terms must be between 0 and 120 days.", "Le délai de paiement doit être compris entre 0 et 120 jours."],
  ["Choose a payment method.", "Choisissez un moyen de paiement."],
  ["Choose a valid payment date.", "Choisissez une date de paiement ou d’échéance valide."],
  ['This clinic does not belong to your account.', 'Ce cabinet n’est pas associé à votre compte.'],
  ['QR code belongs to a different laboratory or case.', 'Ce code QR appartient à un autre laboratoire ou dossier.'],
  ['Your role cannot perform this command.', 'Votre rôle ne permet pas cette action.'],
  ['Your workstation cannot perform this transition.', 'Votre poste ne permet pas de valider cette étape.'],
  ['Supply every required check for a valid inspection stage.', 'Renseignez tous les critères du contrôle correspondant à cette étape.'],
  ['This inspection does not match the current workflow step.', 'Ce contrôle ne correspond pas à l’étape actuelle du dossier.'],
  ['Inspection track does not match the case.', 'Le type de contrôle ne correspond pas à l’empreinte de ce dossier.'],
  ['Upload the actual STL file before its inspection.', 'Téléversez le fichier STL du dossier avant de contrôler le fichier numérique.'],
  ['Describe the non-compliance reason.', 'Décrivez le motif de non-conformité.'],
  ['This case is not at a rework-capable step.', 'Une reprise ne peut pas être enregistrée à cette étape.'],
  ['Dentists report remakes after delivery/fitting.', 'Le dentiste peut demander une reprise après la livraison ou l’essayage.'],
  ['Origin, cause and corrective action are mandatory.', 'Renseignez l’origine, la cause et l’action corrective de la reprise.'],
  ['Choose a responsible restart step from this production route.', 'Choisissez une étape de reprise adaptée au parcours de fabrication.'],
  ['Dentist review must be requested on a CAO case.', 'Demandez la validation du dentiste depuis l’étape CAO.'],
  ['Upload a design artifact for this case.', 'Téléversez un design pour ce dossier avant de demander sa validation.'],
  ['A design review is already pending.', 'Une demande de validation du design est déjà en attente.'],
  ['Only the owning dentist can approve or request design changes.', 'Seul le dentiste de ce dossier peut approuver le design ou demander des corrections.'],
  ['Choose a pending review and valid design decision.', 'Choisissez une demande en attente et une décision de validation valide.'],
  ['Describe the requested design changes.', 'Décrivez les corrections demandées sur le design.'],
  ['Provide paused=true/false and a pause reason.', 'Renseignez la décision de pause et son motif.'],
  ['A pending dentist review cannot be bypassed by resuming manually.', 'Attendez la décision du dentiste avant de reprendre le travail.'],
  ['Only a returned intake can be resubmitted.', 'Seul un dossier retourné peut être soumis à nouveau.'],
  ['This scan does not match the current custody step.', 'Ce scan ne correspond pas à l’étape actuelle du transport. Actualisez la mission.'],
  ['Checkout is required before delivery confirmation.', 'Enregistrez la sortie du laboratoire avant de confirmer la livraison.'],
  ['Only the owning dentist can issue a delivery PIN before receipt.', 'Seul le dentiste de ce dossier peut émettre un PIN avant la réception.'],
  ['The owning dentist records fitting after delivery.', 'Le dentiste du dossier valide l’essayage après la livraison.'],
  ['For failed fitting, use the rework command with origin, cause and action.', 'En cas d’essayage non conforme, enregistrez une reprise avec origine, cause et action corrective.'],
  ['Manual J+1 quotes are accepted before production/invoicing.', 'Le devis manuel J+1 doit être validé avant la production et la facturation.'],
  ['Provide the manual urgency surcharge.', 'Renseignez le supplément d’urgence du devis manuel.'],
  ['Edit remarks for your workstation only.', 'Modifiez uniquement les remarques de votre poste.'],
  ['Describe the contested line.', 'Décrivez le motif de contestation de la ligne comptable.'],
  ['This idempotency key belongs to a different command.', 'Cette demande correspond à une autre action déjà enregistrée. Actualisez puis réessayez.'],
  ['Choose a photograph from this case.', 'Choisissez une photo de preuve appartenant à ce dossier.'],
  ['Resume the case before advancing.', 'Reprenez le dossier avant de passer à l’étape suivante.'],
  ['Accept the case before advancing.', 'Acceptez la demande avant de passer à l’étape suivante.'],
  ['Confirm reception before advancing.', 'Confirmez la réception des éléments avant de continuer.'],
  ['Use the authenticated QR custody command.', 'Utilisez le scan QR de la mission pour enregistrer cette remise.'],
  ['Choose production method and confirmed delivery date.', 'Choisissez la méthode de fabrication et la date de livraison prévue.'],
  ['A manual J+1 quote is required before production.', 'Validez un devis manuel J+1 avant de lancer la production.'],
  ['An explicit disinfection declaration is required.', 'Confirmez explicitement la déclaration de désinfection.'],
  ['Issue invoices through monthly closing.', 'Émettez les factures depuis la clôture mensuelle.'],
  ['Use the rework command with origin, cause, action and measured losses.', 'Utilisez la reprise documentée avec origine, cause, action corrective et pertes mesurées.'],
  ['Submit a design version for dentist review.', 'Soumettez une version du design au dentiste avant de continuer.'],
  ['The production route is locked after planning.', 'Le parcours de fabrication est verrouillé après la planification.'],
  ['Accepted clinical specifications require a recorded revision.', 'Une modification clinique après acceptation nécessite une révision documentée.'],
  ['A failed intake inspection is required.', 'Enregistrez un contrôle de réception non conforme avant de demander un retour.'],
  ['Dentist design approval is required.', 'L’approbation du design par le dentiste est obligatoire.'],
  ['Only a design decision can return this case to CAO.', 'Seule une décision sur le design peut renvoyer ce dossier en CAO.'],
  ['Use the dentist fitting command.', 'Utilisez la validation d’essayage dans le portail dentiste.'],
  ['Advance to the next workflow step or use an explicit exception command.', 'Validez l’étape suivante du parcours ou enregistrez une exception documentée.'],
  ['Document belongs to another tenant.', 'Ce document n’appartient pas au laboratoire connecté.'],
  ['Upload a non-empty file of at most 25 MB.', 'Choisissez un fichier non vide de 25 Mo maximum.'],
  ['Choose STL, PHOTO (JPEG/PNG), or DESIGN (PDF/STL/JPEG/PNG).', 'Formats acceptés : STL, photo JPEG/PNG ou design PDF/STL/JPEG/PNG.'],
  ['STL uploads must use the .stl extension.', 'Le fichier STL doit porter l’extension .stl.'],
  ['The uploaded data is not a valid finite STL mesh.', 'Le fichier ne contient pas un maillage STL valide avec des coordonnées finies.'],
  ['Upload a valid JPEG or PNG photograph/design.', 'Choisissez une image JPEG ou PNG valide.'],
  ['Record material usage during a production step.', 'Enregistrez la consommation pendant une étape de production.'],
  ['Use the explicit, audited rework command.', 'Utilisez la reprise documentée pour enregistrer les pertes.'],
  ['This key already identifies a different movement.', 'Cette demande identifie déjà un autre mouvement de stock.'],
  ['Automatic rework classifications cannot be manually reversed.', 'Une perte classée par une reprise ne peut pas être annulée manuellement.'],
  ['This movement has already been reversed.', 'Ce mouvement a déjà fait l’objet d’une correction.'],
  ['Loss must reference unreversed consumption from the current attempt and cannot exceed it.', 'La perte doit correspondre à une consommation non annulée de la tentative actuelle, sans la dépasser.'],
  ['Each measured loss requires a usage UUID and decimal quantity.', 'Chaque perte doit référencer une consommation et une quantité décimale.'],
  ['Awaiting dentist design validation', 'En attente de validation du design par le dentiste'],
  ['Complete the analysis checkpoint.', 'Validez l’analyse de la demande avant de terminer cette étape.'],
  ['Inspection advance must be a boolean.', 'L’option de validation et de passage à l’étape suivante doit être un booléen.'],
  ['Your workstation cannot validate and advance this inspection checkpoint.', 'Votre poste ne peut pas valider et faire avancer ce contrôle. Demandez au poste responsable ou au responsable du laboratoire.'],
  ['Only an unaccepted new request can be accepted and advanced.', 'Seule une nouvelle demande non encore acceptée peut être acceptée et envoyée à l’analyse. Actualisez le dossier.'],
  ['A failed inspection or gap requires photographic evidence.', 'Un contrôle non conforme ou un écart nécessite une photo de preuve.'],
  ['Invalid or expired QR code.', 'Code QR invalide ou expiré. Scannez à nouveau l’étiquette de ce dossier.'],
  ['QR code does not match this case.', 'Ce code QR ne correspond pas à ce dossier.'],
  ['Incorrect delivery PIN.', 'PIN de livraison incorrect. Vérifiez les quatre chiffres auprès du dentiste.'],
  ['Invalid delivery PIN.', 'PIN de livraison invalide. Vérifiez les quatre chiffres auprès du dentiste.'],
  ['Link a production lot before fabrication.', 'Liez un lot de production au dossier avant la fabrication.'],
  ['Use QR checkout and server-side PIN confirmation.', 'Utilisez le QR pour l’expédition et le PIN pour confirmer la livraison.'],
  ['Validate final quality control.', 'Validez le contrôle qualité final.'],
  ['Network Error', 'Connexion au serveur impossible. Vérifiez votre connexion et réessayez.'],
  ['Failed to fetch', 'Connexion au serveur impossible. Vérifiez votre connexion et réessayez.'],
  ['Authentication credentials were not provided.', 'Connectez-vous pour effectuer cette action.'],
  ['You do not have permission to perform this action.', 'Votre compte ne permet pas cette action.'],
  ['Not found.', 'Élément introuvable ou inaccessible.'],
  ['This field is required.', 'Ce champ est obligatoire.'],
  ['This field may not be blank.', 'Ce champ ne peut pas être vide.'],
  ['This field may not be null.', 'Ce champ doit être renseigné.'],
  ['Enter a valid value.', 'Saisissez une valeur valide.'],
  ['Enter a valid date.', 'Saisissez une date valide.'],
  ['A valid integer is required.', 'Saisissez un nombre entier valide.'],
  ['A valid number is required.', 'Saisissez un nombre valide.'],
]);
const frenchWords = /[àâçéèêëîïôùûüœ]|\b(le|la|les|des|une?|du|de|est|sont|pour|avec|avant|après|dossier|champ|impossible|requis|requise|veuillez|erreur|aucun|aucune|votre|connexion|test)\b/i;

export function frenchMessage(value, fallback = 'Action impossible. Vérifiez les informations saisies et les prérequis de l’étape.') {
  const text = String(value ?? '').trim();
  if (!text) return fallback;
  if (translations.has(text)) return translations.get(text);
  const inspection = text.match(/^A passing (PHYSICAL|DIGITAL|MODEL|QUALITY) inspection for this revision\/attempt is required\.$/);
  if (inspection) return `Enregistrez un contrôle conforme « ${labelFor(inspection[1])} » pour cette version du dossier.`;
  if (/^Request failed with status code|^timeout of/.test(text)) return fallback;
  if (/\bpin\b.*(?:incorrect|invalid)|(?:incorrect|invalid).*\bpin\b/i.test(text)) return 'PIN incorrect ou invalide. Vérifiez les quatre chiffres auprès du dentiste.';
  return frenchWords.test(text) ? text : fallback;
}

const fieldLabels = { legal_name: 'Dénomination légale', address: 'Adresse du laboratoire', city: 'Ville du laboratoire', phone: 'Téléphone du laboratoire', ice: 'ICE', identifiant_fiscal: 'Identifiant fiscal', registre_commerce: 'Registre du commerce', patente: 'Patente', clinic: 'Cabinet', method: 'Moyen de paiement', amount: 'Montant', received_on: 'Date de réception', due_on: 'Échéance', bank: 'Banque', reference: 'Référence', allocations: 'Répartition', invoice: 'Facture', payment_terms_days: 'Délai de paiement', detail: '', non_field_errors: '', status: 'Étape', notes: 'Motif', pin: 'PIN', qr_token: 'Code QR',
  file: 'Fichier', code: 'Code', quantity_changed: 'Quantité', inventory_item: 'Consommable', prescription: 'Dossier',
  delivery_date: 'Livraison prévue', production_method: 'Méthode de fabrication', analysis_validated: 'Analyse',
  reception_validated: 'Réception', quality_validated: 'Qualité', employee: 'Technicien', machine: 'Machine',
  username: 'Identifiant', password: 'Mot de passe', email: 'Adresse e-mail' };

export function errorMessage(error) {
  const status = error?.response?.status;
  const fallback = status === 401 ? 'Session expirée ou identification incorrecte. Reconnectez-vous.'
    : status === 403 ? 'Votre compte ne permet pas cette action.'
      : status === 429 ? 'Trop de tentatives. Patientez avant de réessayer.'
        : status >= 500 ? 'Le serveur ne peut pas traiter la demande. Réessayez dans un instant.'
          : 'Action impossible. Vérifiez les informations saisies et les prérequis de l’étape.';
  const flatten = value => typeof value === 'string' ? frenchMessage(value, fallback)
    : Array.isArray(value) ? value.map(flatten).join(' ')
      : value && typeof value === 'object' ? Object.entries(value).map(([key, val]) =>
        `${fieldLabels[key] ? fieldLabels[key] + ' : ' : ''}${flatten(val)}`).join(' ') : fallback;
  return error?.response?.data ? flatten(error.response.data) : frenchMessage(error?.message, fallback);
}
