# Simulation légère — conception et limites

La simulation v1 répond à une question de capacité avec des données synthétiques. Elle exerce les commandes métier et le planificateur existants ; elle ne certifie ni qualité clinique ni performances d’un laboratoire réel.

## Exécution et frontières

- Projet Docker **cabinet-sim**, API **18002**, sans frontend ni appareil.
- Base `cabinet_sim`, Redis et volumes propres à chaque `SIM_RUN`.
- Trois laboratoires : schémas `simpetit`, `simmoyen`, `simgrand`, noms affichés SIM-PETIT/MOYEN/GRAND.
- Le simulateur refuse le projet de présentation, celui de vérification, le schéma `simlab`, les anciens jeux déjà remplis et les dossiers hors de son registre.
- Deux dentistes globaux travaillent dans plusieurs laboratoires ; chaque cabinet et chaque dossier garde son propriétaire.
- Les identifiants sont générés dans le conteneur et ne figurent pas dans les métriques.

Les modules se trouvent dans `api/simulation/` : bootstrap et ressources, scénarios, client authentifié, horloge, moteur d’événements, métriques, isolation et rapport. La commande est `simulate_lab`. Le guide donne les [commandes exactes](../DEMO_GUIDE.md) de lancement et d’arrêt sans suppression de volumes.

## Personnel, demande et équipement

PETIT/MOYEN/GRAND disposent de **2/5/10 techniciens de conception et fabrication**, plus une personne de réception et une de qualité chacun : **4/7/12 personnes planifiées**. Les profils CAO/FAO sont distincts. Responsable, comptabilité et coursier ne créent pas une capacité supplémentaire.

La demande nominale est de 8/20/60 dossiers par jour ouvré. Le jeu exécuté réduit GRAND à **12/jour** pour borner le calcul ; il ne valide donc pas 60/jour. Le samedi reçoit la moitié du volume. PETIT utilise le parcours conventionnel ; MOYEN possède une usineuse et un four, GRAND deux de chaque. Les routes utilisent les machines et qualifications réellement configurées.

Trois exécutions de 28 jours sont prévues : normal, horaires réduits de type Ramadan, et mixte avec MOYEN à 30/jour et une usineuse GRAND indisponible une journée. Les variantes sont appliquées à la même période synthétique de novembre ; elles ne prétendent pas représenter le calendrier religieux réel.

## Horloge et commandes

L’horloge virtuelle est locale à la commande. L’[audit des sources de temps](SIMULATION_CLOCK_AUDIT.md) décrit les valeurs capturées, les limites PostgreSQL, Redis, signatures et PDF. Aucun mécanisme d’horloge n’est ajouté à la production.

Les acteurs synthétiques utilisent les vraies sessions, permissions, vues et commandes. Les décisions de contrôle sont explicites et tirées selon la graine du scénario. Aucun SQL ou changement ORM n’avance un statut. Les gardes de départ et de réservation restent actives ; un refus provoque une attente et une replanification normale.

Les phases chargement/cycle/fin réelle/déchargement sont distinctes. Le moteur tient compte de tournées de coursier et d’une attente de réponse du dentiste. L’outbox reste conservée sans publication externe ; les workers ne pilotent pas le temps virtuel. Une tâche PDF existante est appelée directement pour le contrôle documentaire.

## Mesures et preuves

Les métriques sont figées à la fin des 28 jours, avant les contrôles financiers d’isolation. Elles indiquent créés, livrés, clôturés, non-livrés, ponctualité par service, médiane/P90, trois attentes principales, occupation du personnel et des machines, reprises et panne.

Les livraisons de la dernière tentative sont distinguées des dossiers encore en reprise. Les attentes ouvertes sont censurées, donc des bornes inférieures. L’occupation machine comprend l’attente de déchargement ; ce n’est pas du temps de coupe productif. Les différences entre cohortes ne prouvent pas une causalité.

Chaque exécution contrôle les sept rôles laboratoire/coursier, les listes et identifiants de dossiers, tâches, fichiers, factures et paiements, les créances, le tableau de bord, les caches et les dentistes multi-laboratoires. Les **189 tentatives inter-laboratoires** doivent toutes être refusées sans écriture. Après la fenêtre, des dossiers SIM-CACHE et de nouvelles opérations financières propres au simulateur vérifient les caches et PDF sans contaminer les métriques.

Le rapport final et les JSON ne sont générés que lorsque les trois exécutions sont complètes et les preuves d’isolation valides. Les petits probes et les exécutions interrompues ne les remplacent pas. L’état daté est dans [TEST_RESULTS.md](TEST_RESULTS.md).

## Après la soutenance

La Phase 9 complète reste différée après le 9 décembre et nécessite une décision du propriétaire : interface de simulation, scénarios de déconnexion, comparaison des effectifs, intégrations d’appareils et calibration à partir d’un pilote réel. La simulation légère actuelle ne commence aucune de ces intégrations.
