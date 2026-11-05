# Planning dynamique — audit et plan d’intégration

Date : 5 novembre 2026. Mission fournie dans le fichier joint « Planning dynamique et gestion manuelle du workflow de fabrication ».

## Phase 1 — audit

Graphify a été interrogé avant l’exploration : 1 110 nœuds, 2 653 liens au début de la mission. Le README local déjà modifié est conservé.

| Élément existant | Réutilisation / limite constatée |
| --- | --- |
| `api.models.EmployeeProfile` | Personnel opérationnel et rôle, disponibilité globale, lien utilisateur Django. Ajouter un lien facultatif vers le compte plateforme ; ne pas créer un second personnel. |
| `api.models.StaffMember` | Anciennes fiches, qualifications/horaires libres : ne pas déduire des qualifications obligatoires de ce texte. |
| `api.models.Machine` | État et capacité existants. Réutiliser les machines pour les réservations de capacité. |
| `api.workflow.workflow_steps/next_status` | Source du parcours réellement applicable, dépendant du type d’empreinte, de la méthode et de l’approbation CAO. |
| `api.domain.validate_source_change` | Gardes de rôles, preuves, QR/PIN, lots, devis J+1 et reprise : aucun contournement par le planning. |
| `api.case_commands.execute_case_command` | Verrouillage, audit et reçus UUID d’idempotence : intégrer les actions de tâches dans ce service. |
| `api.models.Prescription.save` | Point central protégé pour synchroniser les tâches après une modification métier validée, y compris les anciennes mises à jour autorisées. |
| `api.outbox` / `api.tasks` | Événements persistants et exécution Celery tenant-scoped, récupération après panne Redis. |
| Clients Axios et `retryableRequest` | Authentification et isolation du laboratoire à conserver. |
| `ProductionWorkflow.jsx` / `BpmnCasePanel.jsx` | Ajouter la progression de fabrication ; les preuves et actions spécialisées restent disponibles. |

## Plan retenu

1. Modèles tenant-scoped : tâches, qualifications structurées, disponibilités, paramètres et événements. Migration additive, contraintes PostgreSQL de non-chevauchement et journal immuable.
2. Génération depuis le parcours existant ; conserver les tâches terminées et les tentatives précédentes, annuler les tâches devenues inapplicables sans les supprimer.
3. Moteur déterministe : urgence et marge avant échéance, contraintes strictes de rôle/qualification/horaire/absence/capacité, puis score configurable. Réservations sérialisées par verrou du laboratoire.
4. Recalcul durable via Celery après les changements de commandes, disponibilités ou équipements. Les tâches en cours et affectations verrouillées ne sont pas déplacées automatiquement.
5. Commandes manuelles idempotentes : démarrer, terminer, pause, blocage, reprise ; terminer une tâche appelle la transition métier existante. Les validations de design et de livraison restent des commandes spécialisées.
6. API paginée et filtrée ; page React Planning avec calendrier, Gantt, charge, filtres et formulaires de supervision. Préserver le mode aperçu sans base.
7. Tests sur une instance PostgreSQL jetable séparée, tests d’interface, documentation et mise à jour Graphify. Aucune migration sur la base réelle, aucun envoi externe ni publication GitHub.

## Hypothèses explicites

- En l’absence d’un horaire hebdomadaire individuel, un employé déclaré disponible suit les heures d’ouverture configurées du laboratoire. Les absences et pauses individuelles sont prioritaires.
- Durées initiales indicatives et pondérations sont configurables. L’heuristique fournit une proposition explicable, pas une garantie d’optimalité.
- Les créneaux futurs sont prévisionnels : seule la tâche correspondant à l’étape métier actuelle peut démarrer, après satisfaction des dépendances et contraintes.
- Un devis J+1 non validé bloque l’entrée en fabrication. Une validation externe, un retour de dossier ou une pause ne sont pas remplacés par une simple fin de tâche.
- Une absence ou panne touchant une tâche déjà commencée ou verrouillée est signalée comme conflit ; elle exige une intervention autorisée.

## Fonctionnement et limites de cette version

Le moteur crée les tâches depuis `workflow_steps`, conserve les tentatives et révisions précédentes et synchronise les transitions métier validées. Il ne crée pas rétrospectivement de fausses heures de travail pour une commande déjà avancée. Les étapes externes (design, garde physique, QR/PIN, essayage) restent subordonnées à leurs commandes spécialisées.

L'affectation est déterministe : priorité commerciale, marge avant échéance, filtrage strict des ressources, puis score pondéré et identifiants stables. Les règles modifiées s'appliquent aux tâches automatiques déplaçables. Les horaires individuels qui se chevauchent sont fusionnés pour ne pas doubler la capacité.

Le recalcul réordonne les tâches déplaçables du laboratoire et préserve les tâches terminées, commencées, bloquées manuellement ou verrouillées. Une incompatibilité sur une réservation protégée devient un conflit visible. Cette version ne fournit pas encore de solveur optimal ni de recalcul incrémental limité à un sous-graphe. La limite est de 5 000 tâches non terminales et l'horizon configurable de 1 à 90 jours.

Les tâches réservent un employé et, si nécessaire, un équipement pendant toute leur durée. Elles ne sont pas fractionnées autour des pauses. Un frittage de neuf heures ne tient donc pas dans les fenêtres standard séparées par une pause : le moteur signale le blocage et exige une configuration adaptée. Les équipements sans surveillance et les équipes de nuit nécessitent une évolution métier spécifique.

Les créneaux manuels sont modifiés dans un formulaire validé côté serveur ; le glisser-déposer n'est pas implémenté. Le Gantt dessine les dépendances présentes sur la page et signale les prérequis hors page. Les couleurs distinguent statut et retard ; un trait sombre montre le temps réel.

Les dates sont stockées avec fuseau. Les paramètres API publient les transitions Africa/Casablanca utilisées par le backend sur une fenêtre de six ans ; le frontend les réutilise pour éviter les différences entre versions de tzdata Python et ICU Chromium. Hors de cette fenêtre, l'affichage utilise les règles du navigateur.

## API et permissions

Toutes les routes ci-dessous sont tenant-scoped et exigent une authentification de membre actif du laboratoire. Les coursiers n'ont pas accès au planning. Les mutations des ressources et la supervision sont réservées au responsable.

| Route | Usage |
| --- | --- |
| `GET /api/planning/tasks/` et `calendar/` | Tâches paginées, période et filtres employé, rôle, poste, statut, priorité, commande |
| `GET /api/planning/workload/` | Charge paginée, capacité calculée, conflits et risques de livraison |
| `GET/PATCH /api/planning/settings/` | Heures, jours, horizon, règles par étape et pondérations |
| `/api/planning/availability/` | Horaires hebdomadaires, absences, pauses et exceptions datées |
| `/api/planning/qualifications/` | Codes obligatoires, niveau et expiration |
| `GET /api/planning/accounts/` | Comptes actifs du laboratoire pour la liaison au personnel |
| `GET /api/planning/events/` | Journal immuable, filtré par tâche ou prescription |
| `POST /api/planning/recalculate/` | Envoi durable du recalcul ; nécessite un `Idempotency-Key` UUID |
| `POST /api/planning/tasks/{id}/assign/`, `reschedule/`, `lock/` | Supervision idempotente avec contrôles d'éligibilité et de conflits |
| `POST /api/prescriptions/{id}/command/` | Actions `planning-start`, `planning-complete`, `planning-pause`, `planning-block`, `planning-resume`, et `advance` |

Une action opérateur exige le rôle professionnel de la tâche et l'identité de son employé affecté. Le responsable peut superviser l'exécution. Les comptes plateforme liés au personnel doivent appartenir au même laboratoire et posséder un poste cohérent. L'action `advance` calcule la prochaine étape côté serveur et rejette un statut envoyé par le client.

Les transactions prennent le verrou de prescription avant le verrou de planning lorsqu'une écriture de commande ou un événement outbox référence cette prescription. Le recalcul utilise le verrou consultatif du laboratoire sans verrouiller d'autres commandes. Les exclusions PostgreSQL protègent les réservations employé/équipement contre les chevauchements. Les tâches terminales et les événements d'audit sont protégés par des triggers d'immuabilité.

## Migration et activation sur une base de développement

La migration additive `api.0024_production_planning` ajoute les modèles du planning, le lien optionnel entre personnel existant et compte plateforme, ainsi que le type d'équipement impression 3D. Elle n'efface aucune donnée existante.

L'extension PostgreSQL `btree_gist` doit être disponible dans `public` pour tous les schémas. La migration l'installe avec `CREATE EXTENSION IF NOT EXISTS ... WITH SCHEMA public`. Si une installation l'a déjà placée ailleurs, vérifier son schéma et les droits avec l'administrateur avant de déployer ; cette migration ne déplace pas une extension existante.

Depuis `cabinet_backend`, avec les variables de connexion d'une base de développement configurées :

```powershell
& '..\.venv\Scripts\python.exe' manage.py check
& '..\.venv\Scripts\python.exe' manage.py migrate_schemas --tenant --noinput
```

Rebâtir ensuite les workers existants (`docker compose up -d --build celery_worker celery_beat`). Configurer les ressources dans Planning, puis demander un recalcul pour initialiser les commandes acceptées antérieures. Les nouvelles transitions et modifications de ressources alimentent l'outbox automatiquement. Sans worker, les tâches sont synchronisées à l'enregistrement des commandes mais les affectations attendent le traitement différé.

Aucune migration n'a été appliquée à la base réelle pendant ce travail. Les tests ont utilisé uniquement les conteneurs dédiés `gestion-labo-planning-tests` et `gestion-labo-planning-redis-tests`, sur les ports locaux 55433 et 56379. Aucun identifiant n'est stocké dans ce document.

## Fichiers ajoutés et modifiés

| Ensemble | Fichiers |
| --- | --- |
| Nouveaux modèles et moteur | `cabinet_backend/api/planning_models.py`, `planning.py` |
| API et tests | `cabinet_backend/api/planning_views.py`, `test_planning.py`, `migrations/0024_production_planning.py` |
| Intégration backend | `models.py`, `serializers.py`, `views.py`, `urls.py`, `case_commands.py`, `case_serializers.py`, `outbox.py`, `tasks.py` dans `cabinet_backend/api/` |
| Nouvelles vues React | `cabinet_frontend/src/PlanningWorkspace.jsx`, `PlanningProgress.jsx`, `PlanningResources.jsx` |
| Dates et tests | `cabinet_frontend/src/planningTime.js`, `planningTime.test.js`, `cabinet_frontend/tests/integration.spec.js` |
| Intégration frontend | `App.jsx`, `LabAdminLayout.jsx`, `LabBusinessConfiguration.jsx`, `ProductionWorkflow.jsx`, `api/preview.js`, `index.css` dans `cabinet_frontend/src/`, et `cabinet_frontend/package.json` |
| Documentation | `README.md`, ce document, et mise à jour du graphe local Graphify |

## Vérifications

Commandes reproductibles depuis `cabinet_backend`, avec PostgreSQL et Redis **de test isolés** configurés et un rôle autorisé à créer la base de test :

```powershell
& '..\.venv\Scripts\python.exe' manage.py check
& '..\.venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
& '..\.venv\Scripts\python.exe' manage.py test api.test_planning api.test_bpmn_acceptance --noinput
& '..\.venv\Scripts\python.exe' manage.py test api customers --noinput
```

Depuis `cabinet_frontend` :

```powershell
npm.cmd run lint
npm.cmd run build
npm.cmd test
npm.cmd run test:browser
```

Les tests navigateur utilisent des réponses API contrôlées ; les tests Django exercent réellement PostgreSQL, l'API DRF, les permissions, les transitions et les contraintes. Cette validation ne comprend pas encore un parcours navigateur de bout en bout connecté à Django et à un worker Celery indépendant.

Le 5 novembre 2026, une comparaison de régression a exécuté **104 tests** sur cette version intermédiaire et **82 tests** sur le commit de référence `6454a4d` dans un worktree séparé. Les deux exécutions présentent les mêmes **22 échecs et 13 erreurs**, soit **33 groupes de tests** identiques (des sous-tests partagent leur nom). Les anciens tests de facturation/CQRS emploient des fixtures incompatibles avec les gardes métier ; d'autres scénarios attendent d'anciens contrats d'authentification. Aucun nouveau groupe d'échecs n'a été détecté. Ces échecs restent ouverts ; les contrôles métier n'ont pas été affaiblis pour les faire passer.

Résultats ciblés exécutés sur la version finale :

| Vérification | Résultat |
| --- | --- |
| Django `check` | Aucun problème détecté |
| `makemigrations --check --dry-run` | Aucune migration manquante |
| Planning + acceptation BPMN | **36 tests réussis** : 23 planning et 13 acceptation métier |
| Node | **9 tests réussis**, dont conversions et cohérence du fuseau fourni par le serveur |
| Chromium | **16 tests réussis** ; contrôle mobile du calendrier/de la charge réexécuté avec succès après vérification des captures |
| Build Vite | Réussi |
| Oxlint | Aucun nouvel avertissement ; un avertissement préexistant dans `App.jsx` sur l'effet de chargement |
| Graphify | Graphe AST actualisé : **1 314 nœuds, 3 404 relations**, extraction sans LLM |

Les captures de contrôle et journaux se trouvent dans `.runtime/`, ignoré par Git.
