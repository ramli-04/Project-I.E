# Production planning and equipment phases

Current implementation: 24 November 2026. Planning uses the shared Django workflow and tenant database; the synthetic environment supplies fixtures, not an alternative scheduling backend. Dated test results are in [TEST_RESULTS.md](TEST_RESULTS.md).

## Tasks and scheduling

Accepted prescriptions generate applicable tasks from `api.workflow.workflow_steps`. Route changes preserve completed tasks and earlier attempts; inapplicable work is cancelled with history rather than deleted. No fictitious actual work timestamps are backfilled for an already advanced order.

The deterministic scheduler filters roles, structured qualifications/expiry, availability, shifts, absences, dependencies and machine capacity, then ranks eligible candidates using configured urgency, deadline slack, workload, continuity and stable identifiers. Free-text staff qualifications do not substitute for mandatory structured qualifications.

Automatic recalculation may move forecasts, but preserves started, paused, completed, manually blocked and locked work. An incompatible protected booking is reported as a conflict. Future bookings are provisional; READY does not authorize starting before the assigned time. A due late start/resume rebuilds movable forecasts around actual execution under the tenant lock. Manager-only `start_now: true` requires an explicit reason and still cannot displace protected work.

The heuristic is not an optimal solver. It handles at most 5,000 unfinished tasks with a configurable horizon of 1-90 days. Manual tasks need an available continuous attended window. Individual availability intervals are merged to avoid double-counting capacity; laboratory hours are the fallback when no individual weekly schedule is supplied.

## Technician and machine occupancy

Autonomous operation is an explicit rule for an equipment step. Ordinary laboratories default to attended/manual work; synthetic bootstrap initializes the demo's CNC, printing and furnace rules once and preserves later operator changes.

| Resource phase | Technician | Machine | Explicit next action |
| --- | --- | --- | --- |
| PLANNED | Forecast attended intervals | Forecast reservation | Start |
| SETUP | Occupied | Occupied | Launch cycle |
| CYCLE | Released | Occupied | Confirm actual cycle completion |
| AWAITING_UNLOAD | Awaiting qualified operator | Occupied | Begin unloading |
| UNLOADING | Occupied | Occupied | Confirm unloading and finish |
| FINISHED | Released | Released | Next eligible workflow step |

Manual tasks use MANUAL and ordinary start/complete commands. Total duration includes setup and unloading; the demo defaults to 10 minutes each, with the remainder as autonomous cycle time. These are synthetic estimates, not calibrated manufacturer protocols.

An active equipment hold is unbounded until actual unloading confirmation. Estimate expiry, pausing, blocking or cycle-completion acknowledgement never frees a loaded machine. Qualified operator availability is checked again before unloading; alternate-operator handoff is not implemented. Source advancement cannot skip these phases or the existing design, lot, inspection, custody and clinical gates.

## Transactions and database constraints

- Tenant advisory locking serializes reservation planning and associated changes.
- Prescription writers consistently use `FOR NO KEY UPDATE`, retaining writer serialization while permitting deferred planning foreign-key checks and avoiding the previous planner/source lock inversion.
- Migration0024 adds planning models and `btree_gist` reservation exclusions. Migration0025 uses PostgreSQL 14+ multiranges for the two attended employee windows and continuous equipment occupancy.
- Completed tasks, events and clinical/audit records retain their immutability protections. Commands carry UUID idempotency receipts; retrying the same payload is safe.
- Overlapping employee work is permitted only during an explicitly unattended cycle. Independent machine capacity slots remain independent resources; shared batch cycles are future work.
- Rolling back0025 may fail if new split-window bookings overlap under the former full-duration employee rule. Review data compatibility before a schema rollback.

Recalculation runs through the durable tenant-aware outbox/Celery pipeline. A source transition and its planning synchronization remain subject to one transactional guard path. Redis failure does not silently discard committed work. Lists poll approximately every 15 seconds, planning every 10 seconds, and tab return refreshes cases; asynchronous replanning can briefly retain a predecessor block after unloading.

## API and permissions

All planning routes require an active authenticated laboratory membership. Couriers cannot access planning. Resource changes and supervised assignments require the manager role. Ordinary task operation also requires the assigned employee/account, workflow role and current source stage.

| Route | Purpose |
| --- | --- |
| GET `/api/work-queue/` | Uncached per-user queue, search, manager workstation filter and pagination |
| GET `/api/planning/tasks/`, `calendar/` | Paginated tasks/calendar and filters |
| GET `/api/planning/workload/` | Workload, capacity, conflicts and delivery risks |
| GET/PATCH `/api/planning/settings/` | Hours, days, horizon, weights and step rules |
| `/api/planning/availability/`, `qualifications/` | Structured availability and qualifications |
| GET `/api/planning/accounts/` | Active laboratory accounts for staff linkage |
| GET `/api/planning/events/` | Immutable task/prescription event history |
| POST `/api/planning/recalculate/` | Durable recalculation |
| POST `/api/planning/tasks/{id}/assign/`, `reschedule/`, `lock/` | Supervision with eligibility/conflict checks |
| POST `/api/prescriptions/{id}/command/` | Existing idempotent workflow command entrypoint |

Task commands include `planning-start`, `planning-pause`, `planning-block`, `planning-resume`, `planning-complete`, `planning-launch-cycle`, `planning-cycle-finished` and `planning-begin-unload`. Payloads include the task UUID and notes; `start_now` is a supervised option. Successful completion advances through the existing clinical workflow. External design, custody, PIN and fitting steps retain their specialized commands.

## User interface and time

### Personal work queue (UX Phase 2)

Laboratory users land on **À faire**; accounting retains **Facturation** as its landing page and has a queue for manual J+1 quotes. The read-only queue groups owned work, external handoffs, paused cases and work assigned elsewhere. It uses the existing task assignment permission function shared with `TaskSerializer`, and the existing planning risk/deadline calculation. Manager role filters narrow the work shown without impersonating another technician. Accepted legacy requests still at DEMANDE_RECUE retain a path to analysis.

Case/task/dependency reads are batched and user permissions are never stored in the tenant-shared active-list cache. Pagination defaults to 50 and allows at most 200 rows per response. Search and role filters run on the server; the current implementation calculates risk across matching active cases before pagination, so very large laboratories still require the load-testing listed in ROADMAP.md. Closed cases are omitted; delivered cases remain visible while waiting for fitting. All lab staff can follow external handoffs because no case-subscription model exists.

Assignment permission does not establish readiness. Future bookings and pending dependencies show French explanations and a planning link. The assigned operator still sees explicit cycle-completion/unloading entry points in **En attente**. Source pause, task pause, machine occupancy, clinical inspections and managerial early-start checks remain distinct. Each queue button opens the shared case workspace; it never executes a workflow command directly. Phase 4 combines acceptance with opening analysis through the explicit command described below.

The queue refreshes every 15 seconds and on focus/visibility return. Manual refresh reports a French notification. The dentist's smaller action list is derived from server step metadata and existing delivery/design/fitting states, with no additional endpoint or inferred approval.

### Read-only case workflow metadata

UX Phase 1 added `current_step`, `stages` and `rework_restart_options` to the existing prescription serializer, including the dentist portal. `api/workflow_spec.py` declares every status, display stage, step kind, legacy workstation ownership, inspection track and rework/manufacturing/external flag. Phase 6 derives the runtime guard constants and `workflow.LABELS` from this specification. An independent fixture captured before consolidation freezes their original values.

`current_step` contains the status key/label, stage key/label, kind, owner-role codes, external/rework flags, applicable inspection stages, confirmation field, French instruction and next key/label. Intake inspection stages follow the case's physical/digital track. Labels and destinations follow the existing route, including its selected thermal treatment. The descriptor contains no assigned employee, personal execution permission or planning record. Legacy workstation ownership is descriptive: clinic/custody commands, assignee checks and all existing guards remain authoritative.

`stages` groups only applicable route steps into Commande, Collecte et réception, Contrôle d'entrée, Plâtre et scan, Planification et conception, Fabrication, Finition et contrôle qualité, Livraison et essayage, and Clôturé. Its `done/current/todo` values describe position in the route, not a new clinical approval or actual work timestamp. Rework does not mark a future restart stage done. Billing remains a separate track. Restart choices preserve the existing command's allowed set and are empty outside a rework-capable source step.

All three fields are read-only and viewer-independent, so the tenant-shared active-order cache can contain them. Cache envelopes require both the current tenant read generation and shape `workflow-step-v2` (Phase 4 adds planning destinations); missing/older shapes are rebuilt on read. Workstation notes are still filtered after the shared cache. Dentist list/create/retry responses now pass request context through the existing serializer so internal workstation notes are filtered there too. No status, role, command, persisted action value or migration is added in Phase 1. Existing `workflow_steps`, `next_status` and `status_label` fields remain compatible.

### Case workspace (UX Phases 3-5)

Queue rows, order cards, dentist cases and the planning task drawer open `CaseWorkspace.jsx`, built on the existing native `ActionDialog`. The header lists every tooth/material/shade, route, deadline, billing state and pause reason. The server's work queue supplies risk; a viewer without a matching queue entry sees an explicit unavailable/closed risk label. `order.stages` renders a read-only stepper, with the current sub-step and `aria-current="step"`. There is no stage-selection tab or clinical drag-and-drop control.

**Votre action** selects one action component from `current_step.kind` and the task matching the current source step, intake revision and production attempt. Ownership, assignment, dependencies and future slots show French waiting explanations. A manager chooses the explicit supervision checkbox and supplies a reason before the single start button sends `start_now: true`; the original resource/protected-booking checks still apply. Equipment controls live in CaseActions and preserve every cycle/unloading command; the unused standalone planning-progress screen was removed in Phase 5.

**Signaler un problème** is collapsed and contains case pause/resume, task pause/block, workstation remarks, documented rework and measured losses. **Dossier** is collapsed and contains private documents, QR/PDF/PIN issuance, design history, explicit dossier-information saves, J+1 quotes, inspections, evidence, the full route and planning history. The dentist uses this same workspace with cabinet actions/documents only; no laboratory task or planning controls are fetched or shown. Phase 5 removed the unused BPMN/production exports and their duplicated stage permissions, transitions, instructions and restart lists after reference checks. The overview has production and billing sections; orders have their own sidebar entry.

Inspection checkboxes start unchecked. A saved passing record is matched to the actual revision/attempt before offering the existing separate advancement action; **Recontrôler** opens a fresh unchecked form. The Phase 4 shortcuts below retain explicit decisions and never infer approval or cycle completion. French reason dropdowns keep optional free text and existing notes payloads; selecting a reason sends nothing. Failures preserve drafts and appear at the top above the dialog. If a write commits but refresh fails, another mutation is blocked until a successful refresh so the committed operation is not repeated.

The workspace polls every 10 seconds and on focus/visibility return without resetting drafts. Dialog closure returns focus to its entry control; 390px layouts retain all clinical items, controls and visible notifications.

### Explicit shortcuts (UX Phase 4)

`accept` is a reception/manager command for an unaccepted DEMANDE_RECUE case. It uses the existing serializer's accepted-at/update logic and moves to ANALYSE_DEMANDE in one transaction/idempotency receipt, with audit action `ACCEPT`. The source save retains normal planning task generation, durable replanning/cache events and read-version invalidation. Existing PATCH acceptance and accepted legacy requests remain supported. **Accepter et analyser** opens analysis; **Analyse validée → [destination]** explicitly confirms it. **Réception confirmée → [destination]** confirms reception without a separate checkbox; its collapsed inspection section retains photographed intake failure/return handling.

`inspection` accepts optional boolean `advance`. A passing PHYSICAL/DIGITAL control at CONTROLE_DOSSIER, MODEL at CONTROLE_MODELE or QUALITY at CONTROLE_QUALITE can record evidence and advance through the normal linear domain guard. Transition ownership is checked before inserting evidence; pause, evidence, lot and equipment guards remain authoritative. The persisted history/event action is **`INSPECTION_ADVANCE`**. The source save marks the checkpoint's existing planning task completed through `sync_order`. Configuring that checkpoint as an autonomous equipment task still rejects an unconfirmed phase and rolls back the evidence. Migration0022's audited version/deferred history triggers and0024's task-history trigger remain unchanged; evidence inserted earlier in the same transaction satisfies the domain query.

With an explicit `advance` flag the result includes `inspection_id`, `passed`, `advanced` and `status`. Without the flag the original two-field result and record-only behavior remain unchanged. At A_CONFIRMER an advance request records the inspection but returns `advanced: false`; reception confirmation is separate. Failed intake still returns the case; failed model/quality controls stay at their checkpoint. The UI's **Documenter la reprise** opens the required corrective-action form without sending a command.

Criteria start unchecked. Secondary **Tout conforme** checks the current stage's criteria locally, never the photo-gap flag, and sends nothing. Unticking switches the primary action to **Enregistrer la non-conformité**, retaining photo/reason rules. With all criteria true and no gap, **Valider le contrôle → [destination]** sends `advance: true`. A reason preset never selects a criterion. Existing passing evidence remains usable through the separate advancement control; **Recontrôler** starts a fresh unchecked form.

PLAN descriptors add viewer-independent `planning_options`, calculated from the real server route for each method without saving. Cache shape `workflow-step-v2` rebuilds older envelopes. The planning button uses the selected method's server label. An absent delivery date is prefilled using `labDate(deadline_at)` and the loaded backend Casablanca transitions; a saved date or user edit takes precedence. No deadline means manual entry. Missing J+1 quotes show a waiting notice. Task start/finish and equipment phases remain the normal WORK path; only a manager sees **Forcer le passage à l’étape suivante** under problems, requiring a reason and using the existing guarded `advance` command.

### UI cleanup and compatibility (UX Phase 5)

The server descriptors, restart options, stages and personal queue remain the workflow source for the UI. `caseStatusLabel` chooses the server current-step label, status label or detailed-route label, with a French unavailable-label message when metadata is missing. The former browser case-status dictionary is gone; design, task, delivery-channel and other protocol labels remain localized. The courier serializer adds only a read-only `status_label` from the existing server workflow labels, retaining its restricted payload and permissions. Static fallback labels and route examples stay inside `api/preview.js`, including a planning case with destinations and grouped steps. The preview still rejects writes.

A read-only presentation-schema count found49 cases and no legacy intake/frittage cases. Phase 5 therefore removed the old quality checkbox and hardcoded legacy frittage UI texts. Backend legacy routes/guards remain unchanged; native-data inventory and migration are a separate follow-up in ROADMAP.md.

### Shared backend rules and command dispatch (UX Phase 6)

`domain.ROLE_STAGES`, `REWORK_ORIGINS`, `MANUFACTURING`, `planning.EXTERNAL`, `workflow.LABELS` and `case_commands.INSPECTION_PERMITTED` now derive from `workflow_spec`. The existing import names remain available. The rework handler validates the same restart set that the serializer describes through `rework_restart_options(order)`. No role, status, permission or clinical requirement changes.

`Action(StrEnum)` names the existing audit/default strings. Hyphens and underscores remain significant: for example, an unsuccessful PIN attempt records `CONFIRM-DELIVERY`, while successful delivery records `CONFIRM_DELIVERY`. Planning source actions keep their hyphens; planning-event kinds still use underscores. Historical JSON and API values are unchanged.

`case_commands.HANDLERS` registers one function per command, with the original role checks, validation order and messages. Commands beginning with `planning-` still dispatch to `task_command`. `execute_case_command` retains its transaction, billing/source lock order, digest, audit context, UUID replay and one-time-PIN receipt filtering. Handler exceptions still roll back the whole transaction.

The [generated workflow diagrams](WORKFLOW.md) cover six physical/digital × fabrication families, combining the optional design-review/thermal branches. Dashed edges describe documented rework, failed intake/resubmission and requested design changes. Generate them from a configured source checkout with `python cabinet_backend/manage.py export_workflow`. In Docker, use `export_workflow --output /tmp/WORKFLOW.md` and copy that file to the repository's `docs/WORKFLOW.md`. The verification Compose backend mounts repository documentation read-only so the regression test compares the committed file with deterministic generated output. Other conformance tests cover all 24 track/method/review/treatment combinations and require test-source coverage for every registered command and supported planning command.

### Planning screens

Planning provides day/week/month calendars, Gantt, workload, filters, immutable history and supervised assignment/locking. The Gantt shows dependencies available on the page and indicates prerequisites outside it. Calendar drag/drop rescheduling is not implemented; use the validated assignment form.

The planning drawer retains supervised assignment, duration, resource and lock controls, and offers **Ouvrir le dossier [reference]** for clinical/task actions in the shared workspace.

Timestamps are aware and use Africa/Casablanca. Backend-supplied timezone transitions keep browser inputs/displays aligned with scheduler tzdata; outside that provided window the browser uses its own rules. Workload/calendar lanes exclude unattended employee time while retaining equipment occupancy.

## Scope still open

No device telemetry, heartbeat/offline detection, shared-batch cycle, alternate unloader handoff or pre-cycle abort/recovery is implemented. There is no demonstrated large-laboratory latency guarantee. The read-only preview shows an explicit empty planning state and does not calculate real assignments. See [ROADMAP.md](ROADMAP.md) and the presenter [demo guide](../DEMO_GUIDE.md).


## Advisory capacity before case creation (v1, Step 8.1)

`POST /api/prescriptions/capacity-preview/` is a read-only projection for MANAGER/RECEPTION and linked dentists. The public dentist form uses `POST /platform/dentist/capacity-preview/` with `laboratory_id`; that gateway switches to the selected tenant and verifies the dentist has a clinic link. Neither path returns case, clinic or staff data. Both return only requested deadline, tri-state `feasible`, earliest date, reason code/message and `provisional: true`. No receipts, locks, configuration creation, route choice or reservations are written.

Input: `delivery_service`, `impression_type`, optional `production_method`, `clinical_item_count` (1-32). Dates use the existing calendar-day service deadlines in Africa/Casablanca, including actual tzdata. Shared `ordered_jobs` and `candidate_slot` are extracted unchanged from `recalculate`; both scheduling paths still use `rule`, `workflow_steps`, `slot_for`, equipment phases, employee calendars/qualifications and reservations. Item count is validated; the existing scheduler has per-case step estimates, so the preview does not invent per-tooth scaling.

When the method is not chosen, the owner approved comparison of existing routes, returning the earliest computed date without assigning a route. The projection preserves real reservations and adds known unreserved internal backlog in memory. It is a provisional lower bound: no duration is invented for unknown courier rounds, dentist decisions, future unplanned work or material-specific thermal protocols. The minimum existing thermal option is used; this never selects or recommends a clinical protocol. Missing resources, indeterminate blocked backlog, malformed routing, no result within the horizon or the existing 5000-task bound produce `feasible: null` without an alert. Capacity never refuses creation. Calendar closure is reported with `CLOSED_DAY`; otherwise a known late result uses `CAPACITY`.

The dentist form debounces lab/service/impression/teeth changes, cancels outdated requests and ignores unavailable previews. False results show the French provisional warning, an explicit submit-anyway button and J+1 -> J+2 -> J+4 slower-service choice; standard service has no slower option. A true result shows a quiet provisional date. These read-only POSTs suppress action-saved notifications. Existing completeness, disinfection, clinic and clinical-item validations remain blocking. No migration, source-state guard or persisted action was added.
