import test from 'node:test';
import assert from 'node:assert/strict';
import { errorMessage, frenchMessage, labelFor } from './messages.js';

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
  assert.equal(frenchMessage('Conflit de réservation : employé déjà occupé.'), 'Conflit de réservation : employé déjà occupé.');
  assert.equal(frenchMessage('Mot de passe incorrect.'), 'Mot de passe incorrect.');
  assert.equal(labelFor('APPROVED'), 'Approuvé');
  assert.equal(labelFor('EN_ROUTE_LABO'), 'En route vers le laboratoire');
  assert.equal(frenchMessage('Awaiting dentist design validation'), 'En attente de validation du design par le dentiste');
});
