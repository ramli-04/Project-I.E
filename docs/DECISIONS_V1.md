# Gestion Labo v1.0 : décisions produit

Décisions du 25 novembre 2026 : **approved by product owner**. Source : statut et phase 8 de `AGENT_PROMPT_UX_STREAMLINING.md`. Ce document consigne le périmètre approuvé ; il ne certifie pas que les étapes suivantes sont déjà livrées.

## D1 : complétude et capacité

La complétude reste bloquante selon les validations existantes, sans nouveau champ obligatoire. La capacité est seulement indicative : afficher une date réaliste et proposer un délai plus long, sans refuser la commande ni suspendre son délai. Aucun statut `EN_ATTENTE` n'est ajouté. Une projection impossible reste inconnue et ne bloque jamais l'envoi. La méthode de fabrication reste choisie au planning. Clarification approuvée par le propriétaire le 25 novembre : comparer les routes existantes et afficher la première date atteignable, clairement indiquée comme provisoire, sans choisir de route pour le dossier.

## D2 : encaissements et créances

Enregistrer les chèques, LCN, virements et espèces, sans passerelle de paiement. Autoriser des paiements partiels répartis sur plusieurs factures du même cabinet, intégralement affectés et plafonnés aux soldes. Conserver paiements, affectations et annulations comme preuves immuables ; une annulation rouvre les soldes. Afficher soldes, échéances et tranches d'ancienneté 0–30 / 31–60 / 61–90 / plus de 90 jours. Délai cabinet par défaut de 60 jours, configurable entre 0 et 120 ; aucune pénalité légale calculée. Livraison prévue à l'étape 8.2.

## D3 : tableau de bord

Ajouter une page « Tableau de bord » pour le gestionnaire, avec le sous-ensemble financier pour la comptabilité. Réutiliser planning, étapes et catalogues existants ; ne pas créer de seconde source de chiffres. « À faire » reste la page d'arrivée. Livraison prévue à l'étape 8.3.

## D4 : identité du laboratoire

Ajouter un profil juridique unique par laboratoire : nom, adresse, ville, téléphone, email et ICE ; IF, RC et patente facultatifs. Utiliser « Gestion Labo » et cette identité uniquement sur les nouveaux documents. Les anciennes factures, les anciens avoirs et leurs PDF restent inchangés. Un profil vide doit conserver la génération avec le nom existant du laboratoire. Livraison prévue à l'étape 8.4.

## D5 : contrôle de pièce G7, v2

Reporter le contrôle explicite « Pièce OK ? » à la v2. La v1 garde les commandes explicites de reprise existantes, sans inspection clinique automatique ni nouveau contrôle implicite.

## D6 : dossiers de reprise liés, v2

Reporter le nouveau dossier lié après livraison à la v2. La v1 conserve l'identité du dossier et ses tentatives de production. Le projet v2 distingue le nouveau dossier après livraison des tentatives internes au laboratoire.

## D7 : rôles et voies BPMN, v2

Reporter l'alignement des voies et les ensembles de capacités cumulables à la v2. Aucun transfert de propriété des étapes ni changement des rôles existants n'est approuvé pour la v1.

## D8 : simulateur léger

Livrer à l'étape 8.2b une simulation déterministe, synthétique, dans le projet Compose isolé `cabinet-sim`, avec trois laboratoires distincts. Utiliser les vraies commandes et le vrai planning sans modifier le code de production pour la simulation. Produire les indicateurs de délais, de goulets, d'utilisation et les preuves d'isolation ; publier les limites et tout périmètre réduit. Le simulateur complet de phase 9 est reporté après la soutenance du 9 décembre.

## Protection et limites

Phases 0–7 terminées ; phase 8 reprise à l'étape 8.0. Aucun commit, stash, reset, nettoyage Git, push ou PR. Instantanés locaux hors OneDrive avant l'étape 8.1 et après chaque étape ; sauvegarde `pg_dump` avant la première migration du projet de démonstration. Migrations uniquement additives dans les deux projets Docker autorisés. Préserver `MY-TEST-001`, ses preuves et sa ligne de 1500 MAD. Aucun envoi externe, aucun appareil connecté, aucune intervention sur PostgreSQL natif. Clôture de novembre et déploiement exigent leurs instructions spécifiques. Gel fonctionnel le 4 décembre 2026 à 23 h 59 (calendrier du laboratoire).

## Clarification D1 approuvée le 25 novembre

Le formulaire dentiste n'envoie pas de méthode de fabrication ; `PrescriptionSerializer` la garde en lecture seule à la création. Le propriétaire a choisi : « Check all existing routes and show the earliest achievable date, clearly labelled as provisional ». Le preview compare les routes possibles avec le planning existant et ne sauvegarde aucun choix. Les validations humaines, le transport et les indisponibilités non renseignées restent des limites explicites ; une estimation impossible ne bloque jamais la commande.


## Clarification D2 approuvée le 25 novembre

Si un avoir intervient après paiement et rend le solde négatif, conserver les deux preuves. Afficher « Trop-perçu à régulariser » et séparer ce montant des créances en retard. Ne pas annuler automatiquement le paiement, modifier la facture ni ajouter de remboursement automatique. Cette clarification s'appliquera à l'étape 8.2.


## Clarification D8 approuvée le 25 novembre

Les 2 / 5 / 10 techniciens des profils PETIT / MOYEN / GRAND désignent le personnel technique de conception et fabrication. Ajouter, dans chaque laboratoire, un réceptionniste et un opérateur qualité distincts. Le rapport distingue les techniciens et l'effectif total planifié, soit 4 / 7 / 12 personnes. Ne pas représenter une personne par plusieurs profils qui seraient planifiés indépendamment. L'alignement des rôles reste reporté à la v2.
