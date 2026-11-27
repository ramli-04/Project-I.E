import test from 'node:test';
import assert from 'node:assert/strict';
import { caseStatusLabel, errorMessage, frenchMessage, labelFor } from './messages.js';

test('workflow prerequisites and expired QR explain recovery in French', () => {
  assert.match(errorMessage({ response: { status: 400, data: { detail: 'Complete the analysis checkpoint.' } } }), /Validez l’analyse/);
  assert.match(frenchMessage('A failed inspection or gap requires photographic evidence.'), /photo de preuve/);
  assert.match(frenchMessage('A passing MODEL inspection for this revision/attempt is required.'), /Modèle et scan/);
  assert.match(frenchMessage('Invalid or expired QR code.'), /invalide ou expiré/);
});

test('untranslated server details have a French fallback without exposing technical text', () => {
  assert.equal(errorMessage({ response: { status: 500, data: { detail: 'SQL database internal connection failure' } } }),
    'Le serveur ne peut pas traiter la demande. Réessayez dans un instant.');
  assert.match(errorMessage({ message: 'Network Error' }), /Connexion au serveur impossible/);
  assert.equal(errorMessage({ response: { status: 400, data: { quantity_changed: ['This field is required.'] } } }), 'Quantité : Ce champ est obligatoire.');
});

test('French validation detail is preserved and protocol labels stay localized', () => {
  assert.match(frenchMessage('Inspection advance must be a boolean.'), /booléen/);
  assert.match(frenchMessage('Your workstation cannot validate and advance this inspection checkpoint.'), /Votre poste/);
  assert.match(frenchMessage('Only an unaccepted new request can be accepted and advanced.'), /nouvelle demande/);
  assert.equal(frenchMessage('Conflit de réservation : employé déjà occupé.'), 'Conflit de réservation : employé déjà occupé.');
  assert.equal(frenchMessage('Mot de passe incorrect.'), 'Mot de passe incorrect.');
  assert.equal(labelFor('APPROVED'), 'Approuvé');
  assert.equal(caseStatusLabel({ status: 'EN_ROUTE_LABO', status_label: 'Acheminement vers le labo' }), 'Acheminement vers le labo');
  assert.equal(frenchMessage('Awaiting dentist design validation'), 'En attente de validation du design par le dentiste');
});

test('case labels come from server metadata and never guess a workflow label', () => {
  assert.equal(caseStatusLabel({ status: 'USINAGE_CNC', status_label: 'Libellé serveur', current_step: { label: 'Sous-étape serveur' } }), 'Sous-étape serveur');
  assert.equal(caseStatusLabel({ status: 'USINAGE_CNC', workflow_steps: [{ key: 'USINAGE_CNC', label: 'Parcours serveur' }] }), 'Parcours serveur');
  assert.equal(caseStatusLabel({ status: 'USINAGE_CNC' }), 'Étape non renseignée');
  assert.equal(caseStatusLabel(null), 'Étape non renseignée');
  assert.equal(labelFor('USINAGE_CNC'), 'USINAGE_CNC');
});


test('capacity preview clinic access errors are French', () => {
  assert.equal(frenchMessage('This clinic does not belong to your account.'), 'Ce cabinet n’est pas associé à votre compte.');
});


test('every new payment rule has an exact French translation', () => {
  const entries = {
  "Payments require a positive cent-precise amount.": "Saisissez un montant positif avec au plus deux décimales.",
  "Reference is required for this payment method.": "La référence est obligatoire pour ce moyen de paiement.",
  "An LCN maturity date is required.": "Renseignez la date d’échéance de la LCN.",
  "Choose an invoice from this laboratory.": "Choisissez une facture de ce laboratoire.",
  "Choose a clinic from this laboratory.": "Choisissez un cabinet de ce laboratoire.",
  "Choose distinct invoices for the payment.": "Chaque facture ne peut figurer qu’une fois dans la répartition.",
  "Payment allocations must equal the payment amount.": "Le total réparti doit correspondre exactement au montant encaissé.",
  "Allocate only invoices belonging to this clinic.": "Affectez le paiement uniquement aux factures de ce cabinet.",
  "Payment allocation exceeds the invoice balance.": "Le montant affecté dépasse le solde restant de la facture.",
  "Payment idempotency key belongs to a different submission.": "Cette demande correspond à un autre encaissement. Actualisez avant de réessayer.",
  "Payment has already been reversed.": "Cet encaissement a déjà été annulé.",
  "Only cheque or LCN payments can be marked unpaid.": "Seuls un chèque ou une LCN peuvent être signalés impayés.",
  "Choose a payment reversal reason.": "Choisissez un motif d’annulation de l’encaissement.",
  "Invalid payment payload.": "Vérifiez les informations de l’encaissement.",
  "Payment terms must be between 0 and 120 days.": "Le délai de paiement doit être compris entre 0 et 120 jours.",
  "Choose a payment method.": "Choisissez un moyen de paiement.",
  "Choose a valid payment date.": "Choisissez une date de paiement ou d’échéance valide."
};
  for (const [message, translation] of Object.entries(entries)) assert.equal(frenchMessage(message), translation);
});


test('laboratory identity errors and field names are French', () => {
  const translated = frenchMessage('ICE must contain exactly 15 digits.');
  assert.equal(frenchMessage(translated), translated);
  assert.equal(frenchMessage('ICE : ' + translated), 'ICE : ' + translated);
  assert.equal(frenchMessage('ICE must contain exactly 15 digits.'), 'L\u2019ICE doit contenir exactement 15 chiffres. Ce champ peut rester vide.');
  assert.equal(errorMessage({ response: { status: 400, data: { ice: ['ICE must contain exactly 15 digits.'] } } }),
    'ICE : L\u2019ICE doit contenir exactement 15 chiffres. Ce champ peut rester vide.');
  assert.equal(errorMessage({ response: { status: 400, data: { legal_name: ['This field may not be null.'] } } }),
    'Dénomination légale : Ce champ doit être renseigné.');
  assert.equal(frenchMessage('Enter a valid email address.'), 'Saisissez une adresse e-mail valide.');
});
