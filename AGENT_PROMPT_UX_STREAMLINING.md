# Agent brief — Gestion Labo: streamline the user experience against the BPMN

You are continuing **Gestion Labo** (previously *Cabinet 2.0*), a multi-tenant platform for the dental-prosthesis order process: dentists, laboratories, technicians and couriers in one traceable workflow (prescription → intake → fabrication → quality → delivery → fitting → monthly billing). UI language is **French**; money is **MAD**; laboratory calendar is **Africa/Casablanca**.

Repository root: `c:\Users\SetupGame\OneDrive\Desktop\I.E\Soutenance\Projet Innov` (git branch `feat/virtual-lab-demo`, HEAD `42f52aa`, clean tree when this brief was written). Shell: Windows PowerShell 5.1 (use `npm.cmd`, `npx.cmd`; no `&&`).

The product owner's goal, in their words: *"easier for the user, straight to the point."* The backend business rules are sound and verified; the problem is that the screens make users navigate the machinery. Your job is to make each user see **only their work** and do **one obvious action per BPMN step**, while preserving every server-side guard, the audit trail, and the existing demo data.

Work **phase by phase**. Each phase ends with verification and a short report. **Stop and ask the user** at every gate marked ⛔.

> **Status update (25 Nov 2026), read this first.**
> - **Phases 0–7 are done.** See the dated sections of `docs/TEST_RESULTS.md`. The latest counts are 185 Django tests, 21 frontend unit tests, 63 mocked Playwright tests and 12 real-API Playwright tests. All of this work is still uncommitted on top of `42f52aa`.
> - **The product owner has now made the Phase 8 decisions.** Phase 8 below is no longer a design-and-ask gate; it is an implementation phase with its own steps and gates. A light virtual-lab simulator is now **Step 8.2b**. The full Phase 9 simulator comes after the defense.
> - **Resume at Phase 8, Step 8.0.**
> - **Deadline.** The product is defended as **"Gestion Labo v1.0"** on **9 December 2026**. Feature freeze is **4 December 2026 at 23:59**.

---

## 0. Non‑negotiable constraints

1. **Graphify first.** `graphify-out/graph.json` exists. Before your first grep/search/source read for any codebase question, run `.\graphify.cmd query "<question>"` from PowerShell (the wrapper fails from Git Bash because the path contains a space). Use `.\graphify.cmd path "<A>" "<B>"` and `.\graphify.cmd explain "<concept>"` for relationships. Read raw files only for lines the graph located. After modifying code, run `.\graphify.cmd update .`. Put this rule in any sub-agent prompt you write. See `AGENTS.md` and `docs/GRAPHIFY.md`.
2. **Preserve data.** Never remove Docker volumes, reset databases, reseed destructively, or edit rows by SQL/ORM to advance a case. The demo project `cabinet-virtual-lab` (frontend :18080, API :18000) holds the user's **closed case MY-TEST-001** (status `CLOTURE`, quality validated, exactly one 1500.00 MAD November statement line). It must remain untouched. Never advance, reset or "fix" it.
3. **Preserve secrets and private files.** Do not read, print, copy or commit `.env`, `.runtime/` (signing key, bootstrap credentials), `private_media/`, tokens or PINs.
4. **Do not touch the native (non-Docker) PostgreSQL database.** All work and checks use the Docker demo stack or the separate verification stack.
5. **Keep every server guard.** Do not weaken `validate_source_change` (`cabinet_backend/api/domain.py:37`), role checks, idempotency (`CaseCommandReceipt`), PostgreSQL triggers/constraints (migrations `0021`, `0022`, `0024`, `0025`), planning locks, or tenant isolation. New behaviour must go *through* these guards, never around them.
6. **Clinical rule (user decision).** Nothing may approve a clinical check automatically. Reason dropdowns (`ReasonNote`, `technicianNotes.js`) only prepare text; they never tick checks or submit. The new **"Tout conforme"** button is allowed **only** as an explicit user click that ticks the boxes locally. It must not submit, and the user can still untick boxes afterwards.
7. **No external delivery, no devices.** Email/WhatsApp stay disabled (`EXTERNAL_DELIVERY_ENABLED=0`, simulation mode). Do not start CNC/furnace/scanner/printer/CAD integration. Equipment phases stay human acknowledgements.
8. **Wire contract stability.** Backend error strings are an API contract. `cabinet_frontend/src/api/messages.js` translates exact English messages to French (`translations` map, tested in `messages.test.js`). Do not change existing backend message text. Every **new** backend message needs a French entry and a test.
9. **Audit/action strings are persisted.** Values written to `metadata['action']` end up in immutable audit rows (`WorkflowEvent`, `PlanningEvent`). Never rename existing values. New values are allowed and must be documented.
10. **No migrations in phases 1–7.** `manage.py makemigrations --check --dry-run` must report *no changes* after each of those phases. **In Phase 8, additive migrations are approved** under the rules in "Phase 8 amendments".
11. **No commit, push or PR until the product owner explicitly says so.** The product owner will test the result first and decide when to commit. Until then, protect the work with the local snapshots described in Step 8.0.
12. **French UI copy, English code/comments.** Keep accessibility: labelled controls, focus return on dialogs, `aria-*` on tabs and steppers, `prefers-reduced-motion`, and a usable layout at 390px width.

---

## 1. The BPMN (authoritative process model)

The user's BPMN (`processus_laboratoire_prothese.pdf`, 2 pages) is transcribed here, because you cannot open it.

**Global rules:** every QR scan updates the status, the timestamped log, and notifies the clinic. A problem found at any step returns to *the step at fault*. A remade case stays linked to the original case.

### Page 1: order to CAD
Lanes: Cabinet dentaire · Système (application) · Coursier · Réception (labo) · Technicien plâtre et scan · Prothésiste CAO.

| # | Element | Type | Flows |
|---|---|---|---|
| S | Début | start | → Saisir la commande |
| A1 | **Saisir la commande** (Cabinet): teeth, function, shade, form, material, send mode, J+4 / J+2 / J+1, design-validation option | task | → G1 |
| G1 | **Dossier complet et créneau OK ?** (Système) | gateway | Oui → A2 · Non → E1 |
| E1 | **En attente**: alert "compléter ou choisir une autre date", deadline suspended | problem | "Compléter" → A1 |
| A2 | **Calendrier automatique**: deadline, case number, QR, clinic notified | task | → G2 |
| G2 | **Empreinte physique ou fichier STL ?** | gateway | Physique → A3 · Fichier STL → A5 |
| A3 | **Collecte au cabinet** (Coursier): QR scan, lab deposit, status "à confirmer" | task | → A4 |
| A4 | **Contrôle d'entrée** (Réception): deformation, bubbles, limits, occlusion, hygiene, photos | task | → G3 |
| G3 | **Empreinte conforme ?** | gateway | Oui → A6 · Non → E2 |
| A5 | **Contrôle du fichier STL** (Réception): margins, occlusion, space, scan quality | task | → G4 |
| G4 | **Fichier conforme ?** | gateway | Oui → A7 · Non → E2 |
| E2 | **Renvoi demandé** (Cabinet): notification with reason and photos, new impression or new file | problem | "Renvoi" → G2 |
| A6 | **Plâtre et scan** (Technicien plâtre et scan): pour, base, articulator, lab scan | task | → G5 |
| G5 | **Modèle et scan OK ?** | gateway | Oui → A7 · Non → E3 |
| E3 | **Recouler / rescanner**: loss recorded in stock | problem | → A6 |
| A7 | **Conception CAO** (Prothésiste CAO): remarks by type visible at the workstation | task | → G6 |
| G6 | **Validation demandée ?** | gateway | Oui → A8 · Non → connector A |
| A8 | **Valider le design** (Cabinet): dentist approves or requests a change, deadline suspended | task | → connector A |

### Page 2: fabrication to monthly billing
Lanes: Cabinet dentaire · Système · Fabrication (atelier) · Finition et contrôle qualité · Coursier · Comptabilité.

| # | Element | Type | Flows |
|---|---|---|---|
| A | connector from page 1 | — | → B1 |
| B1 | **Fabrication** (Atelier): milling, 3D printing or casting; sintering if zirconia; lot linked to the case | task | → G7 |
| G7 | **Pièce OK ?** | gateway | Oui → B2 · Non → E4 |
| E4 | **Refaire la pièce**: stock loss, alert | problem | → B1 |
| B2 | **Finition**: cosmetic, glazing, polishing | task | → B3 |
| B3 | **Contrôle qualité**: margins, contacts, shade, photo if deviation | task | → G8 |
| G8 | **Contrôle conforme ?** | gateway | Oui → B4 · Non → E5 |
| E5 | **Retour à l'étape en cause**: cause and action recorded | problem | → CAO, fabrication or finishing |
| B4 | **Livraison au cabinet** (Coursier): QR scan at exit, delivery note, clinic PIN code | task | → B5 and → B6 |
| B5 | **Réceptionner** (Cabinet): PIN entry, fitting in the mouth | task | → G9 |
| G9 | **Essayage conforme ?** | gateway | Oui → Fin · Non → E6 |
| E6 | **Cas à refaire** (Système): linked to the original case, origin recorded (lab or clinic) | problem | "Reprise à l'étape en cause" → B1 |
| B6 | **Cas livré** (Comptabilité): added to the month's invoice | task | → B7 |
| B7 | **Clôture mensuelle**: online statement, one line per case, urgency surcharge | task | → G10 |
| G10 | **Relevé contesté ?** | gateway | Non → B8 · Oui → E7 |
| E7 | **Ligne contestée**: case excluded, credit note if corrected | problem | → B7 |
| B8 | **Facture envoyée**: PDF by email or WhatsApp, payment tracking | task | → Fin |

### Known divergences between the BPMN and the code (verified)
- **G1 is not implemented** as an order-entry gate. There is no completeness or slot check at creation, and no "En attente / compléter" loop. The nearest equivalents are the `ANALYSE_DEMANDE` checkpoint and planning delivery-risk reporting.
- **"Suivi des paiements" (B8) has no model.** Invoices and credit notes exist; no payment record exists.
- **G7 "Pièce OK ?" is implicit.** It is handled by the on-demand `rework` command from a manufacturing step. No inspection is recorded.
- **Remakes reuse the same case** with an incremented `production_attempt` (`case_commands.py:180-211`). The BPMN says a remade case "stays linked to the original", which suggests a new linked case.
- **Steps the BPMN does not show:** `ANALYSE_DEMANDE`, `PLANIFICATION` (route and delivery-date choice), `CONDITIONNEMENT`, `PRET_EXPEDITION`, the conventional route (`MODELE_TRAVAIL`, `MODELAGE`, `FABRICATION_MANUELLE`), and the planning/equipment-phase module.
- **Lane vs role mismatches:** the BPMN lane "Technicien plâtre et scan" maps to role `RECEPTION` in code (`COULEE_PLATRE`, `SCAN_LABO`, `CONTROLE_MODELE`). The BPMN puts "Finition" in the QC lane, but code gives `FINITION` to `FAO`. **Do not change role ownership** without ⛔ user approval; record it in the coverage matrix (phase 7).

---

## 2. Current architecture (facts you can rely on; verify line numbers with Graphify)

### Backend (`cabinet_backend/api/`)
- `workflow.py`
  - `LABELS` and `TREATMENTS` hold the French labels.
  - `workflow_steps(order)` (line 23) builds a **linear, route-dependent list**: physical vs digital intake, `intake_version >= 2` (plaster/model steps, fitting), CFAO / 3D / conventional, optional `VALIDATION_CAO`, optional thermal treatment, legacy `FRITTAGE_9H`. Rework statuses (`A_REFAIRE`, `RECOULER`, `RESCANNER`) are inserted before `rework_restart_status`.
  - `next_status(order)` (line 62) returns the next key in that list.
- `domain.py`
  - `MANUFACTURING` (7), `REWORK_ORIGINS` (8), `ROLE_STAGES` (11).
  - `validate_source_change` (37) runs on **every** `Prescription.save()` (`models.py:336-359`). It enforces role ownership, pause, acceptance, rework/return/design/fitting special transitions, `next_status` linearity, and evidence: analysis and reception flags, passing inspections per revision/attempt, production lot before manufacturing, dentist approval, QR custody, PIN delivery, planning prerequisites and the J+1 quote.
  - It reads `metadata['role']` and `metadata['action']` from a context variable set by `prescription_audit_context` (`signals.py`).
- `case_commands.py`
  - `execute_case_command` (75): UUID idempotency receipt, payload digest, billing lock for some commands, `select_for_update`. It sets `metadata = {'role', 'action': command.upper()}`, so custody actions are `PICKUP`, `LAB-DEPOSIT`, `CHECKOUT`.
  - `_execute` (111) is one ~270-line `if command == ...` chain covering: `advance`, `planning-*` (delegated to `planning.task_command`), `inspection`, `rework`, `design-request`, `design-decision`, `pause`, `resubmit`, `pickup` / `lab-deposit` / `checkout`, `confirm-delivery`, `issue-pin`, `fitting`, `quote`, `note`, `dispute`, `assess-loss`.
  - `advance` (115) validates via `PrescriptionSerializer` (fields allowed per role at `case_serializers.py:126-134`), computes the target with `next_status` on a copy, and refuses `EXTERNAL` steps and `VALIDATION_CAO`.
  - `inspection` (141): stages `PHYSICAL`, `DIGITAL`, `MODEL`, `QUALITY` (`CHECKS`, line 21). The permitted map is at line 148. Failure requires a photo and notes. A failed `PHYSICAL`/`DIGITAL` inspection moves to `RETOUR_DEMANDE`. A failed `MODEL`/`QUALITY` inspection **stays** at the checkpoint until an explicit `rework`. **A passing inspection does not advance**; the user must then click "Valider →".
  - `rework` (180): the valid restart set is computed inline (lines 190-195).
- `planning.py`
  - `EXTERNAL` (30), `DEFAULT_RULES` (32): role, duration and machine per step.
  - `sync_order` (89) runs after every source save:
    - Advancing a case **auto-completes** earlier tasks (`SOURCE_COMPLETED`, no `actual_start` if never started).
    - It **refuses** leaving a step whose task is an unattended machine task (`resource_phase == 'PLANNED'`) or one in an equipment phase (lines 98-106).
  - `task_command` (482):
    - `planning-start` requires the assigned employee (`_can_operate`, 472) and no future `planned_start` unless the manager uses `start_now` with a reason.
    - `planning-launch-cycle`, `planning-cycle-finished` (reason required), `planning-begin-unload`, `planning-complete` (610). `planning-complete` **also advances the case** via `next_status` + `change_status`.
  - So, for manual steps, **two paths** advance a case: `advance` (role-based) and `planning-complete` (assignee-based).
- `case_serializers.py`: `PrescriptionSerializer` exposes `workflow_steps`, `next_status`, `status_label`, `quote_required`.
- `views.py:135-165` (`PrescriptionViewSet.list`): active (non-completed) cases are serialized **once for all users** and cached under Redis key `active_orders`, versioned by `TenantReadVersion('active_orders')`. Per-role filtering happens after the cache (`workstation_notes`). **Anything user-specific must not go into the cached serializer output.** If you add fields to `PrescriptionSerializer`, also add a payload-shape constant to the cache envelope (for example `{'version': generation, 'shape': WORKFLOW_PAYLOAD_SHAPE, 'rows': ...}`) and treat a shape mismatch as a cache miss. Otherwise stale envelopes without the new fields are served after deploy.
- `planning_views.py:192` `TaskSerializer`: `source_status`, `external`, `can_operate` (per request user), `can_start_now` (manager).
- `permissions.py:5` `actor_role(request)`: roles are `MANAGER`, `RECEPTION`, `CAO`, `FAO`, `QUALITE`, `COMPTABILITE`, `COURIER`, `DENTIST`.
- `models.py:267`: `intake_version` defaults to `2`. Version-1 cases exist only historically.

### Frontend (`cabinet_frontend/src/`)
**Live laboratory path:**
1. Sidebar **Commandes** (`LabAdminLayout.jsx:5-7`).
2. `OrderManagement` (`LabWorkspace.jsx:43`) shows two columns, "Commandes reçues" and "Commandes acceptées", using `OrderSummary` cards. "Accepter" is a **PATCH** `{accepted:true}` (line 53, `App.jsx:213`). The status stays `DEMANDE_RECUE`, so a separate "Valider → Analyse" click is needed.
3. Clicking a card switches to the tab **"Étapes de commandes"** (select dropdown + `ProductionCard` with `diagram`). That card shows a **drag-and-drop step diagram** (`ProductionWorkflow.jsx:125-135`) and auto-opens the dialog.
4. `BpmnCasePanel` (dialog) has **three tabs** (`BpmnCasePanel.jsx:68`):
   - "Étape et choix techniques" (`workflowControls`: notes, "Problèmes actuels", method/treatment/date, analysis/reception checkboxes, "Enregistrer les informations", "Valider → …").
   - "Contrôles et documents" (reason note, inspection checklist, design request/decision, QR/PDF downloads, uploads, pause, resubmit, PIN, fitting, dispute, J+1 quote, workstation remark, rework, loss assessment, history; **all stacked**).
   - "Progression et machines" (`PlanningProgress.jsx`: start/complete/pause/block, equipment phases, supervised start).

**Also:**
- **Dead code:** the default export `ProductionWorkflow` (phase-filtered list, `ProductionWorkflow.jsx:47-59`) is **never imported**. Only `ProductionCard` is used (by `LabWorkspace.jsx:9`).
- **Duplicated workflow knowledge (drift risk):**
  - `allowedStages` (`ProductionWorkflow.jsx:76`) mirrors `ROLE_STAGES`.
  - The `courier` list (83) mirrors `EXTERNAL`.
  - `canAdvance` (86) re-implements guards.
  - `reworkStages` (`BpmnCasePanel.jsx:17`) mirrors `REWORK_ORIGINS`.
  - `restartSteps` (63) mirrors `case_commands.py:190-195`.
  - `statusLabels` (`messages.js:2`) and `instructions` (`ProductionWorkflow.jsx:19`) duplicate `LABELS`.
  - `completed()` (`contracts.js:35`).
- **Legacy branches in the UI:** `intake_version < 2` quality checkbox (`ProductionWorkflow.jsx:99,116`), `FRITTAGE_9H` texts.
- **Duplicate list screen:** "Vue d'ensemble" has a "Commandes" sub-tab (`LabWorkspace.jsx:36-38`) that repeats the sidebar's Commandes.
- `workstation()` (`contracts.js:36`) reads the role from `sessionStorage.demo_user.workstation_role`.
- Other portals: `DentistPortal.jsx` (uses `BpmnCasePanel` with `dentist`) and `CourierPortal.jsx` (one action per custody status, already close to the target).

### Tests that pin current controls (they will need updating)
- `tests/integration.spec.js` (mocked API, 24 tests) uses locators such as `'Ouvrir le diagramme PAT-TEST'`, `'Valider → Ramassage'` (line 109) and `'Enregistrer le contrôle'` (136, 302, 307, 423, 433), plus tab names.
- `tests/virtual-lab.live.spec.js` (real API, 9 tests) uses `'Ouvrir le diagramme …'` (99, 227, 287) and the planning/equipment controls.
- Unit tests: `npm.cmd test` runs `src/api/contracts.test.js`, `src/api/messages.test.js`, `src/planningTime.test.js`, `src/planningPhases.test.js`.
- Backend: `api/test_bpmn_acceptance.py` (the executable spec), `api/test_planning.py`, `api/test_inventory_workflow.py`, `api/test_cqrs.py`, `api/test_billing_analytics.py`, `api/tests.py`, `customers/tests.py`. Last full run: **131 passed on 15 Nov 2026**; it has not been rerun since the 21 Nov UI changes.

---

## 3. Target experience (what "done" looks like)

1. A laboratory user logs in and lands on **"À faire"**. It lists only the cases waiting for *them*, ordered by deadline risk, each with **one** clearly labelled button (for example "Contrôler l'empreinte", "Démarrer l'usinage", "Valider la finition").
2. Opening a case shows **one workspace**: a header (patient ref, dentist, teeth, material, shade, urgency, deadline + risk, pause banner), a **stepper of BPMN-level stages**, and a **"Votre action"** panel with exactly one primary action for the current step.
3. Exceptions are not removed, but they sit behind **"Signaler un problème"**: pause/resume, documented rework, loss assessment, block the task, workstation remark.
4. Dossier material is in a collapsible **"Dossier"** section: documents and uploads, QR label, delivery note, design reviews, notes, evidence and history, full detailed route.
5. A decision is **one gesture**. Examples: "Tout conforme" + "Valider le contrôle → <étape suivante>"; "Analyse validée → continuer"; planning with the delivery date prefilled from the computed deadline.
6. The frontend no longer re-implements workflow rules. The server describes the current step, and a per-user endpoint says what is actionable.

User-visible stages (display grouping only; statuses are unchanged on the wire):

| Stage key | French label | Statuses |
|---|---|---|
| `COMMANDE` | Commande | `DEMANDE_RECUE`, `ANALYSE_DEMANDE` |
| `RECEPTION` | Collecte et réception | `ATTENTE_RAMASSAGE`, `EN_ROUTE_LABO`, `A_CONFIRMER` |
| `CONTROLE_ENTREE` | Contrôle d'entrée | `CONTROLE_DOSSIER`, `RETOUR_DEMANDE` |
| `MODELE` | Plâtre et scan | `COULEE_PLATRE`, `SCAN_LABO`, `CONTROLE_MODELE`, `RECOULER`, `RESCANNER` |
| `CONCEPTION` | Planification et conception | `PLANIFICATION`, `SALLE_CAO`, `VALIDATION_CAO`, `MODELE_TRAVAIL`, `MODELAGE` |
| `FABRICATION` | Fabrication | `PREPARATION_CNC`, `USINAGE_CNC`, `TRAITEMENT_THERMIQUE`, `FRITTAGE_9H`, `PREPARATION_3D`, `IMPRESSION_3D`, `LAVAGE_SECHAGE`, `POST_POLYMERISATION`, `FABRICATION_MANUELLE`, `A_REFAIRE` |
| `FINITION_QC` | Finition et contrôle qualité | `FINITION`, `CONTROLE_QUALITE`, `CONDITIONNEMENT` |
| `LIVRAISON` | Livraison et essayage | `PRET_EXPEDITION`, `EN_ROUTE_CABINET`, `LIVRE`, `ESSAYAGE` |
| `CLOTURE` | Clôturé | `CLOTURE` |

Billing is a **parallel track** (`billing_stage`, statement line, contested flag). Show it as a badge, not as a stage.

---

## Phase 0: baseline (no code changes)

1. `git status`, record HEAD. Confirm the demo stack is up: `docker compose -f compose.demo.yml ps -a`.
2. Read-only check that MY-TEST-001 is intact. Use a Django shell **inside the demo backend container** with a read-only query (status, `quality_validated`, statement lines count and amount). Do not save anything.
3. Run and record:
   - `docker compose -f compose.demo.yml exec -T backend python manage.py check`
   - `docker compose -f compose.demo.yml exec -T backend python manage.py makemigrations --check --dry-run`
   - `docker compose -f compose.demo.yml exec -T backend python manage.py test api customers --noinput` (disposable test DB)
   - In `cabinet_frontend`: `npm.cmd test`, `npm.cmd run lint`, `npm.cmd run build`, `npx.cmd playwright test`
   - Live suite on the **separate** verification project, exactly as in `DEMO_GUIDE.md` §25 (project `cabinet-ui-verification`, ports 18081/18001, `compose.verify.yml`). Stop it afterwards with volumes preserved.
4. Note whether the backend images contain the current source. If not, rebuild **only** the affected services: `docker compose -f compose.demo.yml up -d --build backend celery_worker celery_beat frontend`. Never use `down -v`.
5. Report the baseline. Pre-existing failures are recorded, not "fixed" by weakening tests.

## Phase 1: one declarative workflow spec plus a cacheable step descriptor (no behaviour change)

**Goal:** a single source of truth that the rest can build on, with zero change in behaviour.

1. Create `cabinet_backend/api/workflow_spec.py`:
   ```python
   from dataclasses import dataclass
   from enum import StrEnum

   class StepKind(StrEnum):
       ACCEPT = 'ACCEPT'        # DEMANDE_RECUE (accept the request)
       CONFIRM = 'CONFIRM'      # ANALYSE_DEMANDE (analysis_validated), A_CONFIRMER (reception_validated)
       PLAN = 'PLAN'            # PLANIFICATION (method, treatment, delivery date; J+1 quote prerequisite)
       INSPECT = 'INSPECT'      # CONTROLE_DOSSIER, CONTROLE_MODELE, CONTROLE_QUALITE
       DESIGN = 'DESIGN'        # SALLE_CAO (design work; design-request when validation requested)
       WORK = 'WORK'            # manual or equipment production steps backed by a planning task
       REWORK = 'REWORK'        # A_REFAIRE, RECOULER, RESCANNER
       CUSTODY = 'CUSTODY'      # ATTENTE_RAMASSAGE, EN_ROUTE_LABO, PRET_EXPEDITION, EN_ROUTE_CABINET
       CLINIC = 'CLINIC'        # VALIDATION_CAO, RETOUR_DEMANDE, LIVRE, ESSAYAGE (dentist acts)
       DONE = 'DONE'            # CLOTURE

   @dataclass(frozen=True)
   class Step:
       key: str
       label: str                 # moved from workflow.LABELS (keep LABELS as a derived alias)
       stage: str                 # stage key from the table in section 3
       kind: StepKind
       owner_roles: frozenset     # lab roles that may perform the step (MANAGER is implicit)
       external: bool             # True where planning.EXTERNAL contains the key
       rework_origin: bool        # True where domain.REWORK_ORIGINS contains the key
       manufacturing: bool        # True where domain.MANUFACTURING contains the key
       inspection_stages: tuple = ()   # e.g. ('PHYSICAL','DIGITAL') for A_CONFIRMER/CONTROLE_DOSSIER
       confirm_field: str = ''         # 'analysis_validated' | 'reception_validated'
       instruction: str = ''           # French, moved from ProductionWorkflow.jsx `instructions`
   ```
   - Define `STEPS: dict[str, Step]` for **every** `Prescription.Status` value, including `FRITTAGE_9H`, `RETOUR_DEMANDE` and the three rework statuses.
   - Define `STAGES: list[tuple[key, label]]`.
   - Define helpers `derived_role_stages()`, `derived_rework_origins()`, `derived_manufacturing()`, `derived_external()`, `inspection_permitted()`.
   - Define `rework_restart_options(order)`: move the logic from `case_commands.py:190-195` here unchanged.
2. **Do not yet replace** the old constants. Add `api/test_workflow_spec.py` asserting that the derived sets/maps **equal** the existing literals (`domain.ROLE_STAGES`, `REWORK_ORIGINS`, `MANUFACTURING`, `planning.EXTERNAL`, the inspection `permitted` map). Also assert that every `Prescription.Status` value has a `Step` and vice versa.
3. Add `current_step` and `stages` to `PrescriptionSerializer`. Both are **role-independent**, so they are safe to cache:
   - `current_step`: `{key, label, stage, stage_label, kind, owner_roles: [...], external, rework_origin, inspection_stages: [...], confirm_field, instruction, next_key, next_label}`. Use `next_status(obj)` for `next_key`.
   - `stages`: route-aware, built from `workflow_steps(obj)`: `[{key, label, state: 'done'|'current'|'todo', steps: [{key,label}]}]`, omitting stages with no step on this route.
   - `rework_restart_options`: `[{key,label}]` from the spec helper (empty when not a rework origin).
   - Keep `workflow_steps`, `next_status` and `status_label` unchanged for compatibility.
4. Update the `active_orders` cache envelope with a shape constant (section 2, `views.py`).
5. Check the dentist portal serializer (`/platform/dentist/orders/`, in the `customers` app). If it uses its own serializer, expose the same `current_step` and `stages` there **without** lab-only data.
6. Tests: serializer output for one physical-CFAO case and one digital-3D case; cache shape-mismatch → miss; the snapshot equality test from step 2.
7. Verify: backend suite, `makemigrations --check`, `graphify update .`.

## Phase 2: "À faire" work queue (per-user, server-computed)

1. New read-only endpoint `GET /api/work-queue/` (tenant API; register in `api/urls.py`). It is **not cached** per tenant; it may reuse the cached active list and then apply per-user logic. Response: paginated `BusinessPagination` or a bounded list (≤ 500) with:
   ```json
   {"id": "...", "patient_ref": "...", "dentist_name": "...", "status": "...", "current_step": {...},
    "group": "TODO|WAITING|PAUSED|TEAM",
    "primary_action": {"kind": "INSPECT", "label": "Contrôler l'empreinte", "command": "inspection", "inspection_stage": "PHYSICAL"},
    "task": {"id": "...", "status": "...", "resource_phase": "...", "planned_start": "...", "can_operate": true, "can_start_now": false} | null,
    "deadline_at": "...", "risk": "LATE|AT_RISK|ON_TRACK", "is_fast_track": true, "is_paused": false, "pause_reason": ""}
   ```
2. **Group rules** (MANAGER sees all lab steps and can filter by role):
   - `TODO`:
     - The actor's role is in `current_step.owner_roles` and the case is not paused.
     - For `WORK`/`REWORK` kinds, additionally the current-step planning task has `can_operate == True` for this actor. Reuse `TaskSerializer.get_can_operate` logic; extract it into a function rather than duplicating it.
     - For `ACCEPT`: unaccepted `DEMANDE_RECUE` for `RECEPTION`.
     - For `COMPTABILITE`: `NEXT_DAY` cases with `total_price is None` in `DEMANDE_RECUE`/`ANALYSE_DEMANDE`/`PLANIFICATION` (manual J+1 quote).
   - `TEAM`: owner role matches but the planning task is assigned to someone else, or not assigned yet.
   - `WAITING`: steps owned by others outside the lab user's control that the user follows (`CUSTODY`, `CLINIC`, machine `CYCLE`/`AWAITING_UNLOAD` phases for the assignee). Label the waiting reason in French ("En attente du coursier", "En attente du dentiste", "Cycle machine en cours").
   - `PAUSED`: `is_paused` cases the user owns, with `pause_reason`.
3. Ordering: risk (`LATE`, `AT_RISK`, `ON_TRACK`) → `deadline_at` ascending → priority (NEXT_DAY > EXPRESS > STANDARD). Reuse `planning.case_risk` and `deadline`. Avoid N+1: prefetch planning tasks for the page's cases in one query.
4. `primary_action` labels (French): derive from kind and step. Examples:
   - ACCEPT → "Accepter et analyser"
   - CONFIRM: ANALYSE_DEMANDE → "Valider l'analyse"; A_CONFIRMER → "Confirmer la réception"
   - PLAN → "Planifier la fabrication"
   - INSPECT: PHYSICAL → "Contrôler l'empreinte"; DIGITAL → "Contrôler le fichier STL"; MODEL → "Contrôler le modèle et le scan"; QUALITY → "Contrôle qualité final"
   - DESIGN → "Concevoir" / "Soumettre le design au dentiste"
   - WORK: task READY/SCHEDULED → "Démarrer : <label>"; IN_PROGRESS + MANUAL → "Terminer : <label>"; equipment phases → the existing phase labels from `PlanningProgress.jsx:17-20`
   - REWORK → "Reprendre : <label>"
5. Frontend:
   - New component `WorkQueue.jsx`, the **default landing view** for laboratory roles other than `COMPTABILITE`. Add a sidebar entry **"À faire"** first in `LabAdminLayout.jsx` and make it the initial `labSection` in `App.jsx`.
   - Show groups as sections with counts. Each row shows patient ref, dentist, current step label, stage chip, deadline + risk badge, urgency badge, paused badge, and **one** primary button that opens the case workspace (phase 3) focused on that action. Include a search box and a role filter for MANAGER.
   - Poll like the existing list (15 s, on focus/visibility); reuse the patterns in `App.jsx:66-73`.
   - Empty state: "Rien à faire pour votre poste pour le moment."
6. **Dentist portal light version:** at the top of `DentistPortal.jsx`, an "À faire" block for cases needing the dentist: pending design review, `EN_ROUTE_CABINET` (enter PIN), `LIVRE`/`ESSAYAGE` (validate fitting), `RETOUR_DEMANDE` (resubmit). Each has one button opening the dialog on that action. Compute it from `current_step.kind == 'CLINIC'`, the existing evidence, and the status; no new endpoint is required.
7. Tests:
   - Backend: group membership per role (RECEPTION, CAO, FAO with assigned vs unassigned task, QUALITE, COMPTABILITE quote, MANAGER), ordering, tenant isolation (another lab's cases never appear), anonymous denial, no N+1 (`assertNumQueries` bound).
   - Frontend unit: label/grouping helpers.
   - Mocked Playwright: landing on "À faire", one button per row, empty state, 390px layout.

## Phase 3: one case workspace with one primary action

Replace the "Étapes de commandes" tab, the drag-and-drop diagram, and the three-tab dialog with **`CaseWorkspace.jsx`**. It is a dialog built on the existing `ActionDialog`, which already handles focus return and stacking with notifications.

1. **Header:** patient ref, dentist, clinical items (all teeth, not only the first `tooth_number`), material/shade, impression type, route, urgency, deadline (`labDateTime` from `planningTime.js`, Casablanca), risk, billing badge, pause banner with reason.
2. **Stepper:** render `order.stages` (phase 1). Show the current sub-step label under the current stage. Use `aria-current="step"`. It is read-only; **no drag-and-drop**.
3. **"Votre action"** renders exactly one component chosen by `current_step.kind` (plus the planning task for WORK):
   - `AcceptAction`, `ConfirmAction`, `PlanAction`, `InspectAction`, `DesignAction`, `WorkAction` (manual start/complete and all equipment phases; move `EquipmentControls` from `PlanningProgress.jsx` here unchanged in behaviour), `ReworkAction` (the rework status itself is a WORK-like task), `WaitingNotice` (external/clinic/courier steps: explain who acts next).
   - If the actor cannot act (not owner, task assigned to someone else, future slot): show *why*, in French, and what to do. Examples: "Tâche affectée à <nom>", "Créneau prévu à <heure> : demandez un démarrage supervisé au responsable".
   - Reason notes: reuse `ReasonNote` with the existing presets (`clinicalNotePresets`, `progressNotePresets`). Show it only where the action takes a note; mandatory where the server requires one (pause, block, cycle-finished, failed inspection, design changes, rework).
4. **"Signaler un problème"** (a disclosure button, collapsed by default) contains: Suspendre/Reprendre (`pause` command), Reprise documentée (`rework`, restart options from `order.rework_restart_options`), Évaluer les pertes d'une reprise (`assess-loss`), Bloquer la tâche / Mettre en pause la tâche (`planning-block` / `planning-pause`), Remarque du poste (`note`). Keep every existing validation and message.
5. **"Dossier"** (collapsed by default): documents list/upload/download, QR label, delivery slip PDF (statuses as today, `BpmnCasePanel.jsx:84`), design reviews, "Problèmes actuels" + "Notes du dossier / consignes techniques" with their own **explicit** save (PATCH as today), J+1 quote panel for COMPTABILITE, evidence/history, full detailed route (`workflow_steps`), planning history.
6. Navigation:
   - "À faire" rows and "Commandes" cards both open `CaseWorkspace`.
   - In `OrderManagement`, remove the "Étapes de commandes" tab and its select. Clicking an `OrderSummary` opens the workspace.
   - Rename the card affordance from "Ouvrir le diagramme" to **"Ouvrir le dossier <ref>"** and update the tests accordingly.
   - Remove the "Commandes" sub-tab from "Vue d'ensemble" (`LabWorkspace.jsx:36`). Keep "Vue production" and "Facturation".
7. **Dentist:** `DentistPortal` keeps using the same workspace in a dentist mode with only the dentist actions: design decision, issue PIN, confirm delivery PIN, fitting, resubmit, dispute, invoice PDF, documents. No lab panels, no planning.
8. Keep the `BpmnCasePanel`/`ProductionCard` exports until all imports are migrated, then delete them in phase 5.
9. Tests:
   - Update the mocked and live Playwright suites to the new locators. Keep **every behavioural assertion** (UUID idempotency header, payload contents, QR/PIN dialog clearing, error visibility above dialog, focus restore, 390px layout, reason-note retention on failure, checks never auto-selected by a reason).
   - Add tests: exactly one primary action button visible per step kind; exceptions hidden until "Signaler un problème" is opened; waiting-notice texts.

## Phase 4: fewer gestures

### 4a. Passing inspection advances (backend, opt-in flag)
In `case_commands.py` `inspection`:
- Accept an optional boolean `data['advance']`. Reject non-boolean values with a new message, translated in `messages.js`.
- If `advance is True` and the inspection **passed** and the current status is the stage's checkpoint (`CONTROLE_DOSSIER` for `PHYSICAL`/`DIGITAL`, `CONTROLE_MODELE` for `MODEL`, `CONTROLE_QUALITE` for `QUALITY`; **not** `A_CONFIRMER`):
  - **Before creating the inspection**, check that the role may perform the transition (`role == 'MANAGER'` or status ∈ `ROLE_STAGES[role]`). If not, raise a new, clear French-translated error. Do not silently record-only, because the UI promised an advance.
  - After `CaseInspection.objects.create(...)` and setting `quality_validated` for `QUALITY`: compute `target = next_status(order)`. Set `metadata['action'] = 'INSPECTION_ADVANCE'` (new persisted value, document it). Call `change_status(order, target)`, then `order.save()`.
  - Everything stays in the same transaction and idempotency receipt. `validate_source_change` must accept it through its normal linear branch (`order.status == next_status(before)` plus `require_inspection`).
- Read migration `0022_enforce_workflow_evidence_and_read_versions.py` and any PostgreSQL triggers on status changes. Confirm that the evidence row inserted earlier in the same transaction satisfies them. Also confirm `sync_order` completes the inspection step's task. If the step's task is configured as an unattended machine task, the save will raise; let it raise with its existing message.
- Return `{'inspection_id', 'passed', 'advanced': bool, 'status': order.status}`.
- Without `advance`, behaviour is **byte-for-byte unchanged**. Existing tests must still pass.
- Failed inspections: unchanged. `PHYSICAL`/`DIGITAL` → `RETOUR_DEMANDE`; `MODEL`/`QUALITY` stay at the checkpoint, and the UI then shows the rework action as the primary next step.
- Backend tests:
  - Pass + advance at each of the three checkpoints.
  - Pass + advance by a non-owner role → rejected, and **no inspection row** was created.
  - Advance requested at `A_CONFIRMER` → recorded without advancing (or rejected; choose one and test it).
  - Paused case → rejected by the existing pause guard and rolled back.
  - Idempotent retry with the same key returns the stored result and does not double-advance.
  - Audit row action is `INSPECTION_ADVANCE`.
  - The planning task for the checkpoint is completed.

### 4b. "Tout conforme" (frontend, user-approved)
In `InspectAction`:
- Checks start **unchecked**.
- A secondary button **"Tout conforme"** sets every criterion of the current stage to `true` in local state only. It does not tick "Écart nécessitant une photo" and does not submit. The user can untick afterwards.
- Primary button:
  - All checks true and no gap → **"Valider le contrôle → <next_label>"**, sending `advance: true`.
  - Any false → **"Enregistrer la non-conformité"**, requiring photo + reason (existing server rules), sending no `advance`.
  - The gap flag requires a photo (existing).
- Tests:
  - "Tout conforme" does not send any request.
  - A reason preset never ticks checks (keep the existing test).
  - Unticking after "Tout conforme" switches the button to non-conformity.
  - The payload includes all criteria + `advance: true`.

### 4c. One-click confirmations (frontend only)
- `ANALYSE_DEMANDE`: one primary button **"Analyse validée → <next_label>"** sending `advance` with `analysis_validated: true`.
- `A_CONFIRMER`: **"Réception confirmée → <next_label>"** sending `reception_validated: true`. Physical/digital intake failure remains available here through `InspectAction`'s non-conformity path, as today.
- Remove the separate checkboxes and the generic "Enregistrer les informations" button from these steps.

### 4d. Accept in one step (backend command)
Add command `accept` to `_execute`:
- Allowed: `RECEPTION` (+ MANAGER).
- Precondition: `not order.accepted and order.status == 'DEMANDE_RECUE'`.
- **Implement it the way `advance` does**: run `PrescriptionSerializer(order, data={'accepted': True, 'action_notes': notes}, partial=True, context={... 'command_action': 'ACCEPT'})` so `accepted_at` and the existing update logic apply. Then advance to `next_status` (`ANALYSE_DEMANDE`) in the same transaction, `metadata['action'] = 'ACCEPT'`.
- Check what the existing PATCH-accept path triggers (signals, planning `sync_order` task generation, cache version bump, deadline/calendar outbox) and make sure the command triggers the same things.
- Keep the PATCH path working for compatibility.
- The UI's `AcceptAction` uses the command: "Accepter et analyser".
- Tests: happy path, non-RECEPTION role denied, already-accepted denied, idempotent retry, planning tasks generated, audit action `ACCEPT`.

### 4e. Prefilled delivery date (frontend)
In `PlanAction`:
- If `order.delivery_date` is empty and `order.deadline_at` exists, prefill the date input with the **Casablanca local date** of `deadline_at`. Use the backend timezone transitions via `planningTime.js`; never the browser timezone.
- Show "Échéance calculée : <date>" next to it. If `deadline_at` is null, show "Échéance en cours de calcul" and require manual entry.
- Method + treatment + date remain required by the server.
- Primary button: **"Planifier → <next_label>"**. The next label must reflect the selected method: conventional → `MODELE_TRAVAIL`, else `SALLE_CAO`. Today this is approximated at `ProductionWorkflow.jsx:84-85`; compute it by asking the server instead, or reuse `current_step.next_label` after a save.
- If the J+1 quote is missing, show a waiting notice ("Devis J+1 requis par la comptabilité") instead of an enabled button.

### 4f. One way to finish a WORK step
In `WorkAction`, the primary path is the planning path: **Démarrer** → **Terminer** (or the equipment phases). It records actual times, which later simulations need. Show the role-based `advance` only to MANAGER, under "Signaler un problème", as **"Forcer le passage à l'étape suivante"**. It requires a reason note and sends the existing `advance` command (no backend change). Non-manager technicians no longer see two competing buttons.

## Phase 5: remove dead and duplicated UI

Use Graphify plus grep to prove that nothing imports a symbol before deleting it.

- Delete the unused default export `ProductionWorkflow` (and its `phases`/`phaseLabels` if unused), the drag-and-drop diagram, `ProductionCard` and `BpmnCasePanel` once migrated (or reduce them to thin wrappers if the tests need them, then remove them).
- Delete the frontend copies of workflow rules: `allowedStages`, the `courier` list, `canAdvance`, `reworkStages`, `restartSteps`, `instructions`. The source of truth becomes `current_step`, `rework_restart_options`, `stages` and `/work-queue/`. `statusLabels` in `messages.js` may stay for non-status labels, but status labels should come from the server; keep a fallback for preview mode (`api/preview.js`). Update the preview fixtures so the read-only preview (`npm.cmd run demo`) still works and includes `current_step`/`stages`.
- Remove the legacy `intake_version < 2` quality checkbox and `FRITTAGE_9H` texts **from the UI only**. First run a **read-only** count in the **demo** DB: cases with `intake_version < 2` or `status = 'FRITTAGE_9H'`. If any exist there, keep a minimal manager-only fallback. **Do not** remove backend legacy branches in `workflow.py`/`domain.py`; the native DB may contain such cases. Add a follow-up line to `docs/ROADMAP.md`.

## Phase 6: backend internal streamlining (pure refactor, behaviour-preserving)

1. Make `domain.ROLE_STAGES`, `REWORK_ORIGINS`, `MANUFACTURING`, `planning.EXTERNAL`, the inspection `permitted` map and `workflow.LABELS` **derived from `workflow_spec`**. Keep the names importable. The phase-1 snapshot test now guards against accidental change.
2. `rework` uses `workflow_spec.rework_restart_options(order)` for validation (same set as before).
3. Introduce `class Action(StrEnum)` in `workflow_spec.py` (or `actions.py`) with **exactly** the existing persisted strings: `ADVANCE`, `INSPECTION`, `INSPECTION_FAILED`, `INSPECTION_ADVANCE`, `REWORK`, `DESIGN_REQUEST`, `DESIGN_DECISION`, `PAUSE`, `RESUBMIT`, `PICKUP`, `LAB-DEPOSIT`, `CHECKOUT`, `CONFIRM_DELIVERY`, `ISSUE-PIN`, `FITTING`, `QUOTE`, `NOTE`, `DISPUTE`, `ASSESS-LOSS`, `ACCEPT`, `ISSUE_INVOICE`, the `PLANNING-*` values, and any others. **Grep** for every producer and consumer of `metadata['action']`, `'action':`, `command.upper()` and `command_action`, across `case_commands.py`, `domain.py`, `billing.py`, `planning.py`, `signals.py` and the tests, to build the complete list. Replace string literals in comparisons with enum members (a `StrEnum` compares equal to its string, so stored data is unaffected).
4. Replace the `_execute` if-chain with a registry:
   ```python
   HANDLERS: dict[str, Callable] = {}
   def handler(name, roles=None):
       def register(fn):
           HANDLERS[name] = (fn, roles)
           return fn
       return register
   ```
   - One function per command, same validation order and **identical error messages**.
   - `planning-*` keeps its prefix dispatch.
   - Unknown command → the same `'Unknown workflow command.'`.
   - Keep `execute_case_command`'s locking, idempotency and billing-lock behaviour exactly as is.
5. Conformance tests (`api/test_workflow_spec.py`, extend):
   - For every route combination (`impression_type` ∈ {PHYSIQUE, NUMERIQUE} × `production_method` ∈ {CFAO, IMPRESSION_3D, CONVENTIONNEL} × `design_validation_requested` ∈ {T, F} × `thermal_treatment` ∈ {AUCUN, FRITTAGE}), every key from `workflow_steps` exists in `STEPS`, and every non-external, non-clinic step has non-empty `owner_roles`.
   - Every `StepKind.INSPECT` step has `inspection_stages` and every `CONFIRM` step has `confirm_field`.
   - Every registered command name appears in at least one test module. Implement this as a test that scans the test sources for the command strings, and list any intentionally untested ones explicitly.
6. Diagram export: a management command `export_workflow` writes `docs/WORKFLOW.md` with a **Mermaid** `flowchart` per route family, generated from the spec plus `workflow_steps`. Show exception edges (rework, return, design changes) as dashed arrows. Add a test that fails if the committed file differs from the generated output.

## Phase 7: BPMN coverage matrix

Create `docs/BPMN_COVERAGE.md`. Every BPMN element and **every gateway outcome** from section 1 (G1 Oui/Non … G10 Oui/Non, plus E1–E7) gets one row with these columns:
- BPMN id
- French element name
- Code mapping (status, command, model)
- Automated test(s) (file::test name)
- Manual demo coverage (MY-TEST-001 covers only the happy physical-CFAO path with design approval, crystallisation and standard billing)
- Status: ✅ covered / ⚠️ partial / ❌ missing

Include the divergences from section 1 as rows with status and a proposed resolution. Link the file from `docs/README.md`. Add any **missing automated tests** that need no product decision (for example G10 "Oui": a contested line is excluded and a credit note is issued, if not already covered by `test_monthly_closing_real_pdf_and_credit_catalog`).

## Phase 8: approved product decisions and the v1.0 release

The original Phase 8 asked for design notes and a ⛔ stop. The product owner has now decided. Implement the decisions below, then finish the product for the 9 December defense.

### Existing pieces to reuse (found while preparing this phase; confirm with Graphify)

- **Order-entry completeness is already enforced at creation.** `case_serializers.py` (around line 105) requires:
  - `disinfected`;
  - at least one clinical item with tooth, function, form, shade and material;
  - distinct FDI teeth;
  - a verified partner clinic with a pickup address.
- **Finance:**
  - Models `BillingPeriod`, `StatementLine`, `FinanceInvoice` (immutable), `CreditNote`, `BillingDispute`, plus the analytics catalogs `MonthlyFinancialCatalog` and `MonthlyStatementCatalog`.
  - Routes under `billing/*` and `analytics/*` in `api/urls.py`.
  - UI in `FinanceDashboard.jsx`.
- **Capacity:** `GET /api/planning/workload/` (`workload_view`), `planning.deadline()` (around `planning.py:257`), `case_risk`, `DEFAULT_RULES`.
- **Immutable evidence:** `ImmutableEvidence` / `EvidenceQuerySet` in `business_models.py`, plus the PostgreSQL protections from migrations `0021`/`0022`.
- **Documents:** `documents.py`. `pdf_document()` and `delivery_slip()` still print the old brand, "Cabinet 2.0 - Bon de livraison".
- **Lab legal identity:** none exists. `customers.Client` has only `name`, and `PartnerClinic` has name, address, phone and email.
- **Dashboards:** `analytics.py`, `analytics_views.py`, `MonthlyBillingSummary`, `LabAlerts.jsx` (`DashboardAlerts`), `LabWorkspace.jsx` (`LabOverview`).

### Decisions (approved by the product owner on 25 Nov 2026)

These decisions target small and medium Moroccan dental laboratories. Dentists pay labs monthly against a statement, by cheque, LCN, bank transfer or cash. Payment delays are the main pain point.

| # | Topic | Decision for v1.0 |
|---|---|---|
| D1 | **G1 order-entry gate** | Completeness stays **blocking**, using the existing creation validation; do not add new mandatory fields. Capacity is **advisory only**: never refuse or hold an order for capacity. Warn the dentist and show the **earliest feasible date**. The dentist may submit anyway or switch to a slower service. **No `EN_ATTENTE` status** and no new workflow state. |
| D2 | **Payments (B8)** | Record payments only; **no payment gateway**. Methods: cheque, LCN, bank transfer, cash. Payments can be partial and can be allocated across several invoices of the same clinic. A bounced or cancelled cheque is recorded as an **immutable reversal**. Invoices show balance and status; receivables show **aging buckets** 0–30 / 31–60 / 61–90 / >90 days. Payment terms default to **60 days** per clinic (maximum 120, in line with Moroccan Law 69-21; display the terms, don't compute legal penalties). |
| D3 | **Manager dashboard** | One "Tableau de bord" page for MANAGER. A finance subset is visible to COMPTABILITE. |
| D4 | **Lab legal identity on documents** | Laboratory profile with ICE, IF, RC, patente (optional), address and phone, printed on **newly generated** invoices, credit notes and delivery slips. Rebrand "Cabinet 2.0" to "Gestion Labo" on new documents only. |
| D5 | **G7 "Pièce OK ?"** | **Deferred to v2.** Keep the current on-demand rework. |
| D6 | **Remake model (E6)** | **Deferred to v2** (planned: linked case for post-delivery remakes, attempts kept for in-lab rework). Keep the current same-case attempts. |
| D7 | **Lane/role alignment** | **Deferred to v2** (planned: capability bundles, several per user). Do not change role ownership. |
| D8 | **Simulator** | **Light version in v1.0 (Step 8.2b).** It is a deterministic virtual-lab run in its own isolated Compose project, uses the real workflow and planning code, and **makes no change to production code**. It produces a KPI report on deadline adherence, bottlenecks and utilisation for Moroccan lab profiles. The full Phase 9 simulator (UI, event-driven device scenarios) comes after the defense. |

### Phase 8 amendments to §0

- **A1. Migrations are allowed, additive only.**
  - New tables and new nullable or defaulted columns only. No column drops, renames or type changes, and no data rewrites of existing evidence.
  - New migrations follow `0025` (`0026_…`, `0027_…`).
  - Apply them **only** to the Docker demo (`cabinet-virtual-lab`) and verification (`cabinet-ui-verification`) projects. Never to the native database.
  - **Before the first migration** on the demo project, take a `pg_dump` of the demo database into the snapshot folder from Step 8.0, which is outside the repository and outside OneDrive. Never print credentials while doing this. Record the dump's file name and size in the report.
  - `makemigrations --check --dry-run` must be clean after each step, once that step's own migration exists.
- **A2. Immutable billing history.** Never modify an existing `FinanceInvoice`, `InvoiceDocument`, `CreditNote` or `CreditDocument`, or their stored PDFs. New identity and branding only affect documents generated after the change.
- **A3. New persisted action values** must be added to the `Action` StrEnum, documented in `docs/WORKFLOW.md` or `docs/BILLING_ANALYTICS.md`, and covered by tests.
- **A4. New backend messages** need a French entry in `messages.js` and a test in `messages.test.js` (§0 rule 8).

### Quality bar for Phase 8 (the product owner asked for "no mistakes")

A step is **done** only when **all** of the following are true.

1. **Tests first for rules.**
   - Write the backend tests for each business rule (allocations, aging boundaries, permissions, immutability, isolation) before or together with the code.
   - Every rule in this brief has at least one test that fails if the rule is removed.
2. **Nothing existing may break.**
   - The full suite must be green before you move on: Django `api customers`, frontend unit, lint, build, mocked Playwright, and the live suite on the verification project.
   - If an existing test fails, **fix the code, not the test**. Edit an existing test only when this brief deliberately changes the asserted behaviour, and list each such edit in the report with the reason.
3. **No new lint warnings.** Only the existing `App.jsx` effect warning and the bundle-size advisory may remain.
4. **No silent gaps.**
   - Every new user-visible string is French.
   - Every new backend error is translated.
   - Every new screen is usable at 390px and with a keyboard.
5. **Real stack check.** After rebuilding the demo images, click the new path once in the real demo UI as the relevant role, using a `V1-…` or verification-project record. Report what you clicked.
6. **Data safety.**
   - MY-TEST-001 is checked unchanged.
   - The `pg_dump` from A1 exists before the first migration.
   - No volume was removed.
7. **Snapshot per step** (Step 8.0, item 2), so any step can be reverted alone. No commits.
8. **When unsure, ask.** If the code contradicts this brief, or a rule is ambiguous, stop and ask the product owner instead of guessing. A wrong guess costs more than a question.
9. **After the freeze (4 Dec 23:59):** no new features, no migrations, no refactors. Only fixes for bugs on the demonstrated path, each with a regression test.

### Step 8.0: local snapshot and decision record

1. **Do not commit.** The product owner has decided not to commit yet. They will test Phases 0–8 themselves first and give the commit instruction later. Never run `git commit`, `git stash`, `git reset`, `git checkout -- <file>`, `git clean` or any command that changes the index, refs or working-tree history. Read-only git commands (`status`, `diff`, `log`) are fine.
2. **Protect the uncommitted work with local snapshots instead.** All of Phases 0–7 exist only in the working tree, inside OneDrive.
   - Snapshot folder: `%USERPROFILE%\GestionLabo-snapshots\`, which is outside the repository and outside OneDrive. Create it if missing.
   - **Before starting Step 8.1,** and again **at the end of each step**, copy the working tree to a dated subfolder named `<YYYYMMDD-HHMM>-<step>`, for example `20261125-0930-before-8.1`. Use `robocopy`.
   - **Exclude from the copy:**
     - `.env*`, `.runtime/`, `private_media/` and any other secrets or credentials;
     - `node_modules/`, `.graphify-venv/`, `graphify-out/cache` if present;
     - build outputs (`dist/`, `test-results/`, `playwright-report/`);
     - the `.git/` objects directory.
   - Alongside each copy, save `git status --short` and `git diff --stat` output (`status.txt`, `diffstat.txt`), and `git diff` as `changes.patch` for tracked files.
   - Never delete or overwrite an earlier snapshot. Report each snapshot's path and size.
   - To revert a step, the product owner, not the agent, chooses a snapshot to restore. Never restore one on your own.
3. **When the product owner later says "commit":**
   - Run `git status` first.
   - Commit only source and docs, excluding `.env`, `.runtime/`, `private_media/` and any credentials.
   - Use the branch and message the product owner gives. If none is given, propose `feat/virtual-lab-demo` and `feat: Gestion Labo v1.0 (UX streamlining, payments, dashboard, simulator)` and wait for confirmation.
   - Never push unless asked.
2. Write `docs/DECISIONS_V1.md`: D1–D8, one short paragraph each, with the date and "approved by product owner".
3. Update `docs/BPMN_COVERAGE.md`:
   - G1 becomes ⚠️ partial (advisory capacity).
   - B8 becomes ✅ covered once Step 8.2 lands.
   - G7, E6 and lanes link to "v2".

### Step 8.1: D1, advisory capacity at order entry (no migration)

**Backend**
1. Use Graphify to locate `workload_view`, `planning.deadline()`, `DEFAULT_RULES` and how a new case's tasks and durations are projected. Reuse that projection; do not write a second scheduler.
2. Add a read-only preview: `POST /api/prescriptions/capacity-preview/`, an `@action(detail=False)` on `PrescriptionViewSet`.
   - **Input:** the routing fields the dentist form already sends: `delivery_service`, `impression_type`, `production_method` if set, and the number of clinical items.
   - **Output:**
     ```json
     {
       "requested_deadline": "...",
       "feasible": true,
       "earliest_feasible_date": "...",
       "reason_code": "CAPACITY" | "CLOSED_DAY" | null,
       "message": "..."
     }
     ```
   - **Behaviour:**
     - No writes, no locks, no receipts.
     - Africa/Casablanca dates, using the same calendar rules as the existing deadline computation.
     - If the projection cannot be computed, return `feasible: null` with no warning. **Never block.**
   - **Permissions:** dentist accounts and lab roles that can create cases. Tenant-isolated exactly like the create endpoint. Never expose other clinics' cases or staff names; return dates and a reason code only.
3. **Optional:** record `capacity_warning_acknowledged` in the creation event payload **only if** this needs no migration and no change to existing event shapes. Otherwise skip it.

**Frontend (`DentistPortal.jsx`, plus the lab-side creation form if one exists)**
- Call the preview, debounced, when service, route or teeth change.
- **If `feasible === false`,** show a non-blocking amber notice: "Le laboratoire est chargé à cette date. Date de livraison réaliste : *{date}*." Offer two buttons:
  - "Envoyer quand même" submits as usual.
  - "Choisir un délai plus long" switches `delivery_service` to the next slower option (J+1 → J+2 → J+4) and re-previews.
- Never disable submission because of capacity. Completeness errors keep their current blocking behaviour.

**Tests**
- Backend:
  - feasible and infeasible projections;
  - closed-day handling;
  - `feasible: null` when not computable;
  - no DB writes (row counts unchanged);
  - tenant isolation;
  - dentist cannot see other clinics' data.
- Mocked Playwright: the warning appears, "Envoyer quand même" submits, and the slower-service switch works.
- Add the G1 test references to `docs/BPMN_COVERAGE.md`.

### Step 8.2: D2, payments and receivables (migration `0026`)

**Models** (`business_models.py`, tenant schema):

```python
class Payment(ImmutableEvidence):
    id = UUIDField(primary_key=True, default=uuid4, editable=False)
    clinic = ForeignKey('api.PartnerClinic', on_delete=PROTECT, related_name='payments')
    method = CharField(max_length=10, choices=[('CHEQUE','Chèque'),('LCN','LCN'),('VIREMENT','Virement'),('ESPECES','Espèces')])
    amount = DecimalField(max_digits=16, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    received_on = DateField()                 # date the lab received the payment
    due_on = DateField(null=True, blank=True) # cheque/LCN maturity ("échéance")
    reference = CharField(max_length=60, blank=True)   # cheque/LCN/transfer number
    bank = CharField(max_length=80, blank=True)
    notes = TextField(blank=True)
    recorded_by = CharField(max_length=255)
    idempotency_key = UUIDField(unique=True)
    created_at = DateTimeField(auto_now_add=True)

class PaymentAllocation(ImmutableEvidence):
    payment = ForeignKey(Payment, on_delete=PROTECT, related_name='allocations')
    invoice = ForeignKey('api.FinanceInvoice', on_delete=PROTECT, related_name='allocations')
    amount = DecimalField(max_digits=16, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    # unique (payment, invoice)

class PaymentReversal(ImmutableEvidence):
    payment = OneToOneField(Payment, on_delete=PROTECT, related_name='reversal')
    reason = CharField(max_length=20, choices=[('IMPAYE','Chèque/LCN impayé'),('ANNULE','Saisie annulée')])
    notes = TextField(blank=True)
    reversed_by = CharField(max_length=255)
    reversed_at = DateTimeField(auto_now_add=True)
```

Also add `PartnerClinic.payment_terms_days`: `PositiveSmallIntegerField(default=60)`, with a CHECK constraint between 0 and 120.

**Database protections** (same style as `0021`/`0022`):
- CHECK `amount > 0` on Payment and PaymentAllocation.
- Block UPDATE and DELETE on the three tables with a trigger, mirroring the existing immutable-evidence triggers.
- `reference` required for CHEQUE, LCN and VIREMENT: enforce in the serializer **and** with a CHECK constraint.
- `due_on` required for LCN.

**Business rules** (new `api/payments.py`, in `transaction.atomic()` with `select_for_update` on the affected invoices in a deterministic order by id; follow the existing billing lock order):
- **Allocations:**
  - Every allocated invoice must belong to `payment.clinic`.
  - The allocations must sum to exactly `payment.amount`. No unallocated credit in v1.
  - An allocation may not exceed the invoice's open balance.
- **Balance formula** (one function, used everywhere):
  - `invoice_balance = total_amount − Σ credit_notes.amount − Σ allocations.amount`, counting only allocations whose payment has no reversal.
  - `payment_status` is `PAYEE` when the balance is 0, `PARTIELLE` when 0 < balance < net, and `IMPAYEE` when the balance equals the net amount.
  - `due_date = issued_at (Casablanca date) + clinic.payment_terms_days`.
  - `days_overdue = max(0, today − due_date)`.
- **Reversal:** allowed once per payment; it reopens the balance on every invoice the payment covered.
- **Idempotency:** same body plus same key returns the original result; different body plus same key gives 409. Reuse the `CreditNote.idempotency_key` pattern.
- **Roles:**
  - Record and reverse: COMPTABILITE and MANAGER.
  - Read: COMPTABILITE and MANAGER.
  - A DENTIST may read only their own clinic's invoice balances, and only where a dentist invoice/statement view already exists.
- **New persisted action values:** `RECORD_PAYMENT`, `REVERSE_PAYMENT` (add them to `Action`).

**API**
- `GET|POST /api/billing/payments/`. POST takes `allocations: [{invoice, amount}]` and the `Idempotency-Key` header. Check that CORS still allows it.
- `POST /api/billing/payments/{id}/reverse/`.
- `GET /api/billing/receivables/`: one row per clinic with:
  - `clinic`, `terms_days`, `total_due`;
  - `not_due`;
  - `buckets` {`0_30`, `31_60`, `61_90`, `90_plus`};
  - `oldest_overdue_days`.
- Extend `InvoiceSerializer` (`business_views.py:51`) with read-only `paid_amount`, `balance`, `payment_status`, `due_date`, `days_overdue`. Compute in bulk; avoid N+1 queries.
- Leave the `MonthlyFinancialCatalog` schema untouched; receivables are computed live.

**Frontend (`FinanceDashboard.jsx`, French)**
- **Invoice cards** show "Payée / Partiellement payée / Impayée", "Reste à payer", "Échéance" and "En retard de N jours". Colour plus text, never colour alone.
- **"Enregistrer un encaissement"** dialog (existing `ActionDialog` pattern):
  - Clinic, method, amount, received date (default today, Casablanca).
  - Reference and bank, shown and required for Chèque, LCN and Virement.
  - Échéance, required for LCN and optional for Chèque.
  - Allocation table prefilled oldest-first; the user can edit it; the sum must match the amount.
  - Send `retryableRequest` with a stable idempotency key per open dialog.
- **"Impayés" panel:** a receivables table per clinic with the buckets and the total. Sort by most overdue first.
- **Payment history** with "Marquer comme impayé / Annuler la saisie": a reason dropdown, with confirmation built into the dialog because `confirm()` is unavailable.
- **Espèces:** a neutral hint, "Conservez un reçu signé." Do not encode tax limits.

**Tests**
- Backend (new `test_payments.py`):
  - partial, full and multi-invoice allocations;
  - over-allocation, cross-clinic allocation and sum mismatch all rejected;
  - reference and due-date requirements per method;
  - reversal reopens the balance, and a double reversal is rejected;
  - credit notes are included in the balance;
  - aging at boundary days 30/31/60/61/90/91 in Casablanca time;
  - role matrix;
  - dentist sees only their own clinic;
  - UPDATE and DELETE blocked at the DB level (raw SQL inside the test DB only);
  - idempotent replay and 409 on mismatch;
  - concurrent allocations can't overdraw an invoice.
- Frontend unit tests for the balance/aging helpers.
- Mocked Playwright: record a cheque, see a partial status, reverse it as impayé, and see the balance restored.
- Live suite: one payment on a **new** verification-project invoice. Never on MY-TEST-001's invoice.
- Update `docs/BILLING_ANALYTICS.md` and the B8 row of `docs/BPMN_COVERAGE.md`.

### Step 8.2b: D8, light virtual-lab simulator (no migration, no production-code change)

> **⛔ CANCELLED by the product owner (25 Nov 2026).** The simulator code and tests are implemented and stay in the repository. The monthly runs were stopped, and all `cabinet-sim` containers and volumes were deleted at the owner's request.
> - **Never create, build or start any simulation Compose project, container or volume, and never run `simulate_lab`, unless the owner explicitly asks again.**
> - Do not write `docs/SIMULATION_REPORT.md`.
> - The simulator's Django unit tests may keep running inside the normal test suite, which uses the throwaway test database.
> - Defense evidence is the demo, the regression counts and the existing multi-tenant isolation tests.
>
> The original specification below is kept for reference only.

**Goal.** Answer the defense question "how do you know it works for a real lab?" with reproducible evidence. Run a month of synthetic activity through the **real** workflow and planning code and report deadline adherence, bottlenecks and utilisation.

**Hard isolation rules (non-negotiable)**
- **Separate Compose project.**
  - Add `compose.sim.yml` (copy the verification pattern in `compose.verify.yml`) for project `-p cabinet-sim`, with **its own named volumes** and its own ports: frontend not required, API on a free port such as `18002`.
  - Never run the simulator against `cabinet-virtual-lab` or `cabinet-ui-verification`.
  - Never touch the presentation tenant schema `simlab` (despite its name, that is the demo lab).
- **Multi-tenant by design.** The simulator's own bootstrap creates **three laboratories as three separate tenants** in the `cabinet-sim` database: `sim-petit`, `sim-moyen` and `sim-grand`. It uses the same tenant-creation and account-creation path as the real product (`customers.Client`/`Domain`, `PlatformAccount`, `EmployeeProfile`), never a shortcut.
  - Each lab gets its own staff accounts (`SIM-…`), partner clinics, planning resources and machines.
  - Credentials are generated inside the sim project and never printed. The demo's `.runtime/` is not read.
  - **At least two dentists work with two labs at once**, if the model supports one dentist account linked to clinics in several tenants (check `PartnerClinic.platform_dentist` → `customers.PlatformAccount`). If it doesn't, say so in the report and skip that part. Do not change the model.
  - The three labs run **interleaved on the same simulated clock**, so their activity overlaps in the database, Redis cache and Celery, as it would in production.
- **Refuse to run outside that project.**
  - The management command `simulate_lab` must abort unless env `GESTION_LABO_SIMULATION=1` is set; set it **only** in `compose.sim.yml`.
  - It must also abort if the target schema is `simlab` or holds any case not created by the simulator. Test both refusals.
- **No production-code change.**
  - Put everything in a new module, for example `cabinet_backend/api/simulation/`: the command, the scenario definitions and the report writer. Existing application files must not change, except to register the command, if registration needs a change at all.
  - **Clock.** Commands and planning call `django.utils.timezone.now()` (for example `planning.py:95` in `sync_order`, `:280` in `slot_for` and `:492` in `task_command`); `recalculate(now=)` and `case_risk(now=)` already accept a time. Drive time with `unittest.mock.patch('django.utils.timezone.now', clock)` **inside the simulation command only**, advancing a virtual clock.
  - **Before relying on the patch,** use Graphify and grep to list every time source the simulated path uses: `timezone.now`, `auto_now(_add)`, `datetime.now`, `date.today`, and PostgreSQL `now()` / `CURRENT_TIMESTAMP` in migrations, triggers and defaults. Report how each one is handled. If a database-side `now()` would break a simulated timeline, **stop and report** before working around it.
  - **External effects:** `EXTERNAL_DELIVERY_ENABLED=0`. Run any outbox and Celery work eagerly or skip it inside the sim; never send anything.
- **Synthetic actors are labelled.**
  - Simulated technicians act only through the real commands: `execute_case_command`, `task_command`, the creation serializer, and the inspection and design-decision commands. Their account names start with `SIM-`.
  - Inspections and decisions are drawn from the scenario's probabilities and submitted explicitly. This is synthetic data in an isolated project; it does not relax the clinical rule anywhere else.
  - Never edit rows by ORM or SQL to advance a case.

**Scenario inputs** (`api/simulation/scenarios.py`; a seeded RNG, so the same seed gives the same report):

| Input | Values |
|---|---|
| Lab profiles | `PETIT`: 2 technicians, no mill, about 8 cases/working day. `MOYEN`: 5 technicians, 1 mill, 1 furnace, about 20/day. `GRAND`: 10 technicians, 2 mills, 2 furnaces, about 60/day. |
| Calendar | Mon–Fri full days; Saturday half-day; Friday midday break; a **Ramadan** variant with reduced hours; one fixed public holiday in the month. Use the existing planning availability models; don't invent a calendar system. |
| Demand | Route, material and delivery-service mix (mostly J+4, some J+2, few J+1). A **summer peak** variant at ×1.5 volume. |
| Failures | Probabilities per gateway: failed physical/digital intake (G3/G4), failed model control, design changes requested, failed quality (G8), failed fitting (G9), and a **machine down for one day**. |
| Couriers | Pickups and deliveries in one or two rounds a day, so "ready" is not the same as "delivered". |

**Run set for the report** (each run covers 4 simulated weeks, with the three tenants running together):

| Run | Tenant conditions |
|---|---|
| 1. Normal month | All three tenants normal |
| 2. Ramadan | All three tenants on reduced hours |
| 3. Mixed | `sim-moyen` summer peak, `sim-grand` with one machine down, `sim-petit` normal |

Keep the total runtime reasonable. If it is too slow, reduce `sim-grand` volume and say so in the report.

**Multi-tenant isolation checks** (run automatically at the end of each run; any failure fails the run):

1. **Data isolation.** For every lab role and every tenant, call the real API as that account and assert that only that tenant's data comes back. Cover:
   - the case list;
   - `work-queue`;
   - planning tasks and workload;
   - `billing/*`, including the payments and receivables from Step 8.2;
   - `dashboard/summary` (Step 8.3);
   - documents and PDFs.

   Cross-check counts against the simulator's own ledger of what it created per tenant.
2. **Cross-tenant attack attempts.** Using tenant A's account, request tenant B's case, task, invoice, payment and attachment by ID, and attempt commands on them. Every attempt must return 403 or 404 and write nothing (row counts unchanged in both schemas).
3. **Cache isolation.** The `active_orders` cache and `TenantReadVersion` keys never serve one tenant's list to another. Assert this after interleaved writes in two tenants within the same simulated minute.
4. **Multi-lab dentists.** If supported, each multi-lab dentist sees their cases from both labs, and each lab sees only its own cases from that dentist.
5. **Per-tenant numbering.** Case references, invoice numbers and statement periods are sequential per tenant and never collide or skip because of another tenant's activity. Report the numbering rule the code actually uses; don't change it.

**Outputs**
- `docs/SIMULATION_REPORT.md`, generated and clearly labelled **"Données synthétiques — simulation"**. For each run it gives:
  - cases created and delivered;
  - percentage delivered on time per service (J+4 / J+2 / J+1);
  - median and 90th-percentile lead time;
  - top 3 bottleneck steps by waiting time;
  - technician and machine utilisation;
  - rework count and its delay impact;
  - the effect of the machine-down day.
- A **"Isolation multi-tenant"** section: the number of isolation assertions and attack attempts executed per run, and the result (expected: 0 leaks, 0 unauthorized writes).
- End the report with a short "Ce que la simulation montre / ne montre pas" section. It validates workflow logic and capacity, **not** real technician behaviour or machine physics, and a pilot with a real lab is the next step.
- `docs/simulation/*.json` with the raw per-run metrics. Keep the report and JSON in the repository (uncommitted). Never put database dumps in the repository.

**Tests** (in the normal Django suite, fast):
- a tiny 2-day scenario is deterministic for a fixed seed;
- the refusal guards (env flag missing, presentation schema);
- a 2-tenant, 1-day mini-run whose isolation checks pass, plus one deliberately injected cross-tenant request that is denied;
- simulated actors go through the real guards (a simulated invalid transition is rejected exactly as for a human);
- the metric calculations on a hand-checked fixture.

**Time box: 2 days.**
- **Fallback if driving full commands is blocked after 1 day:** run a planning-only simulation. Create synthetic cases in the sim tenant through the normal creation path, complete planning tasks via `task_command`, and call `recalculate(now=…)`. Report the reduced scope honestly.
- If even that is blocked, stop and report. Do not touch production code to make it work.

**Docs:** link the report from `docs/README.md` and `README.md`. Add a "Simulation" section to `DEMO_GUIDE.md` with the exact commands to rerun it in `-p cabinet-sim` and to stop it **without** `-v`.

### Step 8.3: D3, "Tableau de bord" (no migration)

1. Inventory the existing analytics with Graphify (see "Existing pieces to reuse"). **Reuse** them. Do not add a second source of truth for any number.
2. Add `GET /api/dashboard/summary/`: a function view, per-tenant, **not** stored in the shared `active_orders` cache. It may use its own key versioned by `TenantReadVersion`, or none.
   - **Operations block** (MANAGER):
     - active cases per display stage, using the `workflow_spec` stages;
     - cases late and cases at risk, using `case_risk`;
     - deliveries due today and this week;
     - cases paused or blocked;
     - remake rate over 30 days (`ReworkCase` rows ÷ cases delivered in the window; show both counts).
   - **Finance block** (MANAGER and COMPTABILITE):
     - billed this month (current Casablanca month);
     - invoiced last closed month;
     - total receivables and the amount over 60 days;
     - open disputes.
   - Other roles get 403. Dentists never see this.
3. Frontend:
   - New `Dashboard.jsx` with KPI tiles at the top, then a stage bar chart (plain CSS/SVG, no new chart library), "En retard" and "À risque" lists linking to `CaseWorkspace`, and the finance tiles.
   - Add the nav entry "Tableau de bord" in `LabAdminLayout.jsx` for MANAGER and COMPTABILITE.
   - "À faire" stays the default landing page.
   - Works at 390px.
4. Tests:
   - backend role matrix;
   - figures against a fixture with known counts;
   - Casablanca month boundaries;
   - no per-user data leaks into the shared cache;
   - mocked Playwright for the tiles and the drill-down link.

### Step 8.4: D4, laboratory identity on documents (migration `0027`)

1. Add a tenant-schema singleton model `LaboratoryProfile` with these fields:
   - `legal_name`, `address`, `city`, `phone`, `email`;
   - `ice` (15 digits; validate the format only);
   - `identifiant_fiscal`, `registre_commerce`, `patente` (all optional);
   - `updated_at`, `updated_by`.

   Enforce one row per tenant.
2. API: `GET|PUT /api/laboratory-profile/`. MANAGER writes; COMPTABILITE reads. Add a French form section in whichever of `LabConfiguration.jsx` and `LabBusinessConfiguration.jsx` already holds lab settings.
3. Documents (`documents.py`): **for documents generated after this change only**:
   - Header "Gestion Labo · {legal_name}", plus address and phone.
   - Footer "ICE … · IF … · RC … · Patente …", showing only the filled values.
   - Replace the "Cabinet 2.0" strings.
   - With an empty profile, fall back to `Client.name` and never fail PDF generation.
   - If the delivery slip prints the patient's full name, **ask before** switching it to the patient reference/initials.
4. Leave existing stored invoice and credit PDFs untouched (A2). Test that downloading an old invoice returns the stored bytes.
5. Tests:
   - ICE validation;
   - singleton enforcement;
   - role matrix;
   - PDF text contains the identity;
   - empty-profile fallback.
6. In the demo project, fill the profile with **clearly fictitious** values via the UI, for example "Laboratoire Démo Atlas" and ICE `000000000000000`.

### Step 8.5: "v1.0" product finish (no migration; complete by 4 Dec)

- **Unfinished UI:** search for "bientôt", "à venir", "TODO", "coming soon", disabled placeholder buttons and dead nav entries. Remove or hide each with a short justification in the report. Do not hide working features.
- **Version label:** show "Gestion Labo v1.0" in the sidebar footer and the login page.
- **French copy:**
  - Grep for visible English strings and mojibake. `OperationsDashboard.jsx` showed `Ã©`-style sequences in one terminal read; determine whether the file is really corrupted before changing it.
  - Every backend error the demo path can trigger must have a French translation.
- **Demo data:** create a fresh, additive set of cases **through the real API/commands** in the demo project, prefixed `V1-`:
  - one at each of the nine display stages;
  - one overdue;
  - one failed inspection that went through rework;
  - one paused for design approval;
  - two clinics with invoices in different aging buckets, using back-dated invoices only if the API allows a test clock or fixture; otherwise use the verification project for aging screenshots.

  Never touch MY-TEST-001. Never edit rows by SQL or ORM to advance a case.
- **⛔ November closing.** From 1 Dec, the November statement can be closed, and MY-TEST-001's 1500 MAD line sits in it. Closing is irreversible. **Ask the product owner first.** Suggest rehearsing the closing in the verification project.
- **Docs:**
  - `README.md`: Features table and a "v1.0 scope / v2 roadmap" section built from D5–D8 plus device integration.
  - `DEMO_GUIDE.md`: new sections for the payment, dashboard and capacity click paths.
  - `docs/ROADMAP.md`: mark Phase 8 v1 items done; list v2.
  - A short user guide, `docs/GUIDE_UTILISATEUR.md` in French: one section per role, 5–10 lines each.

### Step 8.7: post-test UX corrections (approved by the product owner, 26 Nov 2026; frontend only)

**Context.** During the first manual demo test, the owner found that the tooth-chart dashboard (`ClinicalDashboard.jsx`) makes no sense in either portal, and that the prescription form makes the dentist type FDI numbers that a chart could select. Analysis confirmed the following defects:
- The odontogram merges the teeth of **all** cases (66 in the demo) into one mouth, mixing different patients.
- `selectedOrder = orders.find(...)` shows only the first case that contains the clicked tooth.
- The filter chips ("Toutes les dents / En fabrication / Prioritaires / Terminées") filter cases, not teeth.
- "Vue de l'arcade 3D" (`SmileModel`) is a static decorative SVG with no data; "Explorer l'arcade" only rotates it.
- "Carte des prothèses" (`ArchMap`) repeats the same data.
- The bar chart "Vue d'ensemble" computes its own client-side stage groups. This is a second source of truth next to the Tableau de bord.
- The dentist sees the lab footnote "Répartition des dossiers du laboratoire".
- The lab already has "À faire", "Tableau de bord", "Commandes", "Planning" and "Facturation". "Vue d'ensemble" also has a "Facturation" sub-tab (`BillingOverview`) that duplicates the Facturation menu.

**Rules for this step.**
- **Frontend only.** No backend, API, migration, persisted action or message-contract change.
- The quality bar and A1–A4 still apply.
- Take a snapshot before starting and after finishing (Step 8.0, item 2).
- No commit.
- No simulation containers (see Step 8.2b).
- Use Graphify before reading code. Line numbers below were read on 26 Nov; confirm them.

#### 8.7a: remove the "Vue d'ensemble" screen from the lab portal
1. Remove the nav entry `['main', 'Vue d’ensemble', LayoutGrid]` from `LabAdminLayout.jsx`. With Graphify and grep, find every other place that sends a lab user to section `main` or uses `labTab`/`setLabTab`/`activeTab`:
   - `App.jsx`: the `AlertPopup onOpen` handlers (about lines 109 and 164), logout/reset handlers (about lines 81, 101 and 147–148), `onAlertSelect`, the `LabPortal` fallback return (about line 225), and the older header nav entry `['main', 'Menu principal', …]` (about line 122).
2. **New default for lab users:** section `home`. It already resolves to `WorkQueue` ("À faire") for every role except COMPTABILITE, which gets `FinanceDashboard`. The `LabPortal` fallback must return that same `home` behaviour, never a removed screen. Remove the now-unused `labTab` state and props if nothing else uses them.
3. **Alerts must stay visible.**
   - Render the existing `DashboardAlerts` (from `LabAlerts.jsx`, with the same `alertState`, `focusRequest={alertFocus}` and `onSelect={onAlertSelect}`) at the top of the `home` screen, above "À faire" or the finance home, whenever `alertState.alerts.length > 0`.
   - `AlertPopup onOpen` switches to `home` and bumps `alertFocus`, so focus moves to the alerts panel as it does today.
   - Keep the existing focus and keyboard behaviour.
4. Delete `LabOverview` and `BillingOverview` from `LabWorkspace.jsx` **only after** Graphify and grep prove they have no other references. Keep `OrderManagement`.

#### 8.7b: remove "Vue clinique" from the dentist portal
1. In `DentistPortal.jsx`, remove the "Vue clinique" button and the `tab === 'overview'` branch. Two buttons remain: "Nouvelle prescription" and "Mes commandes (N)". **Default tab: "Mes commandes"**, or "Nouvelle prescription" when the dentist has no orders. The "À faire" panel above stays unchanged.
2. **Progress in "Mes commandes."** Each case card shows a compact read-only progress strip and the expected date.
   - **Progress strip:** use the server `stages` descriptor (the nine display stages from `workflow_spec`) if the dentist payload already contains it. Render it as an accessible ordered list, with `aria-current="step"` on the current stage and the label text visible; never colour alone.
   - **Fallback:** if `stages` is absent from the dentist payload, show `caseStatusLabel(order)` only and report it. **Do not change the backend** to add it.
   - **Expected date:** "Livraison prévue : {date}", from the existing confirmed delivery date or deadline field in the payload, formatted in `Africa/Casablanca`. Show "Date à confirmer par le laboratoire" when it is absent.
   - Stack nicely at 390px.

#### 8.7c: select teeth on a chart in the prescription form
1. Create `ToothPicker.jsx`. Move `DentalTooth` and the `upper`/`lower` FDI arrays out of `ClinicalDashboard.jsx` into it, or into a small shared module; `DemoLogin.jsx` imports `DentalTooth` and must keep working. Reuse the existing `.tooth-chart`, `.tooth-row`, `.tooth-button` and `.dental-tooth` CSS.
   - **Props:** `selected` (array of FDI numbers) and `onToggle(number)`.
   - **Buttons:** each tooth is a real `<button type="button">` with `aria-label="Dent {n}"`, `aria-pressed`, and the visible number.
   - **Layout:** upper and lower rows plus the "Maxillaire / Mandibule" divider. Show a caption "Touchez les dents à prothéser · notation FDI" and a live count "{k} dent(s) sélectionnée(s)" (`aria-live="polite"`).
   - **Mobile:** at 390px the chart scrolls horizontally inside its own container; the page body never scrolls sideways.
2. **`DentistForm` behaviour:**
   - **Selection drives the rows.** Start with **no tooth selected** (today `emptyItem()` prefills 11). The `items` rows are driven by the selection.
     - Selecting a tooth appends a row `{tooth_number: n, function: '', form: '', shade: '', material: ''}`.
     - Deselecting removes that tooth's row.
     - Rows appear in FDI chart order (upper 18→28, then lower 48→38).
     - A tooth can't be selected twice.
   - **Rows show the tooth as a heading, not an input.** Each row becomes a `<fieldset>` whose `<legend>` is "Dent {n}". Remove the "Dent FDI" number input and the `fdi-teeth` datalist. Keep the per-row "Retirer cette dent" button; it deselects the tooth on the chart too. Remove "Ajouter une dent (k/32)", because the chart replaces it.
   - **"Appliquer à toutes les dents":** with two or more rows, show this button on the first row. It copies that row's function, form, shade and material to every other row **only on that explicit click**, never automatically. Don't show it with a single row.
   - **Submitting with no tooth:** disable submit and show "Sélectionnez au moins une dent sur le schéma." next to the chart. Keep the existing client checks and server validation messages.
   - **Keep everything else as is:** payload shape (`clinical_items` with numeric `tooth_number`), capacity preview inputs, price estimate, the idempotent `retryableRequest`, STL upload, the disinfection and design checkboxes, and the created-case/PIN screen.
3. Optional; do it only if it takes under 30 minutes, and report it: show the selected teeth as small chips under the chart ("11 · 21 · 22"), each removable.

#### 8.7d: clean-up
- Delete the `ClinicalDashboard` default export, `SmileModel`, `ArchMap`, the filters, the queue and the bar chart once nothing references them. If `ClinicalDashboard.jsx` ends up holding only shared tooth code, move that code to `ToothPicker.jsx` and delete the file.
- Remove CSS rules in `src/index.css` **only** for classes that grep proves unused afterwards (candidates: `dental-dashboard`, `odontogram-*`, `anatomy-*`, `arch-map`, `smile-model`, `rotate-control`, `rotation-badge`, `treatment-*`, `featured-*`, `queue-pagination`, `overview-chart`, `bar-*`, `all-orders-link`, `dental-tabs`, `chart-caption`, `clinical-subnav` if unused). Keep every rule still used by `ToothPicker`, `DemoLogin` or the layout, including the print rules where still relevant.

#### Tests
- **Mocked Playwright** (`tests/integration.spec.js`):
  - Replace the test `clinical dashboard supports tooth selection, filters and mobile navigation` (about line 515; it clicks "Vue d’ensemble") with new tests:
    - (a) The lab nav has no "Vue d’ensemble". A lab user lands on "À faire", and COMPTABILITE lands on finance.
    - (b) An alert from the popup opens `home` with the alerts panel focused.
    - (c) Dentist tooth picker: select 11 and 21 by click and by keyboard (Enter/Space); two "Dent 11/Dent 21" fieldsets in FDI order; deselect removes the row; "Appliquer à toutes les dents" copies only on click; submit disabled with zero teeth; the payload contains the numeric teeth; 390px has no page overflow.
    - (d) Dentist "Mes commandes" shows the progress strip (or the documented fallback) and the expected date; there is no "Vue clinique" button.
  - Update any other locator that relied on the removed screens. List every changed existing test and why in the report.
- **Live Playwright** (`tests/virtual-lab.live.spec.js`, about line 492): replace `getByLabel('Dent FDI').nth(1).fill('21')` with clicking the "Dent 21" chart button. Run only on `cabinet-ui-verification`, with the env-var guard described in the notes (`VIRTUAL_LAB_FRONTEND=http://localhost:18081`, `VIRTUAL_LAB_BACKEND=http://127.0.0.1:18001`, `VIRTUAL_LAB_PROJECT=cabinet-ui-verification`). Stop that project afterwards without `-v`.
- **Unit:** add a small pure helper test for selection ordering and toggling, for example `toothPickerHelpers.test.js`.
- **Full frontend:** unit, lint (only the allowed `App.jsx` warning), build, full mocked and full live suites.
- **Backend:** no backend files change, so a full backend run is not required. Prove it by comparing backend source against the after-8.5 snapshot, excluding `local_settings.py` and `memory.md` before reading bytes.

#### Finish
- Rebuild **only** the main demo frontend:
  ```
  docker compose -p cabinet-virtual-lab -f compose.demo.yml up -d --build --no-deps frontend
  ```
- Manual check in the real demo at 1440px and 390px:
  - Demo Manager lands on "À faire"; alerts are reachable; there is no "Vue d’ensemble".
  - Demo Dentist lands on "Mes commandes" with progress and dates.
  - "Nouvelle prescription": select two teeth on the chart, then **stop before submitting** in the main demo. Submitting is tested only in the verification project.
- Confirm read-only: MY-TEST-001 unchanged, November period still open, main volumes untouched.
- Update docs:
  - `DEMO_GUIDE.md`: dentist prescription steps (click teeth instead of typing "Dent FDI 11"), lab landing page, alerts location; remove references to "Vue d’ensemble", "Vue clinique" and the odontogram dashboard.
  - `docs/GUIDE_UTILISATEUR.md`: dentist and manager sections.
  - `README.md`: the features table, if it mentions the clinical dashboard.
  - `docs/TEST_RESULTS.md`: new dated section at the top.
- Run `.\graphify.cmd update .`. Take the snapshot `…-after-8.7`. Report using the standard format. No commit.

### Step 8.8: presentation readiness after the manual end-to-end test (approved by the product owner, 26 Nov 2026)

**Context.** On 26 Nov the owner ran the full happy path by hand on `TEST-2611-01`: physical impression → CFAO → dentist design approval → CNC → crystallisation → final QC → QR courier pickup, arrival and checkout → PIN delivery → fitting. Final state: CLOTURE, one 1500 MAD November line. The run passed, but it produced the remarks below. They are recorded in `memory.md` under "Manual demo test 26 Nov 2026", items 1–20; item 21 is added here. The owner approved four demo-data decisions (§8.8-D).

**Rules.**
- All of §0, the Phase 8 amendments A1–A4 and the Quality bar apply.
- Snapshot before and after each sub-step group (8.8a–8.8f).
- No commit or push. The owner will commit and push to GitHub after re-testing, on explicit instruction.
- No simulation containers.
- No migration unless a sub-step below says it is allowed. Read-only serializer fields are allowed, with tests and a full backend run.
- Never edit case, planning or billing rows by SQL or ORM. Demo data changes go through the real API or commands, using a guarded script in `demo/` that follows the pattern of `demo/prepare_v1_cases.py`: Docker, simulation and DB guards before `django.setup()`, never printing tokens or PINs, an idempotent ledger, and its own stdlib guard tests.
- **Never touch MY-TEST-001, TEST-2611-01 or the November period** (no closing).
- **Order of work:** 8.8-D (data) first, because it changes what every screen shows. Then 8.8a → 8.8f.
- Feature freeze is still **4 Dec 23:59**. If time runs short, cut from the end of the "Cut order" list.

#### 8.8-D: demo data (owner-approved decisions 1–4)
1. **Realistic team.** Add these staff with the existing account, workstation and assignment flows (the same APIs the admin and configuration screens use). Use clearly synthetic names in the existing style:
   - `Demo Reception B` (RECEPTION)
   - `Demo CAD C` (CAO)
   - `Demo Fabrication B` and `Demo Fabrication C` (FAO)
   - `Demo Quality B` (QUALITE)

   That gives 2 RECEPTION, 3 CAO, 3 FAO and 2 QUALITE including the existing accounts. Then:
   - **Qualifications:** use the existing codes (`demo-cad`, `demo-print`, `demo-cnc`, plus any others the step rules use), with **different proficiency levels** (2–5) so assignment differences are visible. Example: one FAO strong on CNC/zirconia, one strong on 3D printing, one generalist.
   - **Availability:** shifts Mon–Fri 08:00–17:00 with staggered breaks (12:00–13:00 and 13:00–14:00), and Saturday 08:00–12:00 for one person per role.
   - Use the same initial synthetic password as the existing demo accounts. Never print it in reports.
2. **Opening hours.** Through the real planning-settings endpoint and UI (`planning/settings/`, manager): working days Mon–Sat, **08:00–17:00**, break **12:00–13:00**, Saturday ending 12:00 if the settings model supports per-day hours. If it doesn't, keep Mon–Fri 08:00–17:00 and document Saturday as staff availability only.
   - Do **not** edit `seed_virtual_lab.py` defaults for existing installs. It uses `get_or_create`, so a changed setting persists.
   - Document in `DEMO_GUIDE.md` that outside opening hours a step needs "Démarrage supervisé", and that rehearsal should be done during the day.
   - Then trigger a normal recalculation (`planning/recalculate/`, manager).
3. **The 48 `BROWSER-…` automated-test cases.**
   - **(a) Pause them:** use the normal `pause` command with the reason `Données de test automatisées — hors démonstration`. Paused cases' tasks are not booked (`planning.py` ~L428), so they stop occupying technicians.
     - Pause only cases that are not CLOTURE and whose pause is allowed. Report any the guards refuse, with the server's message; never force them.
     - This is reversible with `resume`.
     - Record each case ID in the script's ledger so a future "resume test data" run is possible. Do not write that resume run now.
   - **(b) Hide them from presentation views (frontend):**
     - Add a shared helper `isAutomatedTestCase(order)`: true when the environment is SIMULATION (the existing environment endpoint or flag) **and** `patient_ref` starts with `BROWSER-`.
     - Default **hidden** in: lab Commandes, dentist Mes commandes and À faire, the work queue rows, the planning lists and the Facturation "Commandes livrées" table (8.8c).
     - Show a small toggle: "Afficher les dossiers de test automatisés (N)".
     - Never hide anything outside simulation mode.
     - The live suite must still find its own BROWSER cases: tests can turn the toggle on, or assert through the API.
4. **Stock catalogue.** Through the real inventory APIs, add about 10 realistic consumables with quantity, unit (existing units only: DISQUE, GRAMMES, UNITES, …), alert threshold and unit cost in MAD. For example:
   - Zircone multicouche 98 mm, E-Max CAD blocs (A1/A2/A3), PMMA provisoire disque, Résine 3D modèles, Résine 3D provisoire;
   - Plâtre classe IV, Silicone d'empreinte, Fraises carbure Ø1/Ø2, Pâte de polissage, Liquide de glaçage.

   Put one or two **at or below** their threshold so stock alerts appear on the landing page. Opening balances must go through the normal stock-ledger path, never direct quantity edits.
5. After 8.8-D, re-run planning recalculation. Verify read-only that a **new** test case created during the day would be scheduled the same day or the next working day within opening hours. Use a verification-project rehearsal for this, not a main case.

#### 8.8a: prescription form (remarks 1, 10)
- **Fonction:** a `<select>` with Couronne, Bridge (élément), Inlay/Onlay, Facette, Couronne sur implant, Provisoire, plus "Autre…", which reveals a free-text input (max 100).
- **Forme:** a `<select>` with Anatomique, Réduite (pour céramique), Pontique, plus "Autre…".
- **Teinte:** a `<select>` with the 16 VITA classical shades A1, A2, A3, A3.5, A4, B1–B4, C1–C4, D2–D4, plus "Autre…" (free text, max 10).
- Server limits are unchanged (function/form ≤ 100, shade ≤ 10). The payload stays free text.
- "Appliquer à toutes les dents" copies the selected values, including any "Autre…" text.
- **Dates (remark 10):** never show raw ISO dates. Add one shared formatter for French long dates in Africa/Casablanca (for example "30 novembre 2026") and use it for "Échéance calculée" and all similar labels; grep for raw `YYYY-MM-DD` rendering. Native date inputs keep the browser locale; add `lang="fr"` on the root `<html>` if it is missing.

#### 8.8b: workspace clarity (remarks 6, 7, 9, 11, 12, 13, 14, 16, 17)
- **Stepper (6):** finished stages show ✓ and the visually hidden text "(terminée)", the same as the dentist strip.
- **Inspection form (7):** order the form as checklist → note → photo → button.
  - "Écart nécessitant une photo" is shown separately from the criteria, as a flag.
  - The "Photo de preuve" field appears only when a criterion is unchecked or the flag is set.
  - The note is required **only** on failure or deviation. On a full pass the note is optional.
  - **Check the server rule first.** If the server requires notes for a passing inspection, do **not** change the server rule. Instead, have "Tout conforme" also preselect the existing predefined reason "Contrôle conforme"; it stays explicit and editable, and never submits.
  - The clinical rule is unchanged: nothing is auto-approved.
- **Supervised start (9):** replace "Créneau prévu à … : demandez un démarrage supervisé au responsable" with a plain sentence such as "Prévu le {date} à {heure}." For a manager, add "Vous pouvez commencer maintenant (démarrage supervisé)." For other roles, add "Le responsable peut autoriser un démarrage anticipé." Keep the existing guard and button behaviour.
- **Design upload (11):** at CAO, upload the DESIGN file **inside "Votre action"** (file chooser → upload → the version is auto-selected → "Soumettre au dentiste et suspendre le délai"). Reuse the existing attachment API and `FilePicker`. The Dossier upload stays available.
- **Waiting messages (12):** make each waiting state specific, using data the server already provides (current step, pending design review date, pause reason, custody step). For example:
  - "En attente de la validation du design par le dentiste (envoyée le 26 novembre à 21:50). Délai suspendu."
  - "En attente du coursier pour la collecte."
- **Problems panel (13):** "Signaler un problème" is collapsed by default and never shows disabled actions that don't apply. Hide "Reprendre le travail" unless the case is paused.
- **Dentist view (14):** dentists never see risk badges ("À risque", "Risque non évalué") or lab-internal step descriptions. Show a simple status from the stage plus "Livraison prévue : …".
- **Durations (16):** show "{n} min de travail · {machine} réservée {start}–{end}" when the planned window exceeds the duration because of equipment phases.
- **Transient "Bloquée" (17):** when a task is blocked only because assignment or recalculation is pending, show "Affectation en cours…" with a neutral style. Keep "Bloquée" for real blocking reasons. Base this on the server's `blocking_reason` text or code; do not guess.
- **Risk on a new case (4):** investigate why a just-created case briefly showed "À risque". Fix it only if it is a display bug, for example risk computed before the first planning pass. Otherwise document the reason.

#### 8.8c: Facturation (remarks 19, 20, and the owner request "show finished orders with date, price and relevant details")
- **New default section at the top: "Commandes livrées".**
  - Month selector, **current month preselected**; clinic filter.
  - One table row per delivered case: **Réf. patient · Cabinet / dentiste · Date de livraison · Travail** (for example "Dent 11 · Couronne · E-Max · A1", multiple teeth joined) **· Service** (J+4/J+2/J+1) **· Montant** (base + express) **· Statut** (Dans le relevé / Contestée / Exclue / Facturée / Payée / Partiellement payée).
  - A **total row**. Each row opens the case workspace.
  - Use existing endpoints (statement lines, invoices, payments). If fields are missing, add **read-only** serializer fields only, with role tests: no new write path, no migration.
- **Statement adjustments (20):** the statement shows a compact table. The adjustment form (Contestée/Exclue/Motif) opens only after "Ajuster" on a row.
- **Empty sections (19):** each empty section explains why. For example "Aucune facture : les factures sont émises à la clôture du mois, après le 30 novembre." and "Aucun encaissement enregistré pour le moment."
- **"Catalogues mensuels":** preselect the current month, add a one-line explanation, or merge it into "Commandes livrées" if it duplicates it.

#### 8.8d: Planning (owner request: logical and fair split by qualification)
- The planner already scores qualification, workload (fairness), availability, urgency and continuity (`explain_score`, `planning.py` ~L298), and stores `PlanningTask.assignment_explanation`. Do **not** rewrite the planner.
- **Per-technician view:** inventory the existing "Gantt" and "Charge" views first. Make sure one of them gives a clear **day view per technician**: one row per person, hours 08:00–17:00, their tasks as blocks with reference and step, and breaks and absences greyed. The default range is today and tomorrow. Add it to the existing view if it is missing.
- **"Pourquoi cette affectation ?"** In the task drawer and the case workspace task card, render `assignment_explanation` in plain French. For example "Qualifiée CNC niveau 4 · charge actuelle 2 h 30 sur 8 h · même technicien que l'étape précédente". No new computation.
- **Fairness check:** with the 8.8-D team, run a verification rehearsal that creates about 10 synthetic cases through the API. Report hours assigned per technician per role. If one qualified person takes most of the work while equally qualified colleagues stay idle, propose a **settings-only** weight change (`PlanningSettings.weights`, raising `workload`) and **ask the owner** before applying it to the main demo. Do not change the algorithm.

#### 8.8e: QR, lot and delivery note (remarks 5, 15, 18)
- **QR download (5a):** the dentist "Prescription enregistrée" screen gets "Télécharger l'étiquette QR". Reuse the existing label endpoint.
- **QR import (5b):** the courier dialogs (collecte, arrivée, sortie) get "Importer l'image du QR". Decode in the browser with a small QR library added to `package.json`. The library is **bundled**, not loaded from a CDN, so it works offline; record the library and version in the report. Fill the existing input; the user still clicks confirm.
  - Optional: "Scanner avec la caméra" only where `getUserMedia` exists. Hide it otherwise.
  - Server checks are unchanged.
  - Mocked tests decode a generated QR PNG fixture.
  - After this, `Read-DemoQr.ps1` stays as a fallback only.
- **Lot from the case (15):** at Préparation FAO/CNC (wherever the server requires a production lot), "Votre action" offers "Créer et lier un lot" with **this case preselected** (code, machine, consumable). Reuse the existing lot API. The Stocks et lots multi-select lists **only eligible cases** (cases whose current step allows lot linkage per the server rule). Do not change the server rule.
- **Delivery note PDF (18), new documents only (A2):**
  - Labelled fields: N° de dossier, Référence patient, Cabinet, Adresse de livraison, Dentiste.
  - **Contents table:** dent, fonction, forme, matériau, teinte.
  - **Dates:** expédié le, livraison prévue.
  - **Lot(s)** with code and machine, as traceability for a custom-made device.
  - QR caption "Scanner pour confirmer la remise".
  - Two signature boxes: "Remis par (coursier) — date/heure — signature" and "Reçu par (cabinet) — date/heure — signature".
  - Keep the identity header and ICE footer. Previously stored PDFs are untouched. Add PDF text-extraction tests.

#### 8.8f: small items (remarks 2, 3, 21)
- **Login toast (2):** find why a generic "Action enregistrée." success toast appears right after login; it is likely the login POST going through the global success notifier. Suppress it for authentication requests only.
- **Clutter (3):** handled by 8.8-D item 3.
- **Opérations (21):** the page lists every background job ("Actualisation du cache · Terminé · 1 essai(s)"), which means nothing to a lab manager.
  - Remove it from the main lab navigation.
  - Expose it only under Configuration as "Diagnostic technique" (MANAGER).
  - By default show **only failed or pending** items, with "Afficher tout l'historique" to see the rest.
  - Keep the reconcile actions and the role checks.

#### Cut order (if behind schedule)
Cut from the bottom of this list first; the first items are never cut.
1. Never cut: 8.8-D, 8.8b (7, 9, 12, 14, 17), 8.8c "Commandes livrées", 8.8e delivery note.
2. 8.8a dropdowns, 8.8e lot from the case.
3. 8.8d per-technician view and explanation.
4. 8.8e QR import.
5. 8.8f.
6. The optional camera scan.

#### Verification and finish
- **Quality bar in full**, with every new behaviour tested:
  - backend tests for any read-only field and any demo script guard;
  - mocked Playwright for every UI change at 1440px and 390px, plus keyboard checks;
  - the live suite on the verification project, stopped without `-v`.
- **Full backend suite** if any backend file changed; prove unchanged backend files by hash otherwise.
- Rebuild the main demo images that changed. Run the 8.8-D scripts on main, then a **read-only** main smoke at 1440/390 as Demo Manager, Demo Dentist, Demo Courier and one technician. Do not submit anything clinical on main.
- Confirm read-only: MY-TEST-001 and TEST-2611-01 unchanged, November open, main volumes untouched.
- **Docs:**
  - `DEMO_GUIDE.md`: new click paths (QR import, lot from case, design upload in action, Commandes livrées, per-technician planning, hours and supervised start, test-case toggle).
  - `docs/GUIDE_UTILISATEUR.md`.
  - `README.md` features table.
  - `docs/TEST_RESULTS.md`: a new dated top section listing every remark number and its outcome.
  - `memory.md`: mark each remark done or skipped.
- Run `.\graphify.cmd update .`. Take the snapshot `…-after-8.8`. Report in the standard format, with a table "Remarque n° → fait / reporté (raison)". **No commit.** Stop and tell the owner it is ready for the re-test.

### Step 8.9: professional interactive charts (owner approved, 27 Nov 2026)

**Owner decisions.**
- Modernise **Tableau de bord, Facturation and Planning (Charge)** with interactive charts.
- Add **synthetic history**: one to two past months of activity, created through the API, plus whatever cases the owner creates live.
- Design reference: **TailAdmin React**, MIT licence, React 19 + Tailwind v4, the same stack as ours. Take only its dashboard look: KPI cards with trend, grid, spacing, typography. Do **not** import the template or rewrite other screens.
- Charts: **Recharts**, MIT licence, in the shadcn/ui chart style, themed with our teal palette. Bundled, so it works offline.

**Rules.**
- Quality bar, A1–A4, a snapshot before and after each part, the freeze on **4 Dec 23:59**.
- No commit until the owner says so.
- No simulation containers.
- Read-only endpoints only; no migration.
- Before writing any chart code, load the `dataviz` skill and follow it: chart choice, palette, accessibility, tooltips.

#### 8.9a: backend time series (read-only, no migration)
- Add `GET /api/dashboard/series/?days=7|30|90`, default 30. Roles: MANAGER (all blocks), COMPTABILITE (finance blocks). Isolated per tenant. Not stored in the `active_orders` cache. Africa/Casablanca day and month boundaries.
- **Response blocks:**
  - `daily`: per day, `orders_created`, `orders_delivered`, `delivered_on_time` (delivered on or before the confirmed delivery date or deadline), `reworks`.
  - `monthly_revenue`: the last 6 delivery months, base + express from statement lines, excluding excluded lines. Also the invoiced total and the net of credits, where invoices exist.
  - `aging`: reuse the existing receivables buckets (no second formula).
  - `team_load`: per active technician, planned minutes and available minutes for the period, from the existing workload computation (no second scheduler).
  - `stages`: reuse the existing dashboard stage counts.
- **Tests:**
  - role matrix and tenant isolation;
  - day and month boundaries in Casablanca;
  - on-time computation;
  - excluded lines left out;
  - figures against a hand-checked fixture;
  - query count bounded (no N+1).
- Document the endpoint in `docs/BILLING_ANALYTICS.md`.

#### 8.9b: chart foundation (frontend)
- Add `recharts` at an **exact version** at least 2 weeks old that supports React 19. Record the version and licence in the report.
- Create `src/charts/` with these shared components:
  - `KpiCard`: value, label, delta vs the previous period with ▲/▼ **and** text, an optional sparkline. Clicking it navigates (e.g. to the filtered list).
  - `ChartCard`: title, period selector, a "Voir les données" toggle that shows an accessible table of the same numbers, and empty/loading/error states.
  - Themed `BarChart`, `AreaChart`, `DonutChart` and `HorizontalBars`.
- **Styling and interaction:**
  - Teal palette, colour-blind-safe, never colour alone.
  - French tooltips with exact MAD and dates.
  - Responsive at 390px.
  - `prefers-reduced-motion` honoured.
  - Keyboard focus on clickable bars and segments, with `aria-label`.

#### 8.9c: Tableau de bord
- **Layout, in the TailAdmin style:**
  - **Row 1:** KPI cards. Active cases, deliveries this period (with sparkline), % on time, cases late or at risk, revenue this month, receivables over 60 days, rework rate.
  - **Row 2:** "Dossiers par étape", a bar chart of the 9 stages. Clicking a bar opens Commandes filtered to that stage. Beside it, "Livraisons et ponctualité", an area chart of deliveries per day or week with an on-time % line, and a 7/30/90-day selector.
  - **Row 3:** "Charge de l'équipe", horizontal bars of planned vs capacity per technician. Clicking one opens Planning filtered to that technician. Beside it, "Chiffre d'affaires par mois", a 6-month bar chart.
  - **Row 4** (manager and accounting): "Impayés par ancienneté", a donut whose segments open Facturation → Impayés.
- Keep the existing data sources. "À faire" stays the landing page.

#### 8.9d: Facturation
- Add a KPI strip at the top: billed this month, invoiced, received, still to collect, over 60 days.
- Add "Chiffre d'affaires par mois" (bars) and "Impayés par ancienneté" (donut, with clickable segments).
- The "Commandes livrées" table stays and is synced: clicking a chart month changes the table's month.

#### 8.9e: Planning → Charge
- Replace the plain "Charge" table with an interactive horizontal bar chart: planned vs available minutes per technician, grouped by role, with the utilisation % as text.
- Hover shows the detail. Clicking switches to the calendar "Par technicien (journée)" filtered to that person.
- Keep the table under "Voir les données".

#### 8.9f: synthetic history (data, owner approved)
- **Script:** new `demo/prepare_v1_history.py`, guarded like `prepare_v1_aging.py`. It runs inside the Docker container only. It needs the explicit env flag `GESTION_LABO_HISTORY_OK=1`, passed on the command line for this run only and never put in compose files.
- **Clock:** it uses a **process-local clock patch** (the same technique as the aging fixture) to create history through the **real API and commands**. Never use SQL or ORM edits of case, planning or billing rows.
- **Scope:**
  - Two new synthetic clinics: "V1-HISTO Cabinet Atlas" and "V1-HISTO Cabinet Rif", each linked to Demo Dentist with a pickup address.
  - About **40 cases** spread over the **8–10 weeks before the current month**, with references `V1-HISTO-…`.
  - A realistic mix:
    - services: mostly J+4, some J+2, a few J+1 with a quote;
    - routes: CFAO, 3D printing and conventional;
    - materials: Zircone, E-Max, PMMA, metal;
    - outcomes: about 85% on time, a few late, 2–3 reworks with documented cause and corrective action.
  - Every case is delivered through the normal custody and PIN commands and fitted. Use the presentation team accounts so team load looks realistic.
- **Billing:**
  - **Close only the past months' periods of the two V1-HISTO clinics** through the normal closing command, which creates the invoices.
  - Record payments through the normal payment API: some full, some partial, and **one bounced cheque reversal**, so the aging donut has real buckets.
  - **Never touch** SIMULATION Clinic, its November period, MY-TEST-001, TEST-2611-01, V1 cases, archived cases or any open period.
- **Behaviour:** idempotent through a run tag and ledger. Prints only references and counts, never tokens or PINs. Add stdlib guard tests.
- **Where to run:** rehearse first on `cabinet-ui-verification`, then run on main. Take a `pg_dump` of main first.
- **Dates:** the history ends before the current day. Live cases created by the owner are added naturally on top.
- **Clock check:** if the clock audit (`docs/SIMULATION_CLOCK_AUDIT.md`) shows a database-side `now()` that would make backdated rows inconsistent, **stop and report** before running on main.

#### Verification and finish
- Full quality bar:
  - backend tests for the new endpoint and full backend suite;
  - unit tests for the chart data helpers;
  - mocked Playwright for each chart: render, tooltip by hover and by keyboard focus, click-through navigation, "Voir les données" table, 390px;
  - live suite on verification.
- Main: rebuild, run the history script (after a pg_dump), then a read-only smoke with screenshots at 1440 and 390 of the three screens. Confirm the protected cases and the November period are untouched.
- Docs: `DEMO_GUIDE.md` (the charts and how to present them), `docs/GUIDE_UTILISATEUR.md` (manager and accounting), `README.md` features, `docs/TEST_RESULTS.md`, `memory.md`.
- Report a table of each sub-step with its outcome. No commit.

### Step 8.6 ⛔: deployment (only on explicit instruction)

Do **not** provision servers, buy domains or publish anything. If asked, first write `docs/DEPLOYMENT.md` covering:
- target (VPS + Docker Compose + reverse proxy with HTTPS);
- environment variable names only, never values;
- PostgreSQL plus `private_media/` backup and restore;
- signing-key persistence;
- `EXTERNAL_DELIVERY_ENABLED=0`;
- synthetic data only;
- the CNDP (Law 09-08) caveat for real patient data.

Then stop.

### Timeline (Africa/Casablanca)

| Dates | Work |
|---|---|
| 25 Nov | Step 8.0, Step 8.1 |
| 26–28 Nov | Step 8.2 (payments): the largest and highest-value item |
| 29–30 Nov | Step 8.2b (simulator, time-boxed to 2 days) |
| 1 Dec | Step 8.3 (dashboard); November-closing ⛔ question |
| 2 Dec | Step 8.4 (lab identity) |
| 3–4 Dec | Step 8.5, full verification. **Freeze 4 Dec 23:59** |
| 5–8 Dec | Bug fixes only, on request; final full verification on 8 Dec |

**If behind schedule, cut in this order:**
1. The optional parts of 8.1.
2. The 8.3 drill-down lists.
3. The 8.4 settings UI (keep the model and the PDFs).
4. 8.2b down to two runs (`MOYEN` normal and `MOYEN` Ramadan) or the planning-only fallback.

**Never cut 8.2**, and never cut the quality bar to save time. Report a cut instead.

## Phase 9: full virtual-lab simulator (after 9 December)

The light version is **Step 8.2b**. Do not start the full version before the defense. Afterwards, the product owner will decide whether to extend it with a UI, event-driven device and disconnect scenarios, staffing what-ifs and calibration against pilot-lab data. The scope already covered by 8.2b, for reference:
- **Moroccan lab profiles:** small (2 technicians, about 8 cases/day, milling outsourced), medium (5 technicians, 1 mill, 1 furnace) and a large CAD/CAM center (about 60 cases/day).
- **Calendar:** Saturday half-days, Friday midday slowdown, Ramadan hours, and lunar and fixed holidays.
- **Demand:** summer and pre-Eid peaks.
- **Couriers:** one or two rounds a day per area.
- **Injected failures:** incomplete prescriptions, failed impressions and fittings, late or bounced payments, a machine down.
- **Approach:** the real command API in a separate `-p cabinet-sim` Compose project. This needs a clock-injection seam because commands use `timezone.now()`.

---

## Verification after each phase

1. Backend:
   - `docker compose -f compose.demo.yml exec -T backend python manage.py check`
   - `makemigrations --check --dry-run` (no changes in phases 1–7; in Phase 8, clean once the step's own migration exists)
   - Phase 8 only: run `migrate` in both Docker projects and record the applied migration names. Confirm MY-TEST-001's November period is still open unless the product owner approved closing it. Record the path of the step's snapshot (Step 8.0).
   - Full `test api customers --noinput` (rebuild the backend image first if source is baked in: `docker compose -f compose.demo.yml up -d --build backend celery_worker celery_beat`)
2. Frontend (in `cabinet_frontend`): `npm.cmd test`, `npm.cmd run lint` (the existing `App.jsx` effect warning is pre-existing; add no new warnings), `npm.cmd run build`, `npx.cmd playwright test`.
3. Live suite on `cabinet-ui-verification` (`DEMO_GUIDE.md` §25), then stop that project **without** `-v`.
4. Rebuild the main demo frontend so the presentation shows the new UI: `docker compose -f compose.demo.yml up -d --build frontend` (plus the backend services when backend code changed). Then confirm read-only that MY-TEST-001 is unchanged (`CLOTURE`, quality validated, one 1500.00 MAD line).
5. Run `.\graphify.cmd update .`.
6. Manual smoke at 390px and desktop: as Demo Reception, land on "À faire", accept and analyse, confirm reception (use the verification stack or a **new** `DEMO-…` case, never MY-TEST-001), inspect with "Tout conforme", and plan with the prefilled date.

## Documentation to update

- `DEMO_GUIDE.md`: §5 (dialog → workspace, "À faire", "Signaler un problème", "Dossier"), §§7–21 (every click path that changed), and the locator names.
- `README.md`: the Features table and the "Production planning and manual progress" paragraph.
- `docs/TEST_RESULTS.md`: a new dated section at the top with the exact counts and commands, kept in the existing style. Never delete historical sections.
- `docs/ROADMAP.md`: move completed items and add the phase 8/9 gates and the legacy-branch follow-up.
- `docs/README.md`: link `BPMN_COVERAGE.md`, `WORKFLOW.md` and `SIMULATION_DESIGN.md`.

## Reporting format (end of each phase)

- Files changed (paths) and new files.
- Behaviour changes visible to users (French UI strings added or removed).
- New persisted action values and new API fields or endpoints.
- Test results with counts and durations, plus anything not run and why.
- Confirmation that MY-TEST-001 is intact and that no volume or native DB was touched.
- Open questions. At ⛔ gates, stop here.

---

# RESUME HANDOFF — PHASE 8 FINAL EVIDENCE
**Recorded: 2026-11-25 22:02 UTC. Read this entire section before resuming. It supersedes the earlier resume position at the top of this brief.**

The owner stopped this agent and explicitly requested this handoff at the bottom of this file. Feature work has stopped. The existing simulation jobs were deliberately left running so the next agent can finish seamlessly. **Do not commit, push, create a PR, deploy, or close the main November statement.**

## 1. Exact completion state

- **Phases 0–7 are complete.**
- **Steps 8.0, 8.1, 8.2, 8.3, 8.4 and 8.5 are implemented and verified locally.**
- **Step 8.2b implementation and its small integration tests are complete, but the three real 28-day simulation reports are NOT complete yet.**
- The only remaining work through Step 8.5 is to let those runs finish, handle any genuine failure, validate the generated evidence, perform the final safety check and take/verify the final snapshot.
- **Step 8.6 remains an explicit deployment gate.** “Finish Phase 8” has been treated as finishing authorized work through 8.5, not permission to provision or publish.
- Full Phase 9 remains deferred until after the 9 December defense.
- Never claim all of Phase 8 is complete while monthly evidence is pending or failed.

At the final read-only status check:
| Scenario | Actual dataset tag | Latest virtual date | Result |
| --- | --- | --- | --- |
| Normal | normal-v1-c | 24 November 2026 | Still running; no result JSON |
| Ramadan | ramadan-v1-a | 9 November 2026 | Still running; no result JSON |
| Mixed | mixed-v1-a | 6 November 2026 | Still running; no result JSON |

The finalizer state was `waiting-for-three-monthly-runs`. Its timestamp is updated on state changes, **not a heartbeat**, so an old timestamp alone does not mean it stopped. `docs/SIMULATION_REPORT.md` did not exist at handoff. These dates are a snapshot, not a completion claim.

## 2. Workspace and execution details

Actual repository:
`C:\Users\SetupGame\OneDrive\Desktop\I.E\Soutenance\Projet Innov`

The session's declared writable cwd `...\Desktop\New folder` is stale. Use the real repository as `workdir`, with escalation when the tool sandbox requires it. The default login shell produced invalid-directory errors even though the repository exists. The working invocation was:

- `shell: C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`
- `login: false`
- explicit real repository `workdir`
- `sandbox_permissions: require_escalated` where required.

PowerShell 5.1: use `npm.cmd` / `npx.cmd`; do not use `&&`. Run frontend commands from `cabinet_frontend`, not the repository root. Passing non-ASCII Python source through a PowerShell pipe can turn accents into question marks: use ASCII source with Unicode escapes, or JSON-escaped UTF-8 writes. For scripts piped into Docker, the demo guide uses `cmd /c "... < demo\script.py"` to preserve raw UTF-8 bytes.

Read `AGENTS.md` and the already-installed Graphify skill `.codex/skills/graphify/SKILL.md`. Use `.\graphify.cmd query "<question>"` before new code searches, and AST-only `.\graphify.cmd update .` after code changes. Last graph: **2284 nodes, 6736 edges, 113 communities**. No semantic/API extraction is needed for this finish.

HEAD is still **42f52aa814419d62d1786b68af49ff5c54a8df23**, branch **feat/virtual-lab-demo**. All UX/Phase 8 changes are uncommitted. Use per-command `git -c safe.directory=<absolute repo>`; do not alter history, index, branch or global config. Do not spawn subagents unless newly authorized.

## 3. Environments and protected data

| Project | Purpose | Current state at handoff |
| --- | --- | --- |
| cabinet-virtual-lab | Main demo, frontend18080 / API18000 | Running, rebuilt through8.5; ready for owner testing |
| cabinet-ui-verification | Disposable verification, frontend18081 / API18001 | Stopped without -v; all data/volumes retained |
| cabinet-sim | Only simulation project | Normal plus two new independent scenario stacks running |

**Protected main case:** MY-TEST-001, UUID `7d57c87a-d0aa-4e2c-bd44-75be8e74c176`. It remains CLOTURE, quality_validated=true, is_paused=false, with exactly one standard **1500.00 MAD** November StatementLine, zero surcharge, uncontested/unexcluded. The original November BillingPeriod has `closed_at=null`; there is no `status` field on that model. Do not advance, remake, “fix”, or close its period.

All three original main volumes retain CreatedAt **2026-11-10T20:53:50Z**:
`cabinet-virtual-lab_demo_postgres`, `..._demo_redis`, `..._demo_runtime`.

No native PostgreSQL access, SQL/ORM case advancement, volume removal, reset, destructive seed, external email/WhatsApp, or device integration is authorized. Never read/print/copy `.env`, `.runtime`, signing keys, bootstrap credentials, private_media, native local_settings.py, memory.md, tokens or PINs. Normal authorized API authentication may hold tokens/PINs in process memory; never log them. Synthetic report JSONs at the explicitly named simulation-report paths are the intended evidence, not private credential files.

The main fictitious laboratory profile remains **Laboratoire Démo Atlas**, ICE fifteen zeros. The main V1 cases are additive and use suffix **856684f9**: all nine stages plus V1-RETARD, V1-REPRISE and V1-DESIGN. Search V1- in Commandes. Advanced stage examples/rework use the conventional route; CAD/FAO preparation/design examples use CFAO. Existing demo records are retained.

## 4. Evidence paths and existing snapshots

Do not rediscover all prior work. Read these nonsecret temporary pointer files:
- `%TEMP%\gestion-labo-step82b-path.txt` → simulation campaign evidence directory.
- `%TEMP%\gestion-labo-step85-path.txt` → final product verification evidence.
- `%TEMP%\gestion-labo-step84-path.txt` → identity/PDF checkpoint evidence.
- `%TEMP%\gestion-labo-phase7-path.txt` → directory containing the read-only `protected_case.py` helper.
- `%TEMP%\gestion-labo-phase8-continuation.md` → long chronological scratch checkpoint; its newest sections are the relevant ones.

Simulation campaign directory at handoff:
`C:\Users\SETUPG~1\AppData\Local\Temp\gestion-labo-ux-step82b-20261125-m550j9xw`

Step8.5 evidence:
`C:\Users\SETUPG~1\AppData\Local\Temp\gestion-labo-ux-step85-20261125-g_qninbz`

Latest completed source snapshot:
`C:\Users\SetupGame\GestionLabo-snapshots\20261125-212514-after-8.5`
(283 files, 19,770,495 bytes; clean exclusions).

Snapshot helper:
`%TEMP%\gestion-labo-snapshot-phase8.py`
Run from the real repository with a fresh tag, e.g. `python <helper> after-8.2b-reports`. It creates a unique snapshot outside OneDrive and excludes private files/dependencies/builds/.git. Keep all earlier snapshots. Earlier pre-correction snapshots accidentally included ignored local_settings.py/memory.md; the correction is documented in TEST_RESULTS. Do not open, recopy or delete those earlier copies. The current helper explicitly excludes them.

Approved pre-migration dumps are outside the repository in earlier snapshots; do not make a new dump unless needed. Native DB was never used.

## 5. Running monthly campaign — READ BEFORE TOUCHING DOCKER

All runs retain **28 days**, seed **20261209**, GRAND **12/day** (60 nominal, reduction explicitly allowed and documented), and the original approved staffing:
2/5/10 conception/manufacturing technicians **plus one receptionist and one quality operator per lab** = **4/7/12 scheduled staff**. Do not change workload, clocks, rules or guards just to get a green result.

Frozen images, validated against both tags and actual running backend containers:
- cabinet-sim-backend: `sha256:d2dd3ced97cdbb50e175c39f340ec5a8afca06387f9d720eb71bdaf544e879df`
- cabinet-sim-bootstrap: `sha256:a3f4ca39b1d165b8664630eae60b43c5d0a510988108583af974c211d1907a7b`

They are pre-D4 images, with the same workflow/planner/payment/dashboard implementation. Identity/PDF/UI work has separate241/30/83/16 test evidence. Do not rebuild or recreate an active simulation dataset. The simulator's schemas are **simpetit/simmoyen/simgrand**, not presentation schema simlab.

### Original normal run and sequential bridge

Existing exec session **3301** runs `run_months.py`; its child `run_sim.py normal-v1-c normal 28 12` still handles the original normal dataset. Host PIDs at handoff:
- run_months.py:20892
- run_sim.py:24324

PIDs/session IDs are clues, not portable identities; verify the script command before acting if they changed. Do not kill these while collecting a run. Current normal services are the original `cabinet-sim-backend-1`, `postgres-1`, `redis-1`, API18002. Original container IDs were asserted unchanged during parallel startup.

Normal evidence:
- `normal-v1-c.log`
- `normal-v1-c-result.json` (only when finished)
- `normal-v1-c-report.json` (only on success).

### Ramadan and mixed now run concurrently, without touching normal

Docker had12CPUs/8GB available. To reduce elapsed waiting, only orchestration was changed: two **new** independent stacks were added under the same cabinet-sim project, each with its own internal network, PostgreSQL, Redis and runtime volume. No production/simulator behavior was changed.

Artifacts in the simulation evidence directory:
- `compose.monthly.parallel.json` — merge with root compose.sim.yml.
- `run_parallel_months.py` — running executor, exec session **15448**, host PID14564.
- `parallel-isolation-infrastructure.json` — proof of unchanged normal IDs, distinct networks/volumes and matching frozen images.
- `parallel-up.log`.
- `ramadan-v1-a-parallel.active`, `mixed-v1-a-parallel.active` — prevent duplicate startup.

Additional service names:
`ramadan_backend/postgres/redis/bootstrap` and `mixed_backend/postgres/redis/bootstrap`.
Loopback APIs18003/18004. Database/cache hostnames remain postgres/redis inside **different networks**, so the simulator's actual environment guard stays valid. Volumes are `cabinet-sim_<tag>_{postgres,redis,runtime}`, distinct from normal and every main/verification volume.

Parallel workers write:
- `ramadan-v1-a-parallel.log`, `mixed-v1-a-parallel.log`
- `<tag>-parallel-result.json`
- `<tag>-parallel-report.json` on success.

**Important collection bridge:** the on-disk future `run_sim.py` now checks a tag's `-parallel.active` marker before any Compose startup. When the original normal batch finishes, it joins the already-running Ramadan result and copies the parallel result/report to the **official** names `<tag>-result.json` / `<tag>-report.json`, then does the same for mixed. This preserves the original batch's control flow and prevents duplicate datasets. The original normal Python process had already loaded its code and was unaffected. A `run_sim-before-parallel.py` backup is retained.

**Do not independently rerun run_months.py, run_parallel_months.py, simulate_lab, or up/recreate these active datasets.** Bootstrap refuses existing data, and the executor refuses pre-existing fresh-run volumes. Poll/join the current workers instead. Absence of official Ramadan/mixed result files while parallel files exist can simply mean the normal batch has not reached the bridge yet.

### Automatic finalizer

Current exec session **67190**, host PID2480:
`<simulation evidence>\finish_monthly_reports.py`

Old finalizer session51595 was intentionally stopped while waiting and replaced with this version; do not try to resume it. Polling exec cells221/222 are no longer needed and are not the computation jobs.

Status:
`monthly-finalization-status.json`

The finalizer:
1. Waits for all three **official** successful result files and complete report JSONs.
2. Rejects private fields, wrong scenario, non28-day/tiny runs, wrong tenant set, wrong GRAND volume, failed isolation or anything other than189 denied attack attempts per run with zero leaks/unauthorized writes.
3. Uses the actual `api/simulation/report.py` renderer, which also enforces real workflow/planning scope.
4. Validates the saved parallel network/volume proof if present.
5. Writes `docs/SIMULATION_REPORT.md` and `docs/simulation/{normal,ramadan,mixed}.json` only from these completed reports.
6. Updates README links, docs index, TEST_RESULTS and ROADMAP's current8.2b row; no fabricated KPIs.
7. Stops **all** simulation services, merging the additional parallel Compose file, **without -v**.
8. Updates the Graphify AST, runs git diff --check, creates `after-8.2b-reports` snapshot, and marks status `complete`.

On failure it preserves evidence/data/volumes, stops simulation services and marks `failed-needs-review`. It never commits. Source report/raw metrics did not yet exist at handoff.

The clock/synthetic assumptions, reduced GRAND load, censored waits, calendar occupancy, cohort interpretation and frozen pre-D4 provenance are already explained in the renderer and docs. The current campaign's concurrent real durations are not a production latency benchmark. Sequential rerun commands remain valid in DEMO_GUIDE.

## 6. How the next agent should finish

1. **Read status and tail only SIM progress lines** in the three current logs. Check active scripts/containers if needed. Do not start duplicate jobs. Prefer the existing exec sessions if accessible; otherwise inspect the named artifacts and actual process/container state.
2. If a run fails, inspect its safe log/status and the specific code path using Graphify. Preserve failed records and volumes. Correct only the simulator/orchestration as appropriate, keep all business guards, use a fresh dataset tag for a genuine rerun, and update bridge/finalizer references consistently. Never fabricate exit0/report JSON or relabel a tiny/partial run as monthly.
3. If the finalizer is still waiting and the jobs are healthy, let them compute. They are long-running real-command workloads. Do not spend model usage repeatedly launching tests or rebuilding unchanged source while waiting.
4. When status is `complete`, inspect the generated Markdown and raw JSONs:
   - all three28-day scenarios / all three tenants;
   - actual created/delivered/backlog counts and on-time denominators/limits;
   - staffing4/7/12, actual GRAND12/day, seed and calendar assumptions;
   - rework, machine-down results and censored-wait interpretation;
   - **189 attacks/run =567 total**, zero leaks and unauthorized writes;
   - links and source provenance truthful; no secrets or private file paths.
   Verify raw files match the successfully collected evidence, not probes or failed predecessors.
5. Perform the final read-only protection check in main Docker:
   - use the existing `protected_case.py` via backend stdin, not native Django;
   - compare with Step8.5 `protected-final.json` / `protected-before.json`;
   - confirm original November closed_at is still null;
   - confirm all three original volume creation timestamps, HEAD and branch unchanged.
   Do not repair any discrepancy silently.
6. Verify finalizer's stop/snapshot logs and snapshot.json; `cabinet-sim` and verification should be stopped without removing volumes. Leave the main demo running for testing unless the owner asks otherwise.
7. Check maintained document links and git diff --check. Refresh Graphify after any further code change. If only completed metric/report data changed, reuse already-passing app suites with their exact date/source continuity; run additional tests only for actual new code/failure concerns.
8. Report completion **through8.5**, generated report/snapshot paths, exact validation evidence, protected case preserved, and no commit. Explicitly retain8.6 deployment and Phase9 gates. Do not claim native deployment, external sending, real machine physics or real-lab calibration.

If an orchestration process has disappeared, first determine whether its Docker job/report still exists before choosing a safe recovery. Do not blindly recreate a partially filled dataset or change old result files. The scripts are temporary local evidence; the source demo guide has portable sequential rerun commands.

## 7. Verified product state to preserve

- Latest full backend checkpoint: **241 tests passed** at8.4 (runner711.287s). Later comparison of127 allowed Python files found application source unchanged; only standalone report explanatory copy changed. This is source continuity, not a newly rerun full suite.
- Final8.5 frontend: **30 unit**, **83 mocked Playwright**, **16 real-API Playwright** passed (0.889s /139.759s /282.233s command times).
- **Five** stdlib demo-fixture refusal tests passed.
- Lint: only permitted pre-existing App.jsx effect warning. Build passed; final banner-only copy change lint/build passed again.
- Main Django check and migration drift clean; main/verification use additive0026 and0027; no8.5 migration.
- Actual desktop/390px UI checked: login/sidebar version, reception queue/workspace, French keyboard file chooser, no page overflow. Settled screenshots were inspected.
- Main frontend rebuilt; file-picker labels and version are live.
- Verification-only aging fixtures have two new500MAD invoices in0–30/31–60 overdue buckets, actual table cells checked; main November was never closed.
- New files include FilePicker/version, additive fixture tools, French GUIDE_UTILISATEUR and SIMULATION_DESIGN; README/DEMO_GUIDE/ROADMAP/TEST_RESULTS/index are maintained.
- An earlier live invocation mixed verification frontend with main default API. It was stopped, synthetic BROWSER records retained, and protected data/profile rechecked unchanged. The correct16-test run passed. `playwright.live.config.js` now refuses mixed known targets before testing.
- **Supported live variables:** VIRTUAL_LAB_FRONTEND, VIRTUAL_LAB_BACKEND, VIRTUAL_LAB_PROJECT. For verification use18081,18001,cabinet-ui-verification. The earlier VIRTUAL_LAB_API_PORT variable was wrong and unused.
- Keep all French reason dropdowns, explicit clinical choices, top notifications, source guards, reservations, idempotency and tenant isolation.

## 8. Durable progress and requested next-agent starting instruction

The authoritative current handoff is this bottom section; the chronological TEMP continuation file and dated TEST_RESULTS contain deeper evidence. The current turn changed no product behavior: it added only simulation orchestration helpers and a dated pending-evidence execution-mode note in TEST_RESULTS, before this requested handoff append.

Suggested starting instruction:
> Read the final “RESUME HANDOFF — PHASE 8 FINAL EVIDENCE” section in AGENT_PROMPT_UX_STREAMLINING.md, use Graphify as required, join the existing simulation jobs/finalizer, and finish the Phase8 evidence and final audit through8.5. Do not restart active datasets, weaken guards, touch MY-TEST-001, close November, deploy, or commit.
